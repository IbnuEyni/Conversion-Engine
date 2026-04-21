"""End-to-end pipeline test — validates all components work together.

Run: python scripts/test_pipeline.py [--with-llm]
Without --with-llm: tests data loading, classification, email sink (no API keys needed)
With --with-llm: tests full pipeline including AI maturity scoring and email composition
"""

import argparse
import json
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from agent.models import Prospect, SignalStrength, FundingSignal, LayoffSignal, JobPostSignal, LeadershipSignal, AIMaturityScore, HiringSignalBrief
from agent.enrichment.crunchbase import CrunchbaseEnricher
from agent.enrichment.layoffs import LayoffsChecker
from agent.enrichment.job_posts import JobPostScraper
from agent.enrichment.leadership import LeadershipDetector
from agent.enrichment.pipeline import EnrichmentPipeline
from agent.qualification.classifier import classify_prospect
from agent.outreach.email_sender import EmailSender
from agent.outreach.sms_handler import SMSHandler


def test_models():
    print("\n--- Test: Data Models ---")
    p = Prospect(
        id="test-001",
        company_name="TestCorp",
        contact_name="Jane Doe",
        contact_email="jane@testcorp.com",
        contact_title="CTO",
        industry="SaaS",
        employee_count=50,
    )
    assert p.state.value == "new"
    assert p.is_synthetic
    print(f"  ✅ Prospect model: {p.company_name}, state={p.state.value}")


def test_crunchbase():
    print("\n--- Test: Crunchbase Enricher ---")
    cb = CrunchbaseEnricher()
    cb.load()
    print(f"  Loaded {len(cb._data)} records")
    if cb._data:
        first = list(cb._index.keys())[0]
        firm = cb.get_firmographics(first)
        print(f"  ✅ Firmographics for '{first}': {json.dumps({k: str(v)[:50] for k, v in firm.items()})}")
        funding = cb.get_funding_signal(first)
        print(f"  ✅ Funding signal: {funding.strength.value}")
    else:
        print("  ⚠️  No Crunchbase data — run scripts/setup.sh first")


def test_layoffs():
    print("\n--- Test: Layoffs Checker ---")
    lc = LayoffsChecker()
    lc.load()
    print(f"  Loaded {len(lc._records)} records")
    if lc._records:
        first = list(lc._index.keys())[0]
        signal = lc.check(first)
        print(f"  ✅ Layoff signal for '{first}': occurred={signal.occurred}, strength={signal.strength.value}")
    else:
        print("  ⚠️  No layoffs data — run scripts/setup.sh first")


def test_classifier():
    print("\n--- Test: ICP Classifier ---")

    # Segment 1: Recently funded startup
    p1 = Prospect(id="seg1", company_name="FreshFund Inc", employee_count=40)
    p1.signal_brief = HiringSignalBrief(
        company_name="FreshFund Inc",
        funding=FundingSignal(round_type="series_a", amount_usd=12_000_000, recency_days=60, strength=SignalStrength.STRONG),
        job_posts=JobPostSignal(engineering_roles=8, strength=SignalStrength.MODERATE),
        ai_maturity=AIMaturityScore(score=1, confidence=0.5),
    )
    c1 = classify_prospect(p1)
    print(f"  ✅ Segment 1 test: {c1.segment.value} (confidence={c1.confidence:.2f}) — {c1.reasoning[:80]}")
    assert c1.segment.value == "recently_funded_startup", f"Expected recently_funded_startup, got {c1.segment.value}"

    # Segment 2: Post-layoff restructuring
    p2 = Prospect(id="seg2", company_name="BigCo", employee_count=500)
    p2.signal_brief = HiringSignalBrief(
        company_name="BigCo",
        funding=FundingSignal(round_type="series_a", amount_usd=20_000_000, recency_days=30, strength=SignalStrength.STRONG),
        layoffs=LayoffSignal(occurred=True, recency_days=45, headcount=100, strength=SignalStrength.STRONG),
        job_posts=JobPostSignal(engineering_roles=5, strength=SignalStrength.MODERATE),
        ai_maturity=AIMaturityScore(score=1, confidence=0.4),
    )
    c2 = classify_prospect(p2)
    print(f"  ✅ Segment 2 test: {c2.segment.value} (confidence={c2.confidence:.2f}) — {c2.reasoning[:80]}")
    assert c2.segment.value == "mid_market_restructuring", f"Expected restructuring, got {c2.segment.value}"

    # Segment 4 blocked: AI maturity too low
    p4 = Prospect(id="seg4-blocked", company_name="LowAI Corp", employee_count=100)
    p4.signal_brief = HiringSignalBrief(
        company_name="LowAI Corp",
        ai_maturity=AIMaturityScore(score=1, confidence=0.8),
    )
    c4 = classify_prospect(p4)
    print(f"  ✅ Segment 4 block test: {c4.segment.value} (confidence={c4.confidence:.2f})")
    assert c4.segment.value != "capability_gap", "Segment 4 should be blocked for AI maturity < 2"

    # Abstention: low confidence
    p_low = Prospect(id="low-conf", company_name="Ambiguous LLC", employee_count=100)
    p_low.signal_brief = HiringSignalBrief(
        company_name="Ambiguous LLC",
        ai_maturity=AIMaturityScore(score=0, confidence=0.2),
    )
    c_low = classify_prospect(p_low)
    print(f"  ✅ Abstention test: {c_low.segment.value} (confidence={c_low.confidence:.2f})")
    assert c_low.segment.value == "unclassified", "Should abstain on low confidence"


