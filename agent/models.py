"""Core data models for the Conversion Engine — aligned with official schemas."""

from __future__ import annotations
from datetime import datetime
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


# --- Enums ---

class ICPSegment(str, Enum):
    SEGMENT_1 = "segment_1_series_a_b"
    SEGMENT_2 = "segment_2_mid_market_restructure"
    SEGMENT_3 = "segment_3_leadership_transition"
    SEGMENT_4 = "segment_4_specialized_capability"
    ABSTAIN = "abstain"
    UNCLASSIFIED = "unclassified"


class ConversationState(str, Enum):
    NEW = "new"
    ENRICHED = "enriched"
    OUTREACH_SENT = "outreach_sent"
    ENGAGED = "engaged"
    QUALIFIED = "qualified"
    CALL_BOOKED = "call_booked"
    HANDED_OFF = "handed_off"
    STALLED = "stalled"
    OPTED_OUT = "opted_out"


class Channel(str, Enum):
    EMAIL = "email"
    SMS = "sms"
    VOICE = "voice"


class ReplyClass(str, Enum):
    ENGAGED = "engaged"
    CURIOUS = "curious"
    HARD_NO = "hard_no"
    SOFT_DEFER = "soft_defer"
    OBJECTION = "objection"
    AMBIGUOUS = "ambiguous"


class VelocityLabel(str, Enum):
    TRIPLED_OR_MORE = "tripled_or_more"
    DOUBLED = "doubled"
    INCREASED_MODESTLY = "increased_modestly"
    FLAT = "flat"
    DECLINED = "declined"
    INSUFFICIENT_SIGNAL = "insufficient_signal"


class SignalStrength(str, Enum):
    STRONG = "strong"
    MODERATE = "moderate"
    WEAK = "weak"
    ABSENT = "absent"


# --- Hiring Signal Brief (per hiring_signal_brief.schema.json) ---

class AIMaturityJustification(BaseModel):
    signal: str  # ai_adjacent_open_roles, named_ai_ml_leadership, etc.
    status: str
    weight: str = "medium"  # high, medium, low
    confidence: str = "medium"  # high, medium, low
    source_url: Optional[str] = None


class AIMaturityScore(BaseModel):
    score: int = Field(0, ge=0, le=3)
    confidence: float = Field(0.0, ge=0.0, le=1.0)
    justifications: list[AIMaturityJustification] = Field(default_factory=list)


class HiringVelocity(BaseModel):
    open_roles_today: int = 0
    open_roles_60_days_ago: int = 0
    velocity_label: VelocityLabel = VelocityLabel.INSUFFICIENT_SIGNAL
    signal_confidence: float = 0.0
    sources: list[str] = Field(default_factory=list)


class FundingEvent(BaseModel):
    detected: bool = False
    stage: Optional[str] = None  # seed, series_a, series_b, etc.
    amount_usd: Optional[int] = None
    closed_at: Optional[str] = None
    source_url: Optional[str] = None


class LayoffEvent(BaseModel):
    detected: bool = False
    date: Optional[str] = None
    headcount_reduction: Optional[int] = None
    percentage_cut: Optional[float] = None
    source_url: Optional[str] = None


class LeadershipChange(BaseModel):
    detected: bool = False
    role: Optional[str] = None  # cto, vp_engineering, etc.
    new_leader_name: Optional[str] = None
    started_at: Optional[str] = None
    source_url: Optional[str] = None


class BuyingWindowSignals(BaseModel):
    funding_event: FundingEvent = Field(default_factory=FundingEvent)
    layoff_event: LayoffEvent = Field(default_factory=LayoffEvent)
    leadership_change: LeadershipChange = Field(default_factory=LeadershipChange)


class BenchToBriefMatch(BaseModel):
    required_stacks: list[str] = Field(default_factory=list)
    bench_available: bool = False
    gaps: list[str] = Field(default_factory=list)


class DataSourceCheck(BaseModel):
    source: str
    status: str  # success, partial, no_data, error, rate_limited
    error_message: Optional[str] = None
    fetched_at: Optional[str] = None


class HiringSignalBrief(BaseModel):
    prospect_domain: str = ""
    prospect_name: str = ""
    generated_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")
    primary_segment_match: str = "abstain"
    segment_confidence: float = 0.0
    ai_maturity: AIMaturityScore = Field(default_factory=AIMaturityScore)
    hiring_velocity: HiringVelocity = Field(default_factory=HiringVelocity)
    buying_window_signals: BuyingWindowSignals = Field(default_factory=BuyingWindowSignals)
    tech_stack: list[str] = Field(default_factory=list)
    bench_to_brief_match: BenchToBriefMatch = Field(default_factory=BenchToBriefMatch)
    data_sources_checked: list[DataSourceCheck] = Field(default_factory=list)
    honesty_flags: list[str] = Field(default_factory=list)


