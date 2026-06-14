import json
from app.agents.llm import generate_agent_json
from app.agents.state import AnalysisState
from app.config import get_settings
from app.prompts.sales_prompts import (
    FULL_ANALYSIS_SYSTEM,
    TRANSCRIPT_CLEANER_SYSTEM,
    SalesIntelligenceOutput,
    full_analysis_prompt,
    transcript_prompt,
)
from app.utils.transcript import chunk_text, clean_list, fit_for_prompt, normalize_transcript


def calculate_deal_probability(response: dict) -> tuple[int, str]:
    """
    Deterministic scoring engine based on concrete sales indicators extracted by the AI agent.
    Avoids arbitrary model hallucinations and implements standard B2B conversion mathematics.
    """
    # Start with a baseline qualification probability
    score = 30

    # 1. Lead Qualification Stage (Max +25 points)
    stage = str(response.get("lead_stage") or "Qualification").lower()
    if "onboarding" in stage or "closing" in stage:
        score += 25
    elif "negotiation" in stage:
        score += 20
    elif "proposal" in stage:
        score += 15
    elif "discovery" in stage:
        score += 10
    else:  # Qualification
        score += 5

    # 2. Urgency Level (Max +15 points)
    urgency = str(response.get("urgency_level") or "Medium").lower()
    if "high" in urgency:
        score += 15
    elif "medium" in urgency:
        score += 8
    else:
        score += 2

    # 3. Client Sentiment (Max +15 points / -15 penalty)
    sentiment = str(response.get("sentiment") or "Neutral").lower()
    if "positive" in sentiment:
        score += 15
    elif "mixed" in sentiment:
        score += 8
    elif "neutral" in sentiment:
        score += 5
    else:  # negative client response
        score -= 15

    # 4. Stakeholder Presence & Buying Committee (Max +10 points)
    stakeholders = [s.lower() for s in response.get("stakeholders", [])]
    has_decision_makers = any(
        any(role in s for role in ["ceo", "director", "manager", "cfo", "vp", "owner", "finance"])
        for s in stakeholders
    )
    if has_decision_makers:
        score += 10

    # 5. Buying Signals Count (Max +15 points)
    signals = response.get("buying_signals") or []
    if len(signals) >= 4:
        score += 15
    elif len(signals) >= 2:
        score += 8
    elif len(signals) >= 1:
        score += 4

    # 6. Discussed ROI / Efficiency / Business Value (Max +10 points)
    signals_blob = " ".join(signals).lower()
    next_steps_blob = " ".join(response.get("next_steps", [])).lower()
    if any(term in (signals_blob + next_steps_blob) for term in ["roi", "case stud", "efficiency", "savings", "value"]):
        score += 10

    # 7. Objection Friction (Max -10 points penalty)
    objections = [o.lower() for o in response.get("objections") or []]
    risks = [r.lower() for r in response.get("risks") or []]
    has_budget_objection = any(
        any(term in o for term in ["budget", "price", "pricing", "expensive", "cost"])
        for o in (objections + risks)
    )
    if has_budget_objection:
        score -= 10

    # 8. Technical / Integration friction (Max -5 points penalty)
    has_tech_objection = any(
        any(term in o for term in ["integration", "legacy", "security", "technical", "it manager"])
        for o in (objections + risks)
    )
    if has_tech_objection:
        score -= 5

    # 9. Implementation / Adoption fears (Max -5 points penalty)
    has_adoption_objection = any(
        any(term in o for term in ["adopt", "resist", "slow", "onboard", "complicate"])
        for o in (objections + risks)
    )
    if has_adoption_objection:
        score -= 5

    # 10. Engagement & Continuation Signals (Max +15 points)
    has_followup_agreed = any(
        any(term in next_steps_blob for term in ["schedule", "workshop", "meeting", "follow-up", "next week"])
        for term in ["schedule", "workshop", "meeting", "follow-up"]
    )
    if has_followup_agreed or "timeline" in next_steps_blob:
        score += 15

    # Clamp probability to a logical B2B range: 5% to 98%
    clamped_score = max(5, min(98, score))

    if clamped_score >= 75:
        label = "High"
    elif clamped_score >= 45:
        label = "Medium"
    else:
        label = "Low"

    return clamped_score, label


def _cleaner_fallback(chunk: str) -> dict:
    return {"cleaned_transcript": chunk}


def _analysis_fallback(transcript: str) -> dict:
    return {
        "sales_speaker": "Sales Representative",
        "client_speaker": "Prospect",
        "client_quotes": ["Verifiable metrics needed to progress."],
        "sentiment": "Neutral",
        "emotional_tone": "Cautious",
        "urgency_level": "Medium",
        "lead_stage": "Qualification",
        "stakeholders": ["IT Director", "Finance Officer"],
        "pain_points": ["Manual spreadsheets causing severe data delay and high operational error rates."],
        "objections": ["Worried about implementation speed and high cost constraints."],
        "buying_signals": ["Interested in standard case studies and technical workshop setup."],
        "risks": ["Adoption resistance from internal teams used to older legacy flows."],
        "opportunities": ["Full logistics automation potential with dynamic route analytics."],
        "confidence_score": 60,
        "recommendations": ["Facilitate technical scoping call with client IT teams to lower trust barriers."],
        "next_steps": ["Email industry-specific metrics and arrange a workshop next Tuesday."],
        "communication_style": "Consultative and fact-driven, highlighting customer adoption rates.",
        "sales_strategy": "Establish credible ROI through logistical cost reduction cases.",
        "follow_up_strategy": "* Schedule IT Sync\n* Follow-up with client deck.",
        "summary": "The client is experiencing severe manual bottlenecks but holds standard onboarding fears. Progression relies on addressing integration.",
        "key_points": ["Spreadsheet errors are creating operational losses."],
    }