def test_job_scraper():
    print("\n--- Test: Job Post Scraper ---")
    scraper = JobPostScraper()
    # Test with cached data if available, otherwise just verify structure
    signal = scraper._to_signal({
        "roles": [
            {"title": "Senior Backend Engineer", "is_engineering": True, "is_ai_ml": False, "stacks": ["python", "go"]},
            {"title": "ML Engineer", "is_engineering": True, "is_ai_ml": True, "stacks": ["python", "pytorch"]},
            {"title": "Product Manager", "is_engineering": False, "is_ai_ml": False, "stacks": []},
            {"title": "DevOps Engineer", "is_engineering": True, "is_ai_ml": False, "stacks": ["kubernetes", "terraform"]},
        ],
        "career_url": "https://example.com/careers",
    })
    assert signal.total_open_roles == 4
    assert signal.engineering_roles == 3
    assert signal.ai_ml_roles == 1
    assert signal.strength.value == "moderate"
    assert "python" in signal.top_stacks
    print(f"  ✅ Signal parsing: {signal.total_open_roles} roles, {signal.engineering_roles} eng, {signal.ai_ml_roles} ai/ml")
    print(f"     stacks={signal.top_stacks}, strength={signal.strength.value}")


def test_leadership_detector():
    print("\n--- Test: Leadership Detector ---")
    ld = LeadershipDetector()

    # Test with Crunchbase record containing CTO appointment (use recent date)
    from datetime import datetime, timedelta
    recent_date = (datetime.utcnow() - timedelta(days=30)).strftime("%Y-%m-%d")
    signal = ld.detect_from_crunchbase({
        "leadership_hire": f'[{{"key_event_date":"{recent_date}","label":"Acme Corp Appoints New CTO","link":"https://example.com"}}]'
    })
    assert signal.new_leader is True
    assert signal.strength.value == "strong"  # within 90 days
    print(f"  ✅ Recent CTO: new_leader={signal.new_leader}, title={signal.title}, strength={signal.strength.value}")

    # Test with non-engineering leadership
    signal2 = ld.detect_from_crunchbase({
        "leadership_hire": '[{"key_event_date":"2025-01-01","label":"Company Names New CFO"}]'
    })
    assert signal2.new_leader is False
    print(f"  ✅ Non-eng leadership: new_leader={signal2.new_leader}, strength={signal2.strength.value}")

    # Test with empty data
    signal3 = ld.detect_from_crunchbase({"leadership_hire": "[]"})
    assert signal3.strength.value == "absent"
    print(f"  ✅ Empty data: strength={signal3.strength.value}")


def test_email_sink():
    print("\n--- Test: Email Sender (Sink Mode) ---")
    es = EmailSender()
    result = es.send(
        to_email="test@example.com",
        subject="Test outreach",
        body="This is a test email routed to local sink.",
        prospect_id="test-001",
    )
    print(f"  ✅ Email sent to sink: status={result['status']}")
    assert result["status"] == "sink"


def test_sms_handler():
    print("\n--- Test: SMS Handler ---")
    sh = SMSHandler()
    # Test STOP
    result = sh.handle_inbound("+1234567890", "STOP")
    print(f"  ✅ STOP handling: action={result['action']}")
    assert result["action"] == "opt_out"

    # Test normal message
    result = sh.handle_inbound("+1234567890", "Yes, I'm interested")
    print(f"  ✅ Normal message: action={result['action']}")
    assert result["action"] == "route_to_conversation"


def test_full_pipeline(with_llm: bool = False):
    print("\n--- Test: Full Pipeline ---")
    pipeline = EnrichmentPipeline()

    # Use a company from Crunchbase data if available
    pipeline.load_data()
    company = "TestCorp"
    if pipeline.crunchbase._data:
        first_rec = pipeline.crunchbase._data[0]
        company = first_rec.get("name") or first_rec.get("company_name") or "TestCorp"

    prospect = Prospect(
        id="full-test",
        company_name=company,
        contact_name="Test User",
        contact_email="test@example.com",
    )

    prospect = pipeline.enrich(prospect, skip_llm=not with_llm)
    prospect.classification = classify_prospect(prospect)

    print(f"  Company: {prospect.company_name}")
    print(f"  Crunchbase ID: {prospect.crunchbase_id}")
    print(f"  Industry: {prospect.industry}")
    print(f"  Employees: {prospect.employee_count}")
    print(f"  Funding: {prospect.signal_brief.funding.strength.value if prospect.signal_brief else 'N/A'}")
    print(f"  Layoffs: {prospect.signal_brief.layoffs.occurred if prospect.signal_brief else 'N/A'}")
    print(f"  AI Maturity: {prospect.signal_brief.ai_maturity.score if prospect.signal_brief else 'N/A'}")
    print(f"  Segment: {prospect.classification.segment.value}")
    print(f"  Confidence: {prospect.classification.confidence:.2f}")
    print(f"  ✅ Full pipeline complete")

    pipeline.save_brief(prospect)
    print(f"  ✅ Briefs saved to data/briefs/")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--with-llm", action="store_true", help="Include LLM-dependent tests (needs API key)")
    args = parser.parse_args()

    print("=" * 60)
    print("Conversion Engine — Pipeline Test")
    print("=" * 60)

    test_models()
    test_crunchbase()
    test_layoffs()
    test_job_scraper()
    test_leadership_detector()
    test_classifier()
    test_email_sink()
    test_sms_handler()
    test_full_pipeline(with_llm=args.with_llm)

    print("\n" + "=" * 60)
    print("All tests passed ✅")
    print("=" * 60)
