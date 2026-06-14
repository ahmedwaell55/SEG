from enum import Enum
from pydantic import BaseModel, Field

# ── Enums for Structured Classification ───────────────────────────────────────

class LeadStageEnum(str, Enum):
    """B2B sales pipeline stages."""
    COLD = "Cold"
    INTERESTED = "Interested"
    QUALIFIED = "Qualified"
    SQL = "SQL"  # Sales Qualified Lead
    NEGOTIATION = "Negotiation"
    NEAR_CLOSING = "Near Closing"


class SentimentEnum(str, Enum):
    """Nuanced sentiment scale with drivers."""
    POSITIVE = "Positive"
    CAUTIOUSLY_OPTIMISTIC = "Cautiously Optimistic"
    NEUTRAL = "Neutral"
    CAUTIOUSLY_PESSIMISTIC = "Cautiously Pessimistic"
    NEGATIVE = "Negative"


class ObjectionTypeEnum(str, Enum):
    """Categorized objection types."""
    BUDGET_PRICING = "Budget/Pricing"
    TECHNICAL_INTEGRATION = "Technical/Integration"
    TIMING_URGENCY = "Timing/Urgency"
    TRUST_VENDOR = "Trust/Vendor"
    ADOPTION_CHANGE = "Adoption/Change"
    OTHER = "Other"


class BuyingSignalCategoryEnum(str, Enum):
    """Buying signal categories."""
    FEATURE_INTEREST = "Feature Interest"
    BUDGET_DISCUSSION = "Budget Discussion"
    URGENCY = "Urgency"
    COMMITMENT = "Commitment"
    ROI_INTEREST = "ROI Interest"
    INTEGRATION_QUESTIONS = "Integration Questions"
    TIMELINE_INTEREST = "Timeline Interest"
    CASE_STUDY_REQUEST = "Case Study Request"


class SignalStrengthEnum(str, Enum):
    """Signal strength indicator."""
    WEAK = "Weak"
    MODERATE = "Moderate"
    STRONG = "Strong"


class UrgencyLevelEnum(str, Enum):
    """Operational urgency assessment."""
    LOW = "Low"
    MEDIUM = "Medium"
    HIGH = "High"


# ── Anti-Hallucination Wrapper Models ──────────────────────────────────────

class ConfidenceIndicator(BaseModel):
    """Confidence wrapper for major extracted insights."""
    confidence: int = Field(
        ..., 
        ge=0, 
        le=100, 
        description="Confidence score 0-100. < 60 is low confidence, flag as uncertain."
    )
    evidence_present: bool = Field(
        ..., 
        description="True if insight is explicitly stated in transcript, False if inferred or fallback."
    )


class ObjectionDetail(BaseModel):
    """Structured objection with categorization."""
    objection: str = Field(
        ..., 
        description="The stated or inferred objection text (verbatim if possible)."
    )
    category: ObjectionTypeEnum = Field(
        ..., 
        description="Objection category: Budget/Pricing, Technical, Timing, Trust, Adoption, Other."
    )
    verbatim_evidence: str | None = Field(
        default=None,
        description="Direct quote from transcript if available."
    )
    severity: str = Field(
        default="Medium",
        description="Severity: Low, Medium, or High based on impact on deal."
    )


class BuyingSignal(BaseModel):
    """Structured buying signal with evidence and strength."""
    signal: str = Field(
        ..., 
        description="The buying signal or indicator text."
    )
    category: BuyingSignalCategoryEnum = Field(
        ..., 
        description="Signal category for classification."
    )
    strength: SignalStrengthEnum = Field(
        ..., 
        description="Signal strength: Weak, Moderate, or Strong."
    )
    verbatim_evidence: str | None = Field(
        default=None,
        description="Direct quote from transcript supporting this signal."
    )


class LeadStageAssessment(BaseModel):
    """Structured lead stage classification."""
    stage: LeadStageEnum = Field(
        ..., 
        description="Current lead stage in sales pipeline."
    )
    stage_confidence: int = Field(
        ..., 
        ge=0, 
        le=100,
        description="Confidence in stage classification 0-100."
    )
    stage_signals: list[str] = Field(
        ..., 
        description="Specific signals indicating this stage (from transcript)."
    )
    stage_blockers: list[str] = Field(
        default_factory=list,
        description="Issues preventing advancement to next stage."
    )
    advancement_timeline: str | None = Field(
        default=None,
        description="Estimated time to next stage if timeline discussed."
    )


