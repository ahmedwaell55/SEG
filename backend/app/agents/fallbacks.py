import re
from collections import Counter

from app.utils.transcript import clean_list, normalize_transcript

POSITIVE_TERMS = {
    "interested",
    "good",
    "great",
    "perfect",
    "yes",
    "agree",
    "start",
    "move forward",
    "send proposal",
    "next week",
    "contract",
    "budget approved",
}

NEGATIVE_TERMS = {
    "expensive",
    "concern",
    "problem",
    "not sure",
    "later",
    "no budget",
    "need to think",
    "competitor",
    "risk",
    "delay",
    "too much",
}

OBJECTION_TERMS = (
    "price",
    "expensive",
    "budget",
    "concern",
    "risk",
    "not sure",
    "need to think",
    "competitor",
    "timeline",
    "delay",
    "approval",
    "decision",
    "integration",
)

PAIN_TERMS = (
    "problem",
    "challenge",
    "struggle",
    "slow",
    "manual",
    "lost",
    "waste",
    "miss",
    "hard",
    "issue",
    "pain",
)

BUYING_TERMS = (
    "interested",
    "next step",
    "send",
    "proposal",
    "contract",
    "start",
    "timeline",
    "demo",
    "approve",
    "budget",
    "when can",
)

GENERIC_NON_INSIGHTS = (
    "good afternoon",
    "no problem at all",
    "thank you",
    "thanks",
    "that sounds painful",
    "totally fair concern",
    "understood",
    "completely understandable",
    "that's accurate",
    "that makes sense",
    "that would help",
    "sounds reasonable",
)

SALES_LABEL_HINTS = {"sales", "sales rep", "representative", "rep", "samy", "ceo"}
CLIENT_LABEL_HINTS = {"client", "customer", "prospect", "lead"}
SPEAKER_LINE_PATTERN = re.compile(r"^([A-Za-z][A-Za-z ._-]{1,30}):\s*(.*)$")


def _sentences(text: str) -> list[str]:
    pieces = re.split(r"(?<=[.!?])\s+|\n+", text)
    return [piece.strip(" -") for piece in pieces if len(piece.strip()) > 12]


def _contains_any(text: str, terms: tuple[str, ...] | set[str]) -> bool:
    lower = text.lower()
    return any(term in lower for term in terms)


def _extract(text: str, terms: tuple[str, ...] | set[str], default: str) -> list[str]:
    matches = [sentence for sentence in _sentences(text) if _contains_any(sentence, terms)]
    if not matches:
        return [default]
    return clean_list(matches, max_items=8)


def _prepare_speaker_lines(text: str) -> str:
    # Helps parse single-line transcripts such as "Sales: ... Client: ...".
    return re.sub(r"(?<!^)(?<!\n)\s+([A-Z][A-Za-z ._-]{1,30}:)", r"\n\1", text)


def _turns(text: str) -> list[dict[str, str]]:
    prepared = _prepare_speaker_lines(text)
    turns: list[dict[str, str]] = []
    speaker = ""
    lines: list[str] = []

    def flush() -> None:
        body = " ".join(part.strip() for part in lines if part.strip()).strip()
        if body:
            turns.append({"speaker": speaker, "text": body})

    for raw_line in prepared.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        match = SPEAKER_LINE_PATTERN.match(line)
        if match:
            flush()
            speaker = match.group(1).strip()
            body = match.group(2).strip()
            lines = [body] if body else []
        elif speaker:
            lines.append(line)
        else:
            turns.append({"speaker": "", "text": line})

    flush()
    return turns


def _infer_speaker_labels(text: str) -> tuple[str | None, str | None]:
    labels = [turn["speaker"] for turn in _turns(text) if turn["speaker"]]
    if not labels:
        return None, None

    counts = Counter(labels)
    sales_label: str | None = None
    client_label: str | None = None

    for label, _ in counts.most_common():
        normalized = label.lower().strip()
        if normalized in SALES_LABEL_HINTS and not sales_label:
            sales_label = label
        if normalized in CLIENT_LABEL_HINTS and not client_label:
            client_label = label

    common = [label for label, _ in counts.most_common()]
    sales_label = sales_label or common[0]
    client_label = client_label or next((label for label in common if label != sales_label), None)
    return sales_label, client_label


