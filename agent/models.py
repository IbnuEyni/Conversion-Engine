"""Core data models for the Conversion Engine."""

from __future__ import annotations
from datetime import datetime
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


# --- Enums ---

class ICPSegment(str, Enum):
    RECENTLY_FUNDED = "recently_funded_startup"
    RESTRUCTURING = "mid_market_restructuring"
    LEADERSHIP_TRANSITION = "leadership_transition"
    CAPABILITY_GAP = "capability_gap"
    UNCLASSIFIED = "unclassified"


class ConversationState(str, Enum):
    NEW = "new"
    ENRICHED = "enriched"
    OUTREACH_SENT = "outreach_sent"
    ENGAGED = "engaged"          # prospect replied
    QUALIFIED = "qualified"
    CALL_BOOKED = "call_booked"
    HANDED_OFF = "handed_off"
    STALLED = "stalled"
    OPTED_OUT = "opted_out"


class Channel(str, Enum):
    EMAIL = "email"
    SMS = "sms"
    VOICE = "voice"


class SignalStrength(str, Enum):
    STRONG = "strong"
    MODERATE = "moderate"
    WEAK = "weak"
    ABSENT = "absent"


# --- Signal Models ---

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
    velocity_60d: Optional[float] = None  # % change over 60 days
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


class AIMaturityScore(BaseModel):
    score: int = Field(0, ge=0, le=3)
    confidence: float = Field(0.0, ge=0.0, le=1.0)
    justification: list[str] = Field(default_factory=list)
    signal_inputs: dict = Field(default_factory=dict)


class CompetitorGapEntry(BaseModel):
    competitor_name: str
    ai_maturity: int = 0
    key_practices: list[str] = Field(default_factory=list)
    source: str = ""


class CompetitorGapBrief(BaseModel):
    prospect_position: str = ""  # e.g., "below median"
    sector: str = ""
    top_quartile_practices: list[str] = Field(default_factory=list)
    specific_gaps: list[str] = Field(default_factory=list)
    competitors: list[CompetitorGapEntry] = Field(default_factory=list)


# --- Hiring Signal Brief ---

class HiringSignalBrief(BaseModel):
    company_name: str
    crunchbase_id: Optional[str] = None
    funding: FundingSignal = Field(default_factory=FundingSignal)
    job_posts: JobPostSignal = Field(default_factory=JobPostSignal)
    layoffs: LayoffSignal = Field(default_factory=LayoffSignal)
    leadership: LeadershipSignal = Field(default_factory=LeadershipSignal)
    ai_maturity: AIMaturityScore = Field(default_factory=AIMaturityScore)
    tech_stack: list[str] = Field(default_factory=list)
    enriched_at: datetime = Field(default_factory=datetime.utcnow)


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
    crunchbase_id: Optional[str] = None
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
    draft: bool = True  # all outputs marked draft per data handling policy
