"""JSON-backed service catalog search with fuzzy Arabic/English matching (no embeddings)."""

from __future__ import annotations

import json
import logging
import re
import unicodedata
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

from rapidfuzz import fuzz

from app.config import get_settings

logger = logging.getLogger("ai_closer.service_search")

DEFAULT_CATALOG_PATH = Path(__file__).resolve().parents[2] / "data" / "services.json"

# Minimum fuzzy score (0–100) to consider a service a match
MATCH_THRESHOLD = 55
# Score boost when an alias appears as a substring in the conversation
ALIAS_SUBSTRING_BOOST = 25
# Short aliases (e.g. SEO, ADS) must match on word boundaries — no fuzzy-only hits
SHORT_ALIAS_MAX_LEN = 4
PHRASE_MATCH_SCORE = 120.0

# English/Arabic phrases → canonical service name (longer phrases first)
PHRASE_HINTS: list[tuple[str, str]] = [
    ("professional online store", "إنشاء متجر"),
    ("online store", "إنشاء متجر"),
    ("e-commerce store", "إنشاء متجر"),
    ("ecommerce store", "إنشاء متجر"),
    ("e-commerce", "إنشاء متجر"),
    ("ecommerce", "إنشاء متجر"),
    ("paid advertising", "الحملات الإعلانية"),
    ("paid ads", "الحملات الإعلانية"),
    ("digital advertising", "الحملات الإعلانية"),
    ("advertising campaign", "الحملات الإعلانية"),
    ("ad campaigns", "الحملات الإعلانية"),
    ("strong brand", "تصميم الهوية الكاملة"),
    ("brand identity", "تصميم الهوية الكاملة"),
    ("building a brand", "تصميم الهوية الكاملة"),
    ("visual identity", "تصميم الهوية الكاملة"),
    ("search engine optimization", "SEO"),
    ("تحسين محركات البحث", "SEO"),
    ("متجر إلكتروني", "إنشاء متجر"),
    ("الإعلانات", "الحملات الإعلانية"),
    ("السيو", "SEO"),
]


@dataclass(frozen=True)
class ServiceRecord:
    name: str
    arabic_name: str
    aliases: tuple[str, ...]
    base_price: float
    min_price: float
    max_price: float
    discount_10: float
    discount_15: float
    discount_20: float
    related_services: tuple[str, ...]

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ServiceRecord:
        aliases = list(data.get("aliases") or [])
        for field in ("name", "arabic_name"):
            value = str(data.get(field) or "").strip()
            if value and value not in aliases:
                aliases.append(value)
        related = tuple(str(r).strip() for r in (data.get("related_services") or []) if str(r).strip())
        return cls(
            name=str(data["name"]).strip(),
            arabic_name=str(data.get("arabic_name") or data["name"]).strip(),
            aliases=tuple(dict.fromkeys(a.strip() for a in aliases if a.strip())),
            base_price=float(data["base_price"]),
            min_price=float(data.get("min_price", data["base_price"])),
            max_price=float(data.get("max_price", data["base_price"])),
            discount_10=float(data["discount_10"]),
            discount_15=float(data["discount_15"]),
            discount_20=float(data["discount_20"]),
            related_services=related,
        )


@dataclass(frozen=True)
class ServiceMatch:
    service: ServiceRecord
    score: float
    matched_term: str | None = None


def _normalize_text(text: str) -> str:
    """Normalize Arabic/English text for comparison."""
    if not text:
        return ""
    text = unicodedata.normalize("NFKC", text)
    text = text.lower().strip()
    text = re.sub(r"[\u0640]", "", text)  # tatweel
    text = re.sub(r"[إأآا]", "ا", text)
    text = re.sub(r"[ىي]", "ي", text)
    text = re.sub(r"ة", "ه", text)
    text = re.sub(r"\s+", " ", text)
    return text


def _catalog_path() -> Path:
    configured = get_settings().services_catalog_path
    if configured:
        path = Path(configured)
        if not path.is_absolute():
            path = Path(__file__).resolve().parents[2] / path
        return path
    return DEFAULT_CATALOG_PATH


@lru_cache(maxsize=1)
def load_catalog() -> list[ServiceRecord]:
    path = _catalog_path()
    if not path.exists():
        logger.error("Services catalog not found at %s", path)
        return []
    with open(path, encoding="utf-8") as f:
        payload = json.load(f)
    services = payload.get("services") or []
    return [ServiceRecord.from_dict(item) for item in services if isinstance(item, dict)]


def reload_catalog() -> list[ServiceRecord]:
    load_catalog.cache_clear()
    return load_catalog()


def _phrase_hint_scores(query: str) -> dict[str, float]:
    """Deterministic high-confidence matches from known Arabic/English phrases."""
    normalized = _normalize_text(query)
    if not normalized:
        return {}
    scores: dict[str, float] = {}
    for phrase, service_name in sorted(PHRASE_HINTS, key=lambda item: len(item[0]), reverse=True):
        norm_phrase = _normalize_text(phrase)
        if norm_phrase and norm_phrase in normalized:
            current = scores.get(service_name, 0.0)
            scores[service_name] = max(current, PHRASE_MATCH_SCORE)
    return scores