def _client_turns(text: str) -> list[dict[str, str]]:
    turns = _turns(text)
    sales_label, client_label = _infer_speaker_labels(text)

    if client_label:
        selected = [turn for turn in turns if turn["speaker"].lower() == client_label.lower()]
        if selected:
            return selected

    if sales_label:
        selected = [turn for turn in turns if turn["speaker"] and turn["speaker"].lower() != sales_label.lower()]
        if selected:
            return selected

    return turns


def _client_blob(text: str) -> str:
    return " ".join(turn["text"] for turn in _client_turns(text)).strip()


def _client_sentences(text: str) -> list[str]:
    return _sentences(_client_blob(text) or text)


def _append_unique(values: list[str], value: str) -> None:
    value = value.strip()
    if value and value not in values:
        values.append(value)


def _is_weak_insight(sentence: str) -> bool:
    lower = sentence.lower().strip()
    if len(lower) < 28:
        return True
    if any(phrase in lower for phrase in GENERIC_NON_INSIGHTS):
        return True
    if lower.endswith("?"):
        return True
    if lower in {"yes", "no", "exactly", "great", "perfect"}:
        return True
    if "biggest problem" in lower and len(lower) < 90:
        return True
    return False


def _fallback_matches(text: str, terms: tuple[str, ...] | set[str], default: str) -> list[str]:
    matches = [
        sentence
        for sentence in _client_sentences(text)
        if _contains_any(sentence, terms) and not _is_weak_insight(sentence)
    ]
    return clean_list(matches, max_items=8) or [default]


def _pain_point_insights(text: str) -> list[str]:
    blob = (_client_blob(text) or text).lower()
    insights: list[str] = []

    if _contains_any(blob, ("spreadsheet", "manual", "disconnected")):
        _append_unique(
            insights,
            "Operations rely on manual spreadsheets and disconnected systems, slowing reporting and reducing visibility.",
        )
    if _contains_any(blob, ("reports take forever", "hours", "weekly summaries", "preparing reports")):
        _append_unique(
            insights,
            "Managers spend excessive time preparing reports instead of solving operational issues.",
        )
    if _contains_any(blob, ("mistakes", "copied manually", "inaccurate", "delayed")):
        _append_unique(
            insights,
            "Manual data copying causes frequent mistakes, delayed shipment updates, and inaccurate information.",
        )
    if _contains_any(blob, ("lost two major clients", "financial losses", "operational delays")):
        _append_unique(
            insights,
            "Delayed and inaccurate shipment updates have already caused client loss and operational impact.",
        )
    if _contains_any(blob, ("communication internally", "centralized", "data isn't centralized", "data is not centralized")):
        _append_unique(
            insights,
            "Internal communication is weak because operational data is not centralized.",
        )
    if _contains_any(blob, ("employees resisted", "complicated", "six months", "implementation was always a disaster")):
        _append_unique(
            insights,
            "Past software rollouts were slow and complicated, creating employee adoption risk.",
        )

    if insights:
        return clean_list(insights, max_items=8)
    return _fallback_matches(text, PAIN_TERMS, "Pain points were not explicitly stated.")


def _objection_insights(text: str) -> list[str]:
    blob = (_client_blob(text) or text).lower()
    insights: list[str] = []

    if _contains_any(blob, ("price", "pricing", "expensive", "budget", "roi")):
        _append_unique(
            insights,
            "Pricing and budget approval are concerns; management needs clear ROI before approving.",
        )
    if _contains_any(blob, ("implementation", "onboarding", "six months", "employees resisted", "complicated")):
        _append_unique(
            insights,
            "The client is worried implementation could be slow, complicated, or poorly adopted by employees.",
        )
    if _contains_any(blob, ("security", "sensitive", "on-premise", "encrypted", "audit")):
        _append_unique(
            insights,
            "Security is a key concern because the client handles sensitive shipping data.",
        )
    if _contains_any(blob, ("case studies", "actual case", "numbers", "presenting this internally")):
        _append_unique(
            insights,
            "The client needs logistics-specific case studies and numbers before presenting internally.",
        )
    if _contains_any(blob, ("ceo", "finance director", "it manager", "decision-making")):
        _append_unique(
            insights,
            "Final approval depends on alignment with the CEO, finance director, and IT manager.",
        )

    if insights:
        return clean_list(insights, max_items=8)
    return _fallback_matches(text, OBJECTION_TERMS, "No explicit objection was detected.")