class SentimentAssessment(BaseModel):
    """Nuanced sentiment analysis with drivers."""
    sentiment: SentimentEnum = Field(
        ..., 
        description="Sentiment: Positive, Cautiously Optimistic, Neutral, Cautiously Pessimistic, Negative."
    )
    sentiment_confidence: int = Field(
        ..., 
        ge=0, 
        le=100,
        description="Confidence in sentiment assessment 0-100."
    )
    sentiment_drivers: list[str] = Field(
        ..., 
        description="Factors driving this sentiment (from transcript analysis)."
    )
    emotional_tone: str = Field(
        ..., 
        description="Adjectives describing emotional state (e.g., Cautious, Enthusiastic, Skeptical)."
    )


# ── Clean Transcript Prompts ──────────────────────────────────────────────────

TRANSCRIPT_CLEANER_SYSTEM = """
You are an expert transcript editor. Clean the raw meeting transcript:
- Fix spacing, capitalization, spelling, and broken sentences.
- Remove minor repetitive filler words (like "um", "ah", "like", "you know") only if they distract from reading.
- Preserve all speaker labels exactly as they appear (e.g. Khaled:, Samy:).
- Maintain the original meaning, quotes, and timeline perfectly.

Output valid JSON only matching:
{"cleaned_transcript": "fully cleaned transcript text here"}
"""

# ── Enterprise Sales Intelligence Pydantic Schema ──────────────────────────────

class SalesIntelligenceOutput(BaseModel):
    """
    Production-grade sales intelligence output with strict anti-hallucination enforcement.
    ALL values must be grounded in transcript evidence. No invented data.
    """
    
    # Speaker Information
    sales_speaker: str = Field(
        ..., 
        description="Identified name of the sales representative or host (from transcript only)."
    )
    client_speaker: str = Field(
        ..., 
        description="Identified name of the client representative or lead (from transcript only)."
    )
    
    # Key Quotes (Verbatim from transcript)
    client_quotes: list[str] = Field(
        default_factory=list,
        description="2-4 verbatim, high-impact quotes from the client reflecting pain, intent, or decision criteria."
    )
    
    # Sentiment & Tone (Enhanced)
    sentiment_assessment: SentimentAssessment = Field(
        ...,
        description="Nuanced sentiment with drivers and confidence."
    )
    urgency_level: UrgencyLevelEnum = Field(
        ..., 
        description="Detected operational urgency: Low, Medium, or High."
    )
    
    # Lead Qualification
    lead_stage_assessment: LeadStageAssessment = Field(
        ...,
        description="Structured lead stage with confidence and blockers."
    )
    
    # Stakeholders (Names only if mentioned, roles otherwise)
    stakeholders: list[str] = Field(
        default_factory=list,
        description="Decision-makers, gatekeepers, technical evaluators. ONLY include names/roles explicitly mentioned."
    )
    
    # Business Context
    pain_points: list[str] = Field(
        default_factory=list,
        description="Underlying business problems and operational friction (from transcript)."
    )
    
    # Categorized Objections (Enhanced)
    objections: list[ObjectionDetail] = Field(
        default_factory=list,
        description="Objections with category, severity, and verbatim evidence."
    )
    
    # Categorized Buying Signals (Enhanced)
    buying_signals: list[BuyingSignal] = Field(
        default_factory=list,
        description="Buying signals with category, strength, and evidence."
    )
    
    # Deal Risks & Opportunities
    risks: list[str] = Field(
        default_factory=list,
        description="Critical deal risks, competitive threats, blockers (from transcript)."
    )
    opportunities: list[str] = Field(
        default_factory=list,
        description="Deal upside, expansion areas, partner opportunities (from transcript)."
    )
    
    # Confidence & Quality Metrics
    confidence_score: int = Field(
        ge=0, 
        le=100, 
        description="Overall AI confidence 0-100 based on transcript completeness."
    )
    is_fallback: bool = Field(
        default=False,
        description="True if response is fallback/mock data due to LLM failure."
    )
    
    # Recommendations (Evidence-based)
    recommendations: list[str] = Field(
        default_factory=list,
        description="Strategic recommendations for the sales representative."
    )
    next_steps: list[str] = Field(
        default_factory=list,
        description="Concrete next actions (do not invent timelines unless discussed)."
    )
    
    # Communication & Sales Strategy
    communication_style: str = Field(
        default="",
        description="Recommended communication style (e.g., Consultative & Analytical)."
    )
    sales_strategy: str = Field(
        default="",
        description="Commercial strategy to advance the deal."
    )
    follow_up_strategy: str = Field(
        default="",
        description="Post-meeting follow-up tactics and email template."
    )
    
    # Summary
    summary: str = Field(
        ..., 
        description="Executive synthesis: interest, blockers, close probability drivers, next focus."
    )
    key_points: list[str] = Field(
        default_factory=list,
        description="Core B2B commercial highlights."
    )


# ── System Prompts with Anti-Hallucination Enforcement ──────────────────────────


