from meli_collector.store import Store


def _card(item_id, sold, price=100.0):
    return {"item_id": item_id, "title": "Faja", "price": price, "sold_min": sold, "sold_bucket_text": f"Más de {sold} vendidos", "is_ad": False}


def test_item_falls_back_to_listing_and_growth_uses_listings(tmp_path):
    with Store(tmp_path / "t.db") as st:
        st.insert_listings("faja", [_card("MLM1", 100)], ts="2026-11-01T03:30:00+00:00")
        st.insert_listings("faja", [_card("MLM1", 500, 99.0)], ts="2026-11-08T03:30:00+00:00")
        item = st.latest_item("MLM1")
        assert item["source"] == "listing" and item["sold_min"] == 500 and item["price"] == 99.0
        g = st.growth("MLM1")
        assert g[0]["sold_delta"] == 400 and g[0]["previous_ts"].startswith("2026-11-01")
        assert st.latest_item("MLM404") is None