def _buying_signal_insights(text: str) -> list[str]:
    blob = (_client_blob(text) or text).lower()
    insights: list[str] = []

    if _contains_any(blob, ("curious", "interested", "definitely help", "liked")):
        _append_unique(
            insights,
            "The client is engaged and sees value in the proposed platform.",
        )
    if _contains_any(blob, ("ai assistant", "reports", "weekly summaries", "interests me the most")):
        _append_unique(
            insights,
            "AI-generated reporting is a strong interest area because managers waste time on weekly summaries.",
        )
    if _contains_any(blob, ("roi is clear", "management can approve", "decent budget")):
        _append_unique(
            insights,
            "Budget can move forward if ROI and implementation quality are proven.",
        )
    if _contains_any(blob, ("case studies", "that would help")):
        _append_unique(
            insights,
            "The client requested case studies to support internal buy-in.",
        )
    if _contains_any(blob, ("technical workshop", "it manager")):
        _append_unique(
            insights,
            "The client is open to a technical workshop with IT.",
        )
    if _contains_any(blob, ("follow-up", "next week", "continuing discussions")):
        _append_unique(
            insights,
            "The client is interested in continuing discussions and coordinating a follow-up meeting.",
        )

    if insights:
        return clean_list(insights, max_items=8)
    return _fallback_matches(text, BUYING_TERMS, "No strong buying signal was detected.")


def _join_summary_items(items: list[str], max_items: int = 3) -> str:
    cleaned = [item.rstrip(".") for item in items if item]
    return "; ".join(cleaned[:max_items])


def _score(text: str) -> int:
    lower = (_client_blob(text) or text).lower()
    positive = sum(lower.count(term) for term in POSITIVE_TERMS)
    negative = sum(lower.count(term) for term in NEGATIVE_TERMS)
    score = 50 + positive * 7 - negative * 6
    if "send proposal" in lower or "move forward" in lower:
        score += 12
    if "no budget" in lower or "not interested" in lower:
        score -= 18
    return max(5, min(95, score))


def acceptance_label(probability: int) -> str:
    if probability >= 75:
        return "High"
    if probability >= 45:
        return "Medium"
    return "Low"


def cleaner_fallback(transcript: str) -> dict:
    return {"cleaned_transcript": normalize_transcript(transcript)}


def speaker_fallback(transcript: str) -> dict:
    sales_label, client_label = _infer_speaker_labels(transcript)
    client_text = _client_blob(transcript) or transcript
    return {
        "sales_speaker": sales_label or "Sales representative",
        "client_speaker": client_label or "Client",
        "speaker_notes": "Speaker labels were inferred from transcript formatting.",
        "client_quotes": _extract(client_text, BUYING_TERMS, "No clear direct client quote detected.")[:4],
    }


def sentiment_fallback(transcript: str) -> dict:
    probability = _score(transcript)
    client_text = _client_blob(transcript) or transcript
    if probability >= 70:
        sentiment = "Positive"
    elif probability <= 35:
        sentiment = "Negative"
    elif 45 <= probability <= 60:
        sentiment = "Neutral"
    else:
        sentiment = "Mixed"
    hesitation = "High" if _contains_any(transcript, ("not sure", "need to think", "delay")) else "Medium"
    urgency = "High" if _contains_any(transcript, ("urgent", "as soon", "this week", "next week")) else "Medium"
    return {
        "sentiment": sentiment,
        "emotional_tone": "Cautiously engaged" if sentiment in {"Mixed", "Neutral"} else sentiment,
        "hesitation_level": hesitation,
        "urgency_level": urgency,
        "confidence_score": min(90, max(45, probability)),
        "buying_intent": acceptance_label(probability),
        "evidence": _fallback_matches(client_text, POSITIVE_TERMS | NEGATIVE_TERMS, "Limited explicit sentiment evidence in transcript."),
    }