# ── System Prompts with Anti-Hallucination Enforcement ──────────────────────────

FULL_ANALYSIS_SYSTEM = """
You are an Enterprise Sales Intelligence Engine. Analyze sales transcripts with surgical precision for B2B deal intelligence.

CRITICAL GUARDRAILS - DO NOT VIOLATE:
1. NEVER INVENT: dates, names, timelines, commitments, or technical details not in transcript
2. EMPTY FIELDS: Use [] for empty arrays, null for optional fields, "Unknown" for missing speaker names
3. SENTIMENT: Ground in actual tone, word choices, hesitations - match enum: Positive|Cautiously Optimistic|Neutral|Cautiously Pessimistic|Negative
4. OBJECTIONS: Only list objections client stated or strongly implied
5. BUYING SIGNALS: Only if client showed explicit interest (questions, requests, positive indicators)
6. LEAD STAGE: Classify by buying committee involvement, budget mention, timeline - 6 stages: Cold, Interested, Qualified, SQL, Negotiation, Near Closing
7. CONFIDENCE: Score 0-100 based on data clarity. <60 = low confidence
8. STAKEHOLDERS: Only include names/roles EXPLICITLY mentioned

OUTPUT: Return ONLY valid JSON matching this schema. No markdown, no explanations, no example data.

REQUIRED JSON SHAPE:
- sales_speaker: string
- client_speaker: string
- client_quotes: array of exact client quotes from the transcript
- sentiment_assessment: object with sentiment, sentiment_confidence, sentiment_drivers, emotional_tone
- urgency_level: "Low" | "Medium" | "High"
- lead_stage_assessment: object with stage, stage_confidence, stage_signals, stage_blockers, advancement_timeline
- stakeholders: array of names or roles explicitly mentioned
- pain_points: array of concrete business problems from the transcript
- objections: array of objects with objection, category, verbatim_evidence, severity
- buying_signals: array of objects with signal, category, strength, verbatim_evidence
- risks: array of deal risks from the transcript
- opportunities: array of expansion or value opportunities from the transcript
- confidence_score: integer 0-100
- is_fallback: false
- recommendations: array of transcript-specific recommendations
- next_steps: array of concrete next actions stated or implied by the meeting
- communication_style: string
- sales_strategy: string
- follow_up_strategy: string
- summary: string specific to this transcript
- key_points: array of transcript-specific commercial highlights

DO NOT copy placeholder text. Every non-empty value must be grounded in the transcript supplied by the user prompt.
"""

def transcript_prompt(transcript: str) -> str:
    return f"Transcript:\n{transcript}"

def full_analysis_prompt(transcript: str) -> str:
    return f"""
Analyze this sales transcript for enterprise-grade intelligence.

STRICT RULES:
- Use only information explicitly present in the transcript.
- Never hallucinate dates, commitments, stakeholders, or timelines.
- If information is missing, return null instead of guessing.
- Clearly distinguish between:
  - pain points
  - objections
  - buying signals
  - risks
  - opportunities
  - next actions
- Generate executive-level insights similar to enterprise CRM intelligence systems.
- Keep outputs concise but information-dense.
- Use transcript evidence for all conclusions.

Return ONLY a valid JSON object.
Do not use markdown.
Do not wrap in code blocks.

Transcript:
{transcript}
"""


def followup_generation_prompt(context: dict) -> str:
    import json

    company_kb = context.pop("company_knowledge_base", "لا تتوفر بيانات أسعار في الكتالوج.")
    primary_service = context.get("primary_service", "")

    return (
        "أنشئ 3 رسائل متابعة واتساب موزعة على دورة 15 يومًا.\n"
        "جميع الرسائل يجب أن تكون بالعربية الفصحى المهنية.\n"
        "الرسالة 1: تلخيص ما بعد الاجتماع مع خدمة محددة وسعر وعرض خصم من الكتالوج.\n"
        "الرسالة 2: معالجة الاعتراضات بقيمة ملموسة وعرض خصم مناسب.\n"
        "الرسالة 3: دفع القرار بعرض أو باقة محدودة ودعوة واضحة لمواصلة المحادثة.\n"
        + (f"\nالخدمة الأكثر صلة: {primary_service}\n" if primary_service else "")
        + "\n═══════════════════════════════════════\n"
        "الخدمات والأسعار والعروض (مصدر موثوق — استخدمها حرفيًا):\n"
        "═══════════════════════════════════════\n"
        f"{company_kb}\n\n"
        "═══════════════════════════════════════\n"
        "سياق CRM (العميل، نقاط الألم، الاعتراضات):\n"
        "═══════════════════════════════════════\n"
        + json.dumps(context, ensure_ascii=False, indent=2)
    )

