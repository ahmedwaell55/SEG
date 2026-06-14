"""Tests for JSON catalog fuzzy service matching."""

from app.services.service_search import (
    detect_services_from_conversation,
    get_service_by_name,
    reload_catalog,
    search_services,
)


def setup_module() -> None:
    reload_catalog()


def test_arabic_seo_aliases():
    matches = search_services("نحتاج تحسين محركات البحث للموقع", top_k=1)
    assert matches
    assert matches[0].service.name == "SEO"


def test_seo_shorthand():
    matches = search_services("السيو مهم عندنا", top_k=1)
    assert matches
    assert matches[0].service.name == "SEO"


def test_ecommerce_store():
    matches = search_services("أبغى متجر إلكتروني", top_k=1)
    assert matches
    assert matches[0].service.name == "إنشاء متجر"


def test_ads_campaign():
    matches = search_services("نفكر في الإعلانات على سناب", top_k=1)
    assert matches
    assert matches[0].service.name == "الحملات الإعلانية"


def test_conversation_ranks_primary_service():
    matches = detect_services_from_conversation(
        transcript="العميل يسأل عن السيو والإعلانات لكن التركيز على محركات البحث",
        summary="اهتمام بتحسين الظهور",
        top_k=2,
    )
    assert matches
    assert matches[0].service.name == "SEO"


def test_catalog_loads_all_services():
    from app.services.service_search import load_catalog

    assert len(load_catalog()) == 13


def test_get_service_by_name():
    service = get_service_by_name("باقة سباق")
    assert service is not None
    assert service.base_price == 2971.4


def test_english_meeting_summary_karima():
    summary = (
        "Karima is interested in building a strong brand and creating a sustainable system "
        "for long-term growth. Rahma has explained the benefits of a professional online store "
        "and the importance of paid advertising to generate qualified customers."
    )
    matches = detect_services_from_conversation(summary=summary, top_k=3)
    assert matches
    names = {m.service.name for m in matches}
    assert "إنشاء متجر" in names
    assert "الحملات الإعلانية" in names
    assert matches[0].service.name == "إنشاء متجر"


def test_seo_not_false_positive_on_english_prose():
    summary = (
        "Karima is interested in building a strong brand and creating a sustainable system "
        "for long-term growth."
    )
    matches = search_services(summary, top_k=1)
    assert not matches or matches[0].service.name != "SEO"
