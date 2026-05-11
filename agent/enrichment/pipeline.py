"""Enrichment pipeline — orchestrates all signal collection for a prospect."""

from __future__ import annotations
import json
import logging
from datetime import datetime
from pathlib import Path

from agent.models import (
    HiringSignalBrief, Prospect, HiringVelocity, VelocityLabel,
    BuyingWindowSignals, FundingEvent, LayoffEvent, LeadershipChange,
    BenchToBriefMatch, DataSourceCheck, ConversationState,
)
from agent.enrichment.crunchbase import CrunchbaseEnricher
from agent.enrichment.layoffs import LayoffsChecker
from agent.enrichment.job_posts import JobPostScraper
from agent.enrichment.leadership import LeadershipDetector
from agent.enrichment.scrapling_enricher import ScraplingEnricher
from agent.enrichment.ai_maturity import score_ai_maturity
from agent.enrichment.gap_analysis import analyze_competitor_gap
from agent.observability.tracer import tracer
from config.settings import settings

logger = logging.getLogger(__name__)


class EnrichmentPipeline:
    def __init__(self):
        self.crunchbase = CrunchbaseEnricher()
        self.layoffs = LayoffsChecker()
        self.job_scraper = JobPostScraper()
        self.leadership_detector = LeadershipDetector()
        self.scrapling_enricher = ScraplingEnricher()
        self._loaded = False
        self._bench = None

    def load_data(self):
        if self._loaded:
            return
        self.crunchbase.load()
        self.layoffs.load()
        bench_path = Path(settings.seed_data_path) / "bench_summary.json"
        if bench_path.exists():
            self._bench = json.loads(bench_path.read_text())
        self._loaded = True

    def enrich(self, prospect: Prospect, skip_llm: bool = False) -> Prospect:
        """Run full enrichment pipeline on a prospect."""
        self.load_data()
        company = prospect.company_name
        logger.info(f"Enriching: {company}")

        data_sources: list[DataSourceCheck] = []

        # 1. Firmographics
        with tracer.span("crunchbase_firmographics", prospect_id=prospect.id):
            firmographics = self.crunchbase.get_firmographics(company)
        data_sources.append(DataSourceCheck(
            source="crunchbase_odm",
            status="success" if firmographics else "no_data",
            fetched_at=datetime.utcnow().isoformat() + "Z",
        ))
        if firmographics:
            prospect.industry = prospect.industry or firmographics.get("industry")
            prospect.employee_count = prospect.employee_count or firmographics.get("employee_count")
            prospect.location = prospect.location or firmographics.get("location")
            prospect.description = prospect.description or firmographics.get("description")
            prospect.website = prospect.website or firmographics.get("website")
            prospect.domain = prospect.domain or firmographics.get("website", "").replace("https://", "").replace("http://", "").split("/")[0]

        # 2. Funding signal
        with tracer.span("funding_signal", prospect_id=prospect.id):
            funding_raw = self.crunchbase.get_funding_signal(company)
        funding_event = FundingEvent(
            detected=funding_raw.strength.value != "absent",
            stage=funding_raw.round_type,
            amount_usd=int(funding_raw.amount_usd) if funding_raw.amount_usd else None,
            closed_at=funding_raw.date,
            source_url=funding_raw.source or None,
        )

        # 3. Layoff signal
        with tracer.span("layoff_signal", prospect_id=prospect.id):
            layoff_raw = self.layoffs.check(company)
        data_sources.append(DataSourceCheck(
            source="layoffs_fyi",
            status="success",
            fetched_at=datetime.utcnow().isoformat() + "Z",
        ))
        layoff_event = LayoffEvent(
            detected=layoff_raw.occurred,
            date=layoff_raw.date,
            headcount_reduction=layoff_raw.headcount,
            percentage_cut=layoff_raw.percentage,
            source_url=layoff_raw.source or None,
        )

        # 4. Job post signal
        with tracer.span("job_post_scrape", prospect_id=prospect.id):
            linkedin_url = getattr(prospect, 'linkedin_url', '') or ''
            job_signal = self._get_job_signal(company, prospect.website, linkedin_url)
        data_sources.append(DataSourceCheck(
            source="job_posts_snapshot",
            status="success" if job_signal.total_open_roles > 0 else "no_data",
            fetched_at=datetime.utcnow().isoformat() + "Z",
        ))

        # Build hiring velocity
        velocity_label, velocity_pct = self._compute_velocity_label(job_signal, company)
        hiring_velocity = HiringVelocity(
            open_roles_today=job_signal.total_open_roles,
            open_roles_60_days_ago=max(0, int(job_signal.total_open_roles / (1 + velocity_pct / 100))) if velocity_pct else 0,
            velocity_label=velocity_label,
            signal_confidence=0.7 if job_signal.total_open_roles > 0 else 0.0,
            sources=["job_posts_snapshot"],
        )

        # 5. Leadership change
        with tracer.span("leadership_detection", prospect_id=prospect.id):
            cb_record = self.crunchbase.find_company(company)
            # Try Scrapling-based detection first (faster, includes LinkedIn)
            linkedin_url = getattr(prospect, 'linkedin_url', '') or ''
            leadership_raw = self.scrapling_enricher.scrape_leadership(
                company_name=company,
                website=prospect.website or "",
                linkedin_url=linkedin_url,
            )
            # Fallback to original detector if Scrapling found nothing
            if leadership_raw.strength == SignalStrength.ABSENT:
                leadership_raw = self.leadership_detector.detect(
                    company_name=company,
                    crunchbase_record=cb_record,
                    website=prospect.website or "",
                )
        data_sources.append(DataSourceCheck(
            source="leadership_detection",
            status="success" if leadership_raw.new_leader else "no_data",
            fetched_at=datetime.utcnow().isoformat() + "Z",
        ))
        leadership_change = LeadershipChange(
            detected=leadership_raw.new_leader,
            role=leadership_raw.title,
            new_leader_name=leadership_raw.name,
            started_at=leadership_raw.appointed_date,
            source_url=leadership_raw.source or None,
        )

        buying_window = BuyingWindowSignals(
            funding_event=funding_event,
            layoff_event=layoff_event,
            leadership_change=leadership_change,
        )

        # Bench-to-brief match
        bench_match = self._compute_bench_match(job_signal.top_stacks)

        # Honesty flags
        honesty_flags = []
        if job_signal.total_open_roles < 5:
            honesty_flags.append("weak_hiring_velocity_signal")
        if not job_signal.top_stacks:
            honesty_flags.append("tech_stack_inferred_not_confirmed")
        if not bench_match.bench_available and bench_match.required_stacks:
            honesty_flags.append("bench_gap_detected")
        if layoff_event.detected and funding_event.detected:
            honesty_flags.append("layoff_overrides_funding")

        # Build brief (without AI maturity yet)
        brief = HiringSignalBrief(
            prospect_domain=prospect.domain,
            prospect_name=company,
            generated_at=datetime.utcnow().isoformat() + "Z",
            hiring_velocity=hiring_velocity,
            buying_window_signals=buying_window,
            tech_stack=job_signal.top_stacks,
            bench_to_brief_match=bench_match,
            data_sources_checked=data_sources,
            honesty_flags=honesty_flags,
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
            if brief.ai_maturity.confidence < 0.5:
                honesty_flags.append("weak_ai_maturity_signal")
                brief.honesty_flags = honesty_flags

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

        tracer.trace_outbound(
            action="enrichment_complete",
            prospect_id=prospect.id,
            channel="pipeline",
            content_preview=f"funding={funding_event.detected}, layoff={layoff_event.detected}, ai_maturity={brief.ai_maturity.score}",
            metadata={"company": company, "segment": prospect.classification.segment.value if prospect.classification else "n/a"},
        )
        tracer.flush()

        logger.info(f"Enriched {company}: funding={funding_event.detected}, layoff={layoff_event.detected}, ai_maturity={brief.ai_maturity.score}")
        return prospect

    def _compute_velocity_label(self, job_signal, company_name: str = "") -> tuple[VelocityLabel, float]:
        """Compute 60-day hiring velocity delta.
        
        Compares current open roles against a 60-day-old snapshot.
        If no historical snapshot exists, stores current as baseline.
        Returns (velocity_label, velocity_pct_change).
        """
        history_dir = Path("data/job_posts/history")
        history_dir.mkdir(parents=True, exist_ok=True)
        safe_name = company_name.lower().replace(" ", "_") if company_name else "unknown"
        history_path = history_dir / f"{safe_name}_60d.json"

        current_roles = job_signal.total_open_roles
        now = datetime.utcnow()

        # Load or create historical baseline
        roles_60d_ago = 0
        if history_path.exists():
            try:
                hist = json.loads(history_path.read_text())
                roles_60d_ago = hist.get("open_roles", 0)
                snapshot_date = hist.get("snapshot_date", "")
                # Check if snapshot is roughly 60 days old
                if snapshot_date:
                    snap_dt = datetime.fromisoformat(snapshot_date)
                    age_days = (now - snap_dt).days
                    if age_days < 30:
                        # Snapshot too recent, use it as-is
                        roles_60d_ago = hist.get("open_roles", 0)
            except (json.JSONDecodeError, ValueError):
                roles_60d_ago = 0

        # Store current snapshot for future 60-day comparison
        history_path.write_text(json.dumps({
            "company": company_name,
            "open_roles": current_roles,
            "snapshot_date": now.isoformat(),
        }, indent=2))

        # Compute velocity
        if not job_signal.velocity_60d and roles_60d_ago == 0 and current_roles == 0:
            return VelocityLabel.INSUFFICIENT_SIGNAL, 0.0

        if job_signal.velocity_60d is not None:
            v = job_signal.velocity_60d
        elif roles_60d_ago > 0:
            v = ((current_roles - roles_60d_ago) / roles_60d_ago) * 100
        elif current_roles > 0:
            v = 100.0  # new roles from zero baseline
        else:
            return VelocityLabel.INSUFFICIENT_SIGNAL, 0.0

        if v >= 200:
            return VelocityLabel.TRIPLED_OR_MORE, v
        if v >= 100:
            return VelocityLabel.DOUBLED, v
        if v > 10:
            return VelocityLabel.INCREASED_MODESTLY, v
        if v >= -10:
            return VelocityLabel.FLAT, v
        return VelocityLabel.DECLINED, v

    def _compute_bench_match(self, tech_stack: list[str]) -> BenchToBriefMatch:
        if not self._bench or not tech_stack:
            return BenchToBriefMatch()
        bench_stacks = set(self._bench.get("stacks", {}).keys())
        stack_lower = [s.lower().replace(" ", "_") for s in tech_stack]
        required = []
        gaps = []
        for s in stack_lower:
            for bs in bench_stacks:
                if bs in s or s in bs:
                    required.append(bs)
                    break
            else:
                gaps.append(s)
        return BenchToBriefMatch(
            required_stacks=required or stack_lower,
            bench_available=len(gaps) == 0 and len(required) > 0,
            gaps=gaps,
        )

    def _find_peers(self, prospect: Prospect) -> list[dict]:
        if not prospect.industry:
            return []
        return self.crunchbase.get_peers_by_industry(
            prospect.industry, exclude_name=prospect.company_name, limit=10
        )

    def _get_job_signal(self, company: str, website: str = "", linkedin_url: str = ""):
        from agent.models import SignalStrength
        from collections import namedtuple
        DummySignal = namedtuple("DummySignal", ["total_open_roles", "engineering_roles", "ai_ml_roles", "velocity_60d", "top_stacks", "strength", "source"])

        if not website and not linkedin_url:
            return DummySignal(0, 0, 0, None, [], SignalStrength.ABSENT, "no_website")

        # Try Scrapling enricher first (faster, handles LinkedIn, adaptive selectors)
        try:
            signal = self.scrapling_enricher.scrape_jobs(company, website=website, linkedin_url=linkedin_url)
            if signal.total_open_roles > 0:
                return signal
        except Exception as e:
            logger.debug(f"Scrapling scrape failed for {company}: {e}")

        # Fallback to Playwright-based scraper for JS-heavy pages
        if website:
            try:
                return self.job_scraper.scrape(company, website)
            except Exception as e:
                logger.warning(f"Job scrape failed for {company}: {e}")

        return DummySignal(0, 0, 0, None, [], SignalStrength.ABSENT, "scrape_failed")

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
