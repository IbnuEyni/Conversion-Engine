"""Enrichment pipeline — orchestrates all signal collection for a prospect."""

from __future__ import annotations
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

from agent.models import (
    HiringSignalBrief, Prospect, JobPostSignal, SignalStrength,
    ConversationState,
)
from agent.enrichment.crunchbase import CrunchbaseEnricher
from agent.enrichment.layoffs import LayoffsChecker
from agent.enrichment.job_posts import JobPostScraper
from agent.enrichment.leadership import LeadershipDetector
from agent.enrichment.ai_maturity import score_ai_maturity
from agent.enrichment.gap_analysis import analyze_competitor_gap
from agent.observability.tracer import tracer

logger = logging.getLogger(__name__)


class EnrichmentPipeline:
    def __init__(self):
        self.crunchbase = CrunchbaseEnricher()
        self.layoffs = LayoffsChecker()
        self.job_scraper = JobPostScraper()
        self.leadership_detector = LeadershipDetector()
        self._loaded = False

    def load_data(self):
        if self._loaded:
            return
        self.crunchbase.load()
        self.layoffs.load()
        self._loaded = True

    def enrich(self, prospect: Prospect, skip_llm: bool = False) -> Prospect:
        """Run full enrichment pipeline on a prospect."""
        self.load_data()
        company = prospect.company_name
        logger.info(f"Enriching: {company}")

        # 1. Firmographics
        with tracer.span("crunchbase_firmographics", prospect_id=prospect.id):
            firmographics = self.crunchbase.get_firmographics(company)
        if firmographics:
            prospect.crunchbase_id = firmographics.get("crunchbase_id")
            prospect.industry = prospect.industry or firmographics.get("industry")
            prospect.employee_count = prospect.employee_count or firmographics.get("employee_count")
            prospect.location = prospect.location or firmographics.get("location")
            prospect.description = prospect.description or firmographics.get("description")
            prospect.website = prospect.website or firmographics.get("website")

        # 2. Funding signal
        with tracer.span("funding_signal", prospect_id=prospect.id):
            funding = self.crunchbase.get_funding_signal(company)

        # 3. Layoff signal
        with tracer.span("layoff_signal", prospect_id=prospect.id):
            layoff = self.layoffs.check(company)

        # 4. Job post signal
        with tracer.span("job_post_scrape", prospect_id=prospect.id):
            job_signal = self._get_job_signal(company, prospect.website)

        # 5. Leadership change
        with tracer.span("leadership_detection", prospect_id=prospect.id):
            cb_record = self.crunchbase.find_company(company)
            leadership = self.leadership_detector.detect(
                company_name=company,
                crunchbase_record=cb_record,
                website=prospect.website or "",
            )

        # Build brief
        brief = HiringSignalBrief(
            company_name=company,
            crunchbase_id=prospect.crunchbase_id,
            funding=funding,
            job_posts=job_signal,
            layoffs=layoff,
            leadership=leadership,
            tech_stack=job_signal.top_stacks,
            enriched_at=datetime.utcnow(),
        )

        if not skip_llm:
            from agent.llm_client import get_llm

            # 6. AI maturity
            get_llm("dev").set_context("ai_maturity", prospect.id)
            brief.ai_maturity = score_ai_maturity(
                company_name=company,
                industry=prospect.industry or "",
                description=prospect.description or "",
                employee_count=prospect.employee_count or 0,
                job_signal=job_signal,
                tech_stack=brief.tech_stack,
            )

            # 7. Competitor gap
            get_llm("dev").set_context("gap_analysis", prospect.id)
            peers = self._find_peers(prospect)
            gap_brief = analyze_competitor_gap(
                prospect_brief=brief,
                peer_companies=peers,
                industry=prospect.industry or "",
                description=prospect.description or "",
            )
            prospect.gap_brief = gap_brief

        prospect.signal_brief = brief
        prospect.state = ConversationState.ENRICHED
        prospect.updated_at = datetime.utcnow()

        # Trace the full pipeline result
        tracer.trace_outbound(
            action="enrichment_complete",
            prospect_id=prospect.id,
            channel="pipeline",
            content_preview=f"funding={funding.strength.value}, layoff={layoff.occurred}, ai_maturity={brief.ai_maturity.score}",
            metadata={"company": company, "segment": prospect.classification.segment.value if prospect.classification else "n/a"},
        )
        tracer.flush()

        logger.info(
            f"Enriched {company}: funding={funding.strength.value}, "
            f"layoff={layoff.occurred}, ai_maturity={brief.ai_maturity.score}"
        )
        return prospect

    def _find_peers(self, prospect: Prospect) -> list[dict]:
        """Find peer companies in same sector from Crunchbase data."""
        if not prospect.industry:
            return []
        return self.crunchbase.get_peers_by_industry(
            prospect.industry, exclude_name=prospect.company_name, limit=10
        )

    def _get_job_signal(self, company: str, website: str = "") -> JobPostSignal:
        """Scrape public career page for job post data."""
        if not website:
            return JobPostSignal(strength=SignalStrength.ABSENT, source="no_website")
        try:
            return self.job_scraper.scrape(company, website)
        except Exception as e:
            logger.warning(f"Job scrape failed for {company}: {e}")
            return JobPostSignal(strength=SignalStrength.ABSENT, source=f"error: {e}")

    def save_brief(self, prospect: Prospect, output_dir: str = "data/briefs"):
        """Save hiring signal brief and gap brief as JSON."""
        out = Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)
        safe_name = prospect.company_name.lower().replace(" ", "_")

        if prospect.signal_brief:
            (out / f"{safe_name}_hiring_signal_brief.json").write_text(
                prospect.signal_brief.model_dump_json(indent=2)
            )
        if prospect.gap_brief:
            (out / f"{safe_name}_competitor_gap_brief.json").write_text(
                prospect.gap_brief.model_dump_json(indent=2)
            )


if __name__ == "__main__":
    import argparse
    logging.basicConfig(level=logging.INFO)

    parser = argparse.ArgumentParser()
    parser.add_argument("--company", required=True)
    parser.add_argument("--skip-llm", action="store_true")
    args = parser.parse_args()

    pipeline = EnrichmentPipeline()
    prospect = Prospect(company_name=args.company)
    prospect = pipeline.enrich(prospect, skip_llm=args.skip_llm)
    pipeline.save_brief(prospect)

    print(json.dumps(prospect.model_dump(mode="json"), indent=2, default=str))
