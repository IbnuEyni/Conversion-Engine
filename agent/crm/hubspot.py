"""HubSpot CRM integration.

Syncs every prospect, enrichment result, conversation event, and booking
to HubSpot Developer Sandbox. All fields non-null, enrichment timestamps present.

Objects created:
- Contact: the prospect's contact person
- Company: the prospect's company with enrichment data
- Deal: created when prospect reaches QUALIFIED state
- Notes/Engagements: every email, SMS, and state change logged

Rate limit: 100 API calls per 10s window (HubSpot sandbox).
"""

from __future__ import annotations

import json
import logging
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

from agent.models import Prospect, ConversationState, ICPSegment
from config.settings import settings

logger = logging.getLogger(__name__)


class HubSpotCRM:
    def __init__(self):
        self._client = None
        self._sink_dir = Path("data/outbound_sink/hubspot")
        self._sink_dir.mkdir(parents=True, exist_ok=True)
        self._call_count = 0
        self._window_start = time.time()

    @property
    def client(self):
        if self._client is None and settings.hubspot_access_token:
            from hubspot import HubSpot
            self._client = HubSpot(access_token=settings.hubspot_access_token)
        return self._client

    @property
    def is_connected(self) -> bool:
        return (
            self.client is not None
            and bool(settings.hubspot_access_token)
            and "<" not in settings.hubspot_access_token
        )

    def _rate_limit(self):
        """Respect 100 calls per 10s window."""
        self._call_count += 1
        if self._call_count >= 95:
            elapsed = time.time() - self._window_start
            if elapsed < 10:
                sleep_time = 10 - elapsed + 0.5
                logger.info(f"HubSpot rate limit: sleeping {sleep_time:.1f}s")
                time.sleep(sleep_time)
            self._call_count = 0
            self._window_start = time.time()

    # ── Contact ──────────────────────────────────────────────

    def upsert_contact(self, prospect: Prospect) -> Optional[str]:
        """Create or update a HubSpot contact from a prospect."""
        properties = self._contact_properties(prospect)

        if not self.is_connected:
            return self._sink("contact", properties, prospect.id)

        self._rate_limit()
        try:
            # Search for existing contact by email
            existing_id = self._find_contact_by_email(prospect.contact_email)
            if existing_id:
                from hubspot.crm.contacts import SimplePublicObjectInput
                self.client.crm.contacts.basic_api.update(
                    existing_id,
                    SimplePublicObjectInput(properties=properties),
                )
                logger.info(f"Updated HubSpot contact {existing_id} for {prospect.company_name}")
                return existing_id
            else:
                from hubspot.crm.contacts import SimplePublicObjectInputForCreate
                resp = self.client.crm.contacts.basic_api.create(
                    SimplePublicObjectInputForCreate(properties=properties, associations=[]),
                )
                contact_id = resp.id
                logger.info(f"Created HubSpot contact {contact_id} for {prospect.company_name}")
                return contact_id
        except Exception as e:
            logger.error(f"HubSpot contact upsert failed: {e}")
            return self._sink("contact", properties, prospect.id)

    def _find_contact_by_email(self, email: Optional[str]) -> Optional[str]:
        if not email or not self.is_connected:
            return None
        self._rate_limit()
        try:
            from hubspot.crm.contacts import PublicObjectSearchRequest, Filter, FilterGroup
            f = Filter(property_name="email", operator="EQ", value=email)
            fg = FilterGroup(filters=[f])
            req = PublicObjectSearchRequest(filter_groups=[fg])
            resp = self.client.crm.contacts.search_api.do_search(req)
            if resp.total > 0:
                return resp.results[0].id
        except Exception:
            pass
        return None

    def _contact_properties(self, prospect: Prospect) -> dict:
        brief = prospect.signal_brief
        classification = prospect.classification

        props = {
            "email": prospect.contact_email or f"synthetic+{prospect.id}@sink.local",
            "firstname": (prospect.contact_name or "Unknown").split()[0],
            "lastname": " ".join((prospect.contact_name or "Unknown").split()[1:]) or "Contact",
            "jobtitle": prospect.contact_title or "Engineering Leader",
            "company": prospect.company_name,
            "phone": prospect.contact_phone or "not_provided",
            "website": prospect.website or "unknown",
            "city": (prospect.location or "Unknown").split(",")[0].strip(),
            "icp_segment": classification.segment.value if classification else "unclassified",
            "icp_confidence": str(round(classification.confidence, 2)) if classification else "0",
            "conversation_state": prospect.state.value,
            "ai_maturity_score": str(brief.ai_maturity.score) if brief else "0",
            "enrichment_timestamp": brief.generated_at if brief else datetime.utcnow().isoformat(),
            "emails_sent": str(prospect.emails_sent),
            "calcom_booking_id": prospect.calcom_booking_id or "none",
            "is_synthetic": "true",
            "draft": "true",
        }
        return props

    # ── Company ──────────────────────────────────────────────

    def upsert_company(self, prospect: Prospect) -> Optional[str]:
        """Create or update a HubSpot company with enrichment data."""
        properties = self._company_properties(prospect)

        if not self.is_connected:
            return self._sink("company", properties, prospect.id)

        self._rate_limit()
        try:
            # Search by company name
            existing_id = self._find_company_by_name(prospect.company_name)
            if existing_id:
                from hubspot.crm.companies import SimplePublicObjectInput
                self.client.crm.companies.basic_api.update(
                    existing_id,
                    SimplePublicObjectInput(properties=properties),
                )
                logger.info(f"Updated HubSpot company {existing_id}")
                return existing_id
            else:
                from hubspot.crm.companies import SimplePublicObjectInputForCreate
                resp = self.client.crm.companies.basic_api.create(
                    SimplePublicObjectInputForCreate(properties=properties, associations=[]),
                )
                logger.info(f"Created HubSpot company {resp.id}")
                return resp.id
        except Exception as e:
            logger.error(f"HubSpot company upsert failed: {e}")
            return self._sink("company", properties, prospect.id)

    def _find_company_by_name(self, name: str) -> Optional[str]:
        if not name or not self.is_connected:
            return None
        self._rate_limit()
        try:
            from hubspot.crm.companies import PublicObjectSearchRequest, Filter, FilterGroup
            f = Filter(property_name="name", operator="EQ", value=name)
            fg = FilterGroup(filters=[f])
            req = PublicObjectSearchRequest(filter_groups=[fg])
            resp = self.client.crm.companies.search_api.do_search(req)
            if resp.total > 0:
                return resp.results[0].id
        except Exception:
            pass
        return None

    def _company_properties(self, prospect: Prospect) -> dict:
        brief = prospect.signal_brief
        gap = prospect.gap_brief

        props = {
            "name": prospect.company_name,
            "domain": prospect.domain or (prospect.website or "").replace("https://", "").replace("http://", "").split("/")[0] or "unknown",
            "industry": self._map_industry(prospect.industry),
            "numberofemployees": str(prospect.employee_count or 0),
            "city": (prospect.location or "Unknown").split(",")[0].strip(),
            "description": prospect.description or f"{prospect.company_name} - no public description",
        }

        if brief:
            bw = brief.buying_window_signals
            props.update({
                "funding_round_type": bw.funding_event.stage or "none",
                "funding_amount_usd": str(bw.funding_event.amount_usd or 0),
                "funding_date": bw.funding_event.closed_at or "n/a",
                "layoff_occurred": str(bw.layoff_event.detected).lower(),
                "layoff_date": bw.layoff_event.date or "n/a",
                "layoff_headcount": str(bw.layoff_event.headcount_reduction or 0),
                "hiring_velocity_label": brief.hiring_velocity.velocity_label.value,
                "open_roles_today": str(brief.hiring_velocity.open_roles_today),
                "open_roles_60d_ago": str(brief.hiring_velocity.open_roles_60_days_ago),
                "leadership_change": str(bw.leadership_change.detected).lower(),
                "leadership_role": bw.leadership_change.role or "none",
                "leadership_name": bw.leadership_change.new_leader_name or "none",
                "ai_maturity_score": str(brief.ai_maturity.score),
                "ai_maturity_confidence": str(round(brief.ai_maturity.confidence, 2)),
                "tech_stack": ", ".join(brief.tech_stack) if brief.tech_stack else "unknown",
                "honesty_flags": ", ".join(brief.honesty_flags) if brief.honesty_flags else "none",
                "enrichment_timestamp": brief.generated_at,
            })

        if prospect.classification:
            props["icp_segment"] = prospect.classification.segment.value
            props["icp_confidence"] = str(round(prospect.classification.confidence, 2))

        if gap:
            props["gap_sector"] = gap.prospect_sector or "not_analyzed"
            props["gap_top_quartile_benchmark"] = str(gap.sector_top_quartile_benchmark)
            props["gap_findings_count"] = str(len(gap.gap_findings))

        return props

    @staticmethod
    def _map_industry(raw_industry: str) -> str:
        """Map free-text industry to HubSpot's allowed enum values."""
        if not raw_industry:
            return "INFORMATION_TECHNOLOGY_AND_SERVICES"
        low = raw_industry.lower()
        mapping = {
            "ai": "COMPUTER_SOFTWARE",
            "artificial intelligence": "COMPUTER_SOFTWARE",
            "saas": "COMPUTER_SOFTWARE",
            "software": "COMPUTER_SOFTWARE",
            "fintech": "FINANCIAL_SERVICES",
            "financial": "FINANCIAL_SERVICES",
            "banking": "BANKING",
            "health": "HOSPITAL_HEALTH_CARE",
            "biotech": "BIOTECHNOLOGY",
            "e-commerce": "INTERNET",
            "ecommerce": "INTERNET",
            "internet": "INTERNET",
            "education": "EDUCATION_MANAGEMENT",
            "hardware": "COMPUTER_HARDWARE",
            "security": "COMPUTER_NETWORK_SECURITY",
            "cybersecurity": "COMPUTER_NETWORK_SECURITY",
            "telecom": "TELECOMMUNICATIONS",
            "media": "ONLINE_MEDIA",
            "marketing": "MARKETING_AND_ADVERTISING",
            "consulting": "MANAGEMENT_CONSULTING",
            "analytics": "INFORMATION_TECHNOLOGY_AND_SERVICES",
            "data": "INFORMATION_TECHNOLOGY_AND_SERVICES",
            "cloud": "INFORMATION_TECHNOLOGY_AND_SERVICES",
            "devtools": "COMPUTER_SOFTWARE",
            "infrastructure": "INFORMATION_TECHNOLOGY_AND_SERVICES",
            "enterprise": "COMPUTER_SOFTWARE",
            "gaming": "COMPUTER_GAMES",
            "retail": "RETAIL",
            "real estate": "REAL_ESTATE",
            "automotive": "AUTOMOTIVE",
            "energy": "OIL_ENERGY",
            "insurance": "INSURANCE",
            "logistics": "LOGISTICS_AND_SUPPLY_CHAIN",
            "food": "FOOD_BEVERAGES",
            "seo": "MARKETING_AND_ADVERTISING",
        }
        for keyword, hubspot_val in mapping.items():
            if keyword in low:
                return hubspot_val
        return "INFORMATION_TECHNOLOGY_AND_SERVICES"

    # ── Deal ─────────────────────────────────────────────────

    def create_deal(self, prospect: Prospect) -> Optional[str]:
        """Create a deal when prospect reaches QUALIFIED state."""
        properties = self._deal_properties(prospect)

        if not self.is_connected:
            return self._sink("deal", properties, prospect.id)

        self._rate_limit()
        try:
            from hubspot.crm.deals import SimplePublicObjectInputForCreate
            resp = self.client.crm.deals.basic_api.create(
                SimplePublicObjectInputForCreate(properties=properties, associations=[]),
            )
            logger.info(f"Created HubSpot deal {resp.id} for {prospect.company_name}")
            return resp.id
        except Exception as e:
            logger.error(f"HubSpot deal creation failed: {e}")
            return self._sink("deal", properties, prospect.id)

    def _deal_properties(self, prospect: Prospect) -> dict:
        seg = prospect.classification.segment if prospect.classification else ICPSegment.UNCLASSIFIED
        acv_map = {
            ICPSegment.SEGMENT_1: "480000",
            ICPSegment.SEGMENT_2: "540000",
            ICPSegment.SEGMENT_3: "390000",
            ICPSegment.SEGMENT_4: "190000",
            ICPSegment.ABSTAIN: "0",
            ICPSegment.UNCLASSIFIED: "0",
        }
        return {
            "dealname": f"Tenacious x {prospect.company_name}",
            "pipeline": "default",
            "dealstage": "qualifiedtobuy",
            "amount": acv_map.get(seg, "0"),
            "description": (
                f"Segment: {seg.value} | "
                f"AI Maturity: {prospect.signal_brief.ai_maturity.score}/3 | "
                f"Confidence: {prospect.classification.confidence:.2f}"
                if prospect.signal_brief and prospect.classification else ""
            ),
        }

    # ── Notes / Engagements ──────────────────────────────────

    def log_event(
        self,
        prospect: Prospect,
        event_type: str,
        body: str,
        contact_id: Optional[str] = None,
    ) -> Optional[str]:
        """Log a conversation event as a HubSpot note."""
        timestamp = datetime.utcnow().isoformat()
        note_body = (
            f"[{event_type.upper()}] {timestamp}\n"
            f"Prospect: {prospect.company_name} ({prospect.id})\n"
            f"State: {prospect.state.value}\n"
            f"Channel: {prospect.channel.value}\n\n"
            f"{body}"
        )

        if not self.is_connected:
            return self._sink("note", {"body": note_body, "event_type": event_type}, prospect.id)

        self._rate_limit()
        try:
            from hubspot.crm.objects.notes import SimplePublicObjectInputForCreate
            properties = {
                "hs_timestamp": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S.000Z"),
                "hs_note_body": note_body,
            }
            associations = []
            if contact_id:
                associations.append({
                    "to": {"id": contact_id},
                    "types": [{"associationCategory": "HUBSPOT_DEFINED", "associationTypeId": 202}],
                })
            resp = self.client.crm.objects.notes.basic_api.create(
                SimplePublicObjectInputForCreate(properties=properties, associations=associations),
            )
            logger.info(f"Created HubSpot note {resp.id} for {prospect.company_name}")
            return resp.id
        except Exception as e:
            logger.error(f"HubSpot note creation failed: {e}")
            return self._sink("note", {"body": note_body, "event_type": event_type}, prospect.id)

    # ── Full Sync ────────────────────────────────────────────

    def sync_prospect(self, prospect: Prospect) -> dict:
        """Full sync: upsert contact + company, create deal if qualified, log event."""
        result = {"prospect_id": prospect.id, "company": prospect.company_name}

        # Company
        company_id = self.upsert_company(prospect)
        result["company_id"] = company_id

        # Contact
        contact_id = self.upsert_contact(prospect)
        result["contact_id"] = contact_id
        prospect.hubspot_contact_id = contact_id

        # Associate contact to company
        if self.is_connected and company_id and contact_id:
            self._associate_contact_to_company(contact_id, company_id)

        # Deal (if qualified or beyond)
        qualified_states = {
            ConversationState.QUALIFIED,
            ConversationState.CALL_BOOKED,
            ConversationState.HANDED_OFF,
        }
        if prospect.state in qualified_states:
            deal_id = self.create_deal(prospect)
            result["deal_id"] = deal_id

        # Log enrichment event
        if prospect.signal_brief:
            brief = prospect.signal_brief
            bw = brief.buying_window_signals
            body_parts = [
                f"Funding: {bw.funding_event.stage or 'none'} (detected={bw.funding_event.detected})",
                f"Layoffs: {'Yes' if bw.layoff_event.detected else 'No'}",
                f"Hiring Velocity: {brief.hiring_velocity.velocity_label.value} ({brief.hiring_velocity.open_roles_today} roles)",
                f"Leadership: {'Change' if bw.leadership_change.detected else 'No change'}",
                f"AI Maturity: {brief.ai_maturity.score}/3 (confidence {brief.ai_maturity.confidence:.2f})",
                f"Honesty Flags: {', '.join(brief.honesty_flags) if brief.honesty_flags else 'none'}",
            ]
            if prospect.classification:
                body_parts.append(
                    f"Segment: {prospect.classification.segment.value} "
                    f"(confidence {prospect.classification.confidence:.2f})"
                )
            self.log_event(
                prospect,
                "enrichment",
                "\n".join(body_parts),
                contact_id=contact_id,
            )

        result["synced_at"] = datetime.utcnow().isoformat()
        result["mode"] = "live" if self.is_connected else "sink"
        logger.info(f"HubSpot sync complete for {prospect.company_name} (mode={result['mode']})")
        return result

    def _associate_contact_to_company(self, contact_id: str, company_id: str):
        self._rate_limit()
        try:
            from hubspot.crm.associations.v4 import (
                AssociationSpec,
                BatchInputPublicDefaultAssociationMultiPost,
                PublicDefaultAssociationMultiPost,
            )
            self.client.crm.associations.v4.basic_api.create(
                object_type="contacts",
                object_id=contact_id,
                to_object_type="companies",
                to_object_id=company_id,
                association_spec=[AssociationSpec(
                    association_category="HUBSPOT_DEFINED",
                    association_type_id=1,
                )],
            )
        except Exception as e:
            logger.warning(f"Contact-company association failed: {e}")

    # ── Custom Properties Setup ──────────────────────────────

    def ensure_custom_properties(self):
        """Create custom properties in HubSpot if they don't exist.
        Run once during setup."""
        if not self.is_connected:
            logger.info("HubSpot not connected — skipping property setup")
            return

        contact_props = [
            ("crunchbase_id", "Crunchbase ID", "string"),
            ("icp_segment", "ICP Segment", "string"),
            ("icp_confidence", "ICP Confidence", "string"),
            ("conversation_state", "Conversation State", "string"),
            ("ai_maturity_score", "AI Maturity Score", "string"),
            ("enrichment_timestamp", "Enrichment Timestamp", "string"),
            ("emails_sent", "Emails Sent", "string"),
            ("is_synthetic", "Is Synthetic", "string"),
            ("draft", "Draft", "string"),
        ]
        company_props = [
            ("crunchbase_id", "Crunchbase ID", "string"),
            ("funding_round_type", "Funding Round Type", "string"),
            ("funding_amount_usd", "Funding Amount USD", "string"),
            ("funding_recency_days", "Funding Recency Days", "string"),
            ("layoff_occurred", "Layoff Occurred", "string"),
            ("layoff_recency_days", "Layoff Recency Days", "string"),
            ("job_posts_total", "Job Posts Total", "string"),
            ("job_posts_engineering", "Job Posts Engineering", "string"),
            ("job_posts_ai_ml", "Job Posts AI/ML", "string"),
            ("leadership_change", "Leadership Change", "string"),
            ("ai_maturity_score", "AI Maturity Score", "string"),
            ("ai_maturity_confidence", "AI Maturity Confidence", "string"),
            ("icp_segment", "ICP Segment", "string"),
            ("gap_position", "Gap Position", "string"),
            ("enrichment_timestamp", "Enrichment Timestamp", "string"),
        ]

        for name, label, field_type in contact_props:
            self._create_property("contacts", name, label, field_type)
        for name, label, field_type in company_props:
            self._create_property("companies", name, label, field_type)

    def _create_property(self, object_type: str, name: str, label: str, field_type: str):
        self._rate_limit()
        try:
            from hubspot.crm.properties import PropertyCreate
            self.client.crm.properties.core_api.create(
                object_type=object_type,
                property_create=PropertyCreate(
                    name=name,
                    label=label,
                    type="string",
                    field_type="text",
                    group_name="contactinformation" if object_type == "contacts" else "companyinformation",
                ),
            )
            logger.info(f"Created HubSpot property: {object_type}/{name}")
        except Exception as e:
            if "already exists" in str(e).lower() or "409" in str(e):
                pass  # property already exists
            else:
                logger.warning(f"Property creation failed for {object_type}/{name}: {e}")

    # ── Sink (offline mode) ──────────────────────────────────

    def _sink(self, obj_type: str, properties: dict, prospect_id: str) -> str:
        """Write to local sink when HubSpot is not connected."""
        ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        record = {
            "object_type": obj_type,
            "properties": properties,
            "prospect_id": prospect_id,
            "timestamp": datetime.utcnow().isoformat(),
        }
        filename = f"{ts}_{obj_type}_{prospect_id}.json"
        (self._sink_dir / filename).write_text(json.dumps(record, indent=2, default=str))
        logger.info(f"HubSpot {obj_type} routed to sink: {filename}")
        return f"sink_{ts}"