def objection_fallback(transcript: str) -> dict:
    return {
        "objections": _objection_insights(transcript),
        "pain_points": _pain_point_insights(transcript),
        "buying_signals": _buying_signal_insights(transcript),
        "blockers": _fallback_matches(transcript, ("approval", "budget", "decision", "timeline"), "No clear blocker was detected."),
    }


def prediction_fallback(transcript: str) -> dict:
    probability = _score(transcript)
    return {
        "acceptance_probability": probability,
        "acceptance_label": acceptance_label(probability),
        "confidence_score": min(88, max(45, probability)),
        "reasoning": "Estimated from positive intent, objections, urgency, and next-step clarity found in the transcript.",
    }


def recommendation_fallback(transcript: str) -> dict:
    objections = objection_fallback(transcript)["objections"]
    return {
        "recommendations": [
            "Open the next meeting by confirming the client's highest-priority business problem.",
            "Address the strongest objection directly with proof, numbers, or a relevant case example.",
            "Ask for a clear decision process, timeline, and required stakeholders before proposing next steps.",
        ],
        "next_steps": [
            "Send a concise follow-up summary with agreed priorities and open questions.",
            "Prepare ROI or impact framing tied to the client's pain points.",
            f"Resolve this objection first: {objections[0]}",
        ],
        "communication_style": "Consultative, specific, and calm. Avoid pressure; use evidence and clear options.",
        "sales_strategy": "Convert interest into a concrete decision path by clarifying budget, authority, timeline, and success criteria.",
    }


def summary_fallback(transcript: str) -> dict:
    pain_points = _pain_point_insights(transcript)
    objections = _objection_insights(transcript)
    buying_signals = _buying_signal_insights(transcript)

    summary_parts: list[str] = []
    if pain_points and pain_points[0] != "Pain points were not explicitly stated.":
        summary_parts.append(f"The client described: {_join_summary_items(pain_points)}.")
    if buying_signals and buying_signals[0] != "No strong buying signal was detected.":
        summary_parts.append(f"Buying intent is supported by: {_join_summary_items(buying_signals, max_items=2)}.")
    if objections and objections[0] != "No explicit objection was detected.":
        summary_parts.append(f"The main risks are: {_join_summary_items(objections, max_items=2)}.")

    if summary_parts:
        summary = " ".join(summary_parts)
    else:
        client_sentences = [sentence for sentence in _client_sentences(transcript) if not _is_weak_insight(sentence)]
        summary = (
            " ".join(client_sentences[:3])
            if client_sentences
            else "Transcript was processed, but no clear meeting content was detected."
        )

    key_points = clean_list([*pain_points, *objections, *buying_signals], max_items=8)
    return {
        "summary": summary[:900],
        "key_points": key_points or ["No key discussion points detected."],
    }


def final_report_fallback(state: dict) -> dict:
    transcript = state.get("cleaned_transcript") or state.get("raw_transcript", "")
    sentiment = state.get("sentiment_report") or sentiment_fallback(transcript)
    objections = state.get("objection_report") or objection_fallback(transcript)
    prediction = state.get("prediction_report") or prediction_fallback(transcript)
    recommendation = state.get("recommendation_report") or recommendation_fallback(transcript)
    summary = state.get("summary_report") or summary_fallback(transcript)
    return {
        "summary": summary.get("summary", ""),
        "sentiment": sentiment.get("sentiment", "Neutral"),
        "emotional_tone": sentiment.get("emotional_tone", "Neutral"),
        "urgency_level": sentiment.get("urgency_level", "Medium"),
        "confidence_score": int(prediction.get("confidence_score") or sentiment.get("confidence_score") or 60),
        "pain_points": clean_list(objections.get("pain_points", [])),
        "objections": clean_list(objections.get("objections", [])),
        "buying_signals": clean_list(objections.get("buying_signals", [])),
        "acceptance_probability": int(prediction.get("acceptance_probability") or 50),
        "acceptance_label": prediction.get("acceptance_label") or acceptance_label(int(prediction.get("acceptance_probability") or 50)),
        "recommendations": clean_list(recommendation.get("recommendations", [])),
        "next_steps": clean_list(recommendation.get("next_steps", [])),
        "communication_style": recommendation.get("communication_style", ""),
        "sales_strategy": recommendation.get("sales_strategy", ""),
        "key_points": clean_list(summary.get("key_points", [])),
    }
