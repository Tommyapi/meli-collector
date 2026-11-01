from meli_collector.store import Store


def test_store_round_trip(tmp_path):
    with Store(tmp_path / "snapshots.db") as store:
        store.insert_listings("bottle", [{"item_id": "MLM1", "title": "Bottle", "badges": [], "official_store": False, "full_shipping": False, "free_shipping": True, "is_ad": False, "position": 1}], ts="2026-01-01T00:00:00+00:00")
        assert store.latest_listings("bottle")[0]["item_id"] == "MLM1"
