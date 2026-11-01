from pathlib import Path

from meli_collector.parse import parse_detail_html, parse_list_scripts

ROOT = Path(__file__).resolve().parents[1]


def test_list_fixture_extracts_public_card_fields():
    rows = parse_list_scripts((ROOT / "fixtures" / "listing_scripts.txt").read_text(encoding="utf-8"))
    assert len(rows) == 2
    assert rows[0]["title"] == "Stainless steel bottle"
    assert rows[0]["rating"] == 4.8
    assert rows[0]["sold_min"] >= 500
    assert rows[0]["item_id"].startswith("MLM")
    assert rows[0]["canonical_url"].startswith("https://")


def test_detail_fixture_extracts_product_snapshot():
    row = parse_detail_html((ROOT / "fixtures" / "item.html").read_text(encoding="utf-8"))
    assert row["item_id"] == "MLM1234567890"
    assert row["product_id"] == "MLM987654321"
    assert row["title"] == "Stainless steel bottle"
    assert row["price"] == 799
    assert row["rating"] == 4.8
    assert row["reviews_count"] == 128
    assert row["sold_min"] >= 500
    assert row["seller"] == "Example Store"
    assert row["category_path"]


def test_site_mapping_works_for_brazil():
    raw = '{"id":"POLYCARD","polycard":{"metadata":{"id":"MLB1234567890"},"components":[]}}'
    row = parse_list_scripts(raw, "MLB")[0]
    assert row["canonical_url"].startswith("https://produto.mercadolivre.com.br/")


def test_page2_url_has_noindex_suffix():
    import inspect
    from meli_collector import browser
    src = inspect.getsource(browser)
    # plain _Desde_N redirects back to page 1 on Mercado Libre (verified live 2026-11-02)
    assert "_NoIndex_True" in src