def _term_match_score(normalized_query: str, norm_term: str) -> float:
    if not norm_term:
        return 0.0
    if norm_term in normalized_query or normalized_query in norm_term:
        return 100.0 + ALIAS_SUBSTRING_BOOST
    if len(norm_term) <= SHORT_ALIAS_MAX_LEN:
        pattern = r"(?<!\w)" + re.escape(norm_term) + r"(?!\w)"
        if re.search(pattern, normalized_query):
            return 100.0 + ALIAS_SUBSTRING_BOOST
        return 0.0
    partial = fuzz.partial_ratio(norm_term, normalized_query)
    token = fuzz.token_set_ratio(norm_term, normalized_query)
    return float(max(partial, token))


def _score_service(service: ServiceRecord, query: str) -> ServiceMatch:
    normalized_query = _normalize_text(query)
    if not normalized_query:
        return ServiceMatch(service=service, score=0.0)

    phrase_scores = _phrase_hint_scores(query)
    phrase_score = phrase_scores.get(service.name, 0.0)

    best_score = phrase_score
    best_term: str | None = service.name if phrase_score else None

    candidates = list(service.aliases) + [service.arabic_name, service.name]
    for term in candidates:
        if not term:
            continue
        norm_term = _normalize_text(term)
        if not norm_term:
            continue

        score = _term_match_score(normalized_query, norm_term)
        if score > best_score:
            best_score = score
            best_term = term

    return ServiceMatch(service=service, score=best_score, matched_term=best_term)


def search_services(query: str, *, top_k: int = 3, min_score: float = MATCH_THRESHOLD) -> list[ServiceMatch]:
    """Return services ranked by fuzzy relevance to *query*."""
    catalog = load_catalog()
    if not catalog or not (query or "").strip():
        return []

    scored = [_score_service(service, query) for service in catalog]
    scored.sort(key=lambda m: m.score, reverse=True)
    return [m for m in scored[:top_k] if m.score >= min_score]


def build_conversation_query(
    *,
    transcript: str = "",
    summary: str = "",
    pain_points: list[str] | None = None,
    objections: list[str] | None = None,
    buying_signals: list[str] | None = None,
    extra: list[str] | None = None,
) -> str:
    """Aggregate conversation signals into one search string."""
    parts: list[str] = []
    if summary:
        parts.append(summary)
    if transcript:
        parts.append(transcript)
    for group in (pain_points, objections, buying_signals, extra):
        if group:
            parts.extend(str(item).strip() for item in group if str(item).strip())
    return " ".join(parts)


def detect_services_from_conversation(
    *,
    transcript: str = "",
    summary: str = "",
    pain_points: list[str] | None = None,
    objections: list[str] | None = None,
    buying_signals: list[str] | None = None,
    top_k: int = 3,
) -> list[ServiceMatch]:
    """Intent detection: rank services by relevance to the full conversation."""
    query = build_conversation_query(
        transcript=transcript,
        summary=summary,
        pain_points=pain_points,
        objections=objections,
        buying_signals=buying_signals,
    )
    matches = search_services(query, top_k=top_k)
    logger.info(
        "Service search query length=%d, top match=%s (score=%.1f)",
        len(query),
        matches[0].service.arabic_name if matches else "none",
        matches[0].score if matches else 0,
    )
    return matches


def _format_price(value: float) -> str:
    return f"{value:,.2f}"


def format_service_offer(service: ServiceRecord, *, highlight_discount: str = "discount_15") -> str:
    """Format a single service block for LLM context (Arabic)."""
    discount_map = {
        "discount_10": ("خصم 10%", service.discount_10, service.base_price - service.discount_10),
        "discount_15": ("خصم 15%", service.discount_15, service.base_price - service.discount_15),
        "discount_20": ("خصم 20%", service.discount_20, service.base_price - service.discount_20),
    }
    label, price, savings = discount_map.get(highlight_discount, discount_map["discount_15"])
    lines = [
        f"الخدمة: {service.arabic_name} ({service.name})",
        f"السعر الأساسي: {_format_price(service.base_price)} ريال",
        f"نطاق الأسعار: من {_format_price(service.min_price)} إلى {_format_price(service.max_price)} ريال",
        f"عرض {label}: {_format_price(price)} ريال (توفير {_format_price(savings)} ريال)",
        f"عرض خصم 10%: {_format_price(service.discount_10)} ريال",
        f"عرض خصم 15%: {_format_price(service.discount_15)} ريال",
        f"عرض خصم 20%: {_format_price(service.discount_20)} ريال",
    ]
    if service.related_services:
        lines.append(f"خدمات ذات صلة: {', '.join(service.related_services)}")
    return "\n".join(lines)


def format_catalog_context(matches: list[ServiceMatch]) -> str:
    """Build Arabic pricing context for follow-up / analysis prompts."""
    if not matches:
        return "لا توجد خدمة مطابقة في كتالوج الأسعار. استخدم لغة عامة دون اختراع أسعار."

    primary = matches[0]
    blocks = [
        "═══ الخدمة الأكثر صلة بالمحادثة ═══",
        format_service_offer(primary.service),
    ]
    if len(matches) > 1:
        blocks.append("\n═══ خدمات أخرى ذُكرت أو قد تكون ذات صلة ═══")
        for match in matches[1:]:
            blocks.append(format_service_offer(match.service))
    return "\n\n".join(blocks)


def get_service_by_name(name: str) -> ServiceRecord | None:
    """Exact lookup by canonical or Arabic name."""
    norm = _normalize_text(name)
    for service in load_catalog():
        if _normalize_text(service.name) == norm or _normalize_text(service.arabic_name) == norm:
            return service
    return None