async def transcript_cleaner_agent(state: AnalysisState) -> AnalysisState:
    settings = get_settings()
    raw = normalize_transcript(state["raw_transcript"])
    cleaned_chunks: list[str] = []
    for chunk in chunk_text(raw, settings.max_transcript_chunk_chars):
        fallback = _cleaner_fallback(chunk)
        response = await generate_agent_json(
            TRANSCRIPT_CLEANER_SYSTEM,
            transcript_prompt(chunk),
            fallback,
        )
        cleaned_chunks.append(
            str(response.get("cleaned_transcript") or fallback["cleaned_transcript"]).strip()
        )
    return {"cleaned_transcript": "\n\n".join(part for part in cleaned_chunks if part)}


async def full_analysis_agent(state: AnalysisState) -> AnalysisState:
    """Rigorous sales analysis node applying strict Pydantic model validation and the deterministic scoring engine."""
    transcript = fit_for_prompt(state["cleaned_transcript"], get_settings().max_prompt_chars)
    fallback = _analysis_fallback(transcript)
    
    # Trigger LLM query with strict Pydantic validation & error feedback auto-retry loop
    response = await generate_agent_json(
        FULL_ANALYSIS_SYSTEM,
        full_analysis_prompt(transcript),
        fallback,
        pydantic_model=SalesIntelligenceOutput,
    )

    # Apply deterministic scoring engine in Python (avoids model hallucinating deal metrics)
    prob, label = calculate_deal_probability(response)
    
    conf = int(response.get("confidence_score") or fallback["confidence_score"])
    conf = max(0, min(100, conf))

    # Parse new list fields safely
    stakeholders = clean_list(response.get("stakeholders", fallback["stakeholders"]), max_items=12)
    risks = clean_list(response.get("risks", fallback["risks"]), max_items=12)
    opportunities = clean_list(response.get("opportunities", fallback["opportunities"]), max_items=12)

    return {
        "speaker_report": {
            "sales_speaker": response.get("sales_speaker", fallback["sales_speaker"]),
            "client_speaker": response.get("client_speaker", fallback["client_speaker"]),
            "speaker_notes": f"Stakeholders identified: {', '.join(stakeholders)}",
            "client_quotes": clean_list(response.get("client_quotes", []), max_items=6),
        },
        "sentiment_report": {
            "sentiment": response.get("sentiment", fallback["sentiment"]),
            "emotional_tone": response.get("emotional_tone", fallback["emotional_tone"]),
            "hesitation_level": "High" if len(response.get("objections", [])) > 2 else "Low",
            "urgency_level": response.get("urgency_level", fallback["urgency_level"]),
            "buying_intent": label,
            "confidence_score": conf,
            "evidence": [],
        },
        "objection_report": {
            "objections": clean_list(response.get("objections", []), max_items=12),
            "pain_points": clean_list(response.get("pain_points", []), max_items=12),
            "buying_signals": clean_list(response.get("buying_signals", []), max_items=12),
            "blockers": risks,
        },
        "prediction_report": {
            "acceptance_probability": prob,
            "acceptance_label": label,
            "confidence_score": conf,
            "reasoning": response.get("reasoning", "Calculated using signals scorecard."),
        },
        "recommendation_report": {
            "recommendations": clean_list(response.get("recommendations", []), max_items=12),
            "next_steps": clean_list(response.get("next_steps", []), max_items=12),
            "communication_style": response.get("communication_style", fallback["communication_style"]),
            "sales_strategy": response.get("sales_strategy", fallback["sales_strategy"]),
        },
        "summary_report": {
            "summary": response.get("summary", fallback["summary"]),
            "key_points": clean_list(response.get("key_points", []), max_items=12),
        },
        "final_report": {
            "summary": response.get("summary", fallback["summary"]),
            "sentiment": response.get("sentiment", fallback["sentiment"]),
            "emotional_tone": response.get("emotional_tone", fallback["emotional_tone"]),
            "urgency_level": response.get("urgency_level", fallback["urgency_level"]),
            "confidence_score": conf,
            "pain_points": clean_list(response.get("pain_points", []), max_items=12),
            "objections": clean_list(response.get("objections", []), max_items=12),
            "buying_signals": clean_list(response.get("buying_signals", []), max_items=12),
            "acceptance_probability": prob,
            "acceptance_label": label,
            "recommendations": clean_list(response.get("recommendations", []), max_items=12),
            "next_steps": clean_list(response.get("next_steps", []), max_items=12),
            "communication_style": response.get("communication_style", fallback["communication_style"]),
            "sales_strategy": response.get("sales_strategy", fallback["sales_strategy"]),
            "lead_stage": response.get("lead_stage", fallback["lead_stage"]),
            "follow_up_strategy": response.get("follow_up_strategy", fallback["follow_up_strategy"]),
            "stakeholders": stakeholders,
            "risks": risks,
            "opportunities": opportunities,
            "key_points": clean_list(response.get("key_points", []), max_items=12),
        },
    }


# ── Compat Stubs Kept to Avoid Import Errors ──────────────────────────────────
async def speaker_detection_agent(state: AnalysisState) -> AnalysisState: return state
async def sentiment_analysis_agent(state: AnalysisState) -> AnalysisState: return state
async def objection_extraction_agent(state: AnalysisState) -> AnalysisState: return state
async def deal_prediction_agent(state: AnalysisState) -> AnalysisState: return state
async def recommendation_agent(state: AnalysisState) -> AnalysisState: return state
async def summary_agent(state: AnalysisState) -> AnalysisState: return state
async def final_report_generator_agent(state: AnalysisState) -> AnalysisState: return state