# --- Competitor Gap Brief (per competitor_gap_brief.schema.json) ---

class PeerEvidence(BaseModel):
    competitor_name: str
    evidence: str
    source_url: str = ""


class GapFinding(BaseModel):
    practice: str
    peer_evidence: list[PeerEvidence] = Field(default_factory=list)
    prospect_state: str = ""
    confidence: str = "medium"  # high, medium, low
    segment_relevance: list[str] = Field(default_factory=list)


class CompetitorEntry(BaseModel):
    name: str
    domain: str = ""
    ai_maturity_score: int = 0
    ai_maturity_justification: list[str] = Field(default_factory=list)
    headcount_band: str = ""
    top_quartile: bool = False
    sources_checked: list[str] = Field(default_factory=list)


class GapQualitySelfCheck(BaseModel):
    all_peer_evidence_has_source_url: bool = False
    at_least_one_gap_high_confidence: bool = False
    prospect_silent_but_sophisticated_risk: bool = False


class CompetitorGapBrief(BaseModel):
    prospect_domain: str = ""
    prospect_sector: str = ""
    prospect_sub_niche: Optional[str] = None
    generated_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")
    prospect_ai_maturity_score: int = 0
    sector_top_quartile_benchmark: float = 0.0
    competitors_analyzed: list[CompetitorEntry] = Field(default_factory=list)
    gap_findings: list[GapFinding] = Field(default_factory=list)
    suggested_pitch_shift: str = ""
    gap_quality_self_check: GapQualitySelfCheck = Field(default_factory=GapQualitySelfCheck)


# --- ICP Classification ---

class ICPClassification(BaseModel):
    segment: ICPSegment = ICPSegment.UNCLASSIFIED
    confidence: float = Field(0.0, ge=0.0, le=1.0)
    reasoning: str = ""
    secondary_segment: Optional[ICPSegment] = None
    bench_match: bool = False
    bench_match_detail: str = ""


# --- Prospect ---

class Prospect(BaseModel):
    id: str = ""
    company_name: str = ""
    domain: str = ""
    contact_name: Optional[str] = None
    contact_email: Optional[str] = None
    contact_phone: Optional[str] = None
    contact_title: Optional[str] = None

    # Firmographics
    industry: Optional[str] = None
    employee_count: Optional[int] = None
    location: Optional[str] = None
    description: Optional[str] = None
    website: Optional[str] = None
    linkedin_url: Optional[str] = None

    # Enrichment outputs
    signal_brief: Optional[HiringSignalBrief] = None
    gap_brief: Optional[CompetitorGapBrief] = None
    classification: Optional[ICPClassification] = None

    # State
    state: ConversationState = ConversationState.NEW
    channel: Channel = Channel.EMAIL
    emails_sent: int = 0
    last_contact: Optional[datetime] = None
    hubspot_contact_id: Optional[str] = None
    calcom_booking_id: Optional[str] = None

    # Metadata
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    is_synthetic: bool = True
    draft: bool = True


# --- Legacy Signal Types (used internally by enrichment sub-modules) ---

class FundingSignal(BaseModel):
    round_type: Optional[str] = None
    amount_usd: Optional[float] = None
    date: Optional[str] = None
    recency_days: Optional[int] = None
    strength: SignalStrength = SignalStrength.ABSENT
    source: str = ""


class JobPostSignal(BaseModel):
    total_open_roles: int = 0
    engineering_roles: int = 0
    ai_ml_roles: int = 0
    velocity_60d: Optional[float] = None
    top_stacks: list[str] = Field(default_factory=list)
    strength: SignalStrength = SignalStrength.ABSENT
    source: str = ""


class LayoffSignal(BaseModel):
    occurred: bool = False
    date: Optional[str] = None
    headcount: Optional[int] = None
    percentage: Optional[float] = None
    recency_days: Optional[int] = None
    strength: SignalStrength = SignalStrength.ABSENT
    source: str = ""


class LeadershipSignal(BaseModel):
    new_leader: bool = False
    name: Optional[str] = None
    title: Optional[str] = None
    appointed_date: Optional[str] = None
    recency_days: Optional[int] = None
    strength: SignalStrength = SignalStrength.ABSENT
    source: str = ""
