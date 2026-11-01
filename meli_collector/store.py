"""SQLite persistence for timestamped Mercado Libre snapshots."""

from __future__ import annotations

import csv
import io
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

LISTING_COLUMNS = ["item_id", "product_id", "title", "price", "original_price", "discount_pct", "currency", "seller", "official_store", "rating", "sold_bucket_text", "sold_min", "badges", "full_shipping", "free_shipping", "canonical_url", "is_ad"]
ITEM_COLUMNS = ["item_id", "product_id", "title", "price", "seller", "rating", "reviews_count", "sold_text", "sold_min", "condition", "stock_hint", "category_path"]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class Store:
    def __init__(self, path: str | Path = "data/meli.db") -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.path)
        self.conn.row_factory = sqlite3.Row
        self.init_schema()

    def close(self) -> None:
        self.conn.close()

    def __enter__(self) -> "Store":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def init_schema(self) -> None:
        self.conn.executescript("""
        CREATE TABLE IF NOT EXISTS listings_snapshot (
          ts TEXT NOT NULL, keyword TEXT NOT NULL, position INTEGER,
          item_id TEXT NOT NULL, product_id TEXT, title TEXT, price REAL,
          original_price REAL, discount_pct REAL, currency TEXT, seller TEXT,
          official_store INTEGER, rating REAL, sold_bucket_text TEXT,
          sold_min INTEGER, badges TEXT, full_shipping INTEGER,
          free_shipping INTEGER, canonical_url TEXT, is_ad INTEGER
        );
        CREATE INDEX IF NOT EXISTS idx_listings_kw_ts ON listings_snapshot(keyword, ts);
        CREATE INDEX IF NOT EXISTS idx_listings_item_ts ON listings_snapshot(item_id, ts);
        CREATE TABLE IF NOT EXISTS items_snapshot (
          ts TEXT NOT NULL, item_id TEXT NOT NULL, product_id TEXT, title TEXT,
          price REAL, seller TEXT, rating REAL, reviews_count INTEGER,
          sold_text TEXT, sold_min INTEGER, condition TEXT, stock_hint TEXT,
          category_path TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_items_item_ts ON items_snapshot(item_id, ts);
        CREATE VIEW IF NOT EXISTS latest_items AS
          SELECT i.* FROM items_snapshot i
          JOIN (SELECT item_id, MAX(ts) ts FROM items_snapshot GROUP BY item_id) x
            ON x.item_id=i.item_id AND x.ts=i.ts;
        CREATE VIEW IF NOT EXISTS sold_growth AS
          WITH ordered AS (
            SELECT item_id, ts, sold_min,
                   LAG(ts) OVER (PARTITION BY item_id ORDER BY ts) previous_ts,
                   LAG(sold_min) OVER (PARTITION BY item_id ORDER BY ts) previous_sold_min
            FROM items_snapshot WHERE sold_min IS NOT NULL
          )
          SELECT item_id, ts, sold_min, previous_ts, previous_sold_min,
                 CASE WHEN previous_sold_min IS NULL THEN NULL ELSE sold_min - previous_sold_min END AS sold_delta
          FROM ordered;
        """)
        self.conn.commit()

    def insert_listings(self, keyword: str, rows: Iterable[dict[str, Any]], ts: str | None = None) -> int:
        timestamp = ts or utc_now()
        sql = "INSERT INTO listings_snapshot (ts, keyword, position, " + ",".join(LISTING_COLUMNS) + ") VALUES (?,?,?," + ",".join("?" for _ in LISTING_COLUMNS) + ")"
        count = 0
        for row in rows:
            values = [row.get(column) for column in LISTING_COLUMNS]
            for column in ("badges",):
                index = LISTING_COLUMNS.index(column)
                values[index] = json.dumps(values[index] or [], ensure_ascii=False)
            for column in ("official_store", "full_shipping", "free_shipping", "is_ad"):
                index = LISTING_COLUMNS.index(column)
                values[index] = int(bool(values[index]))
            self.conn.execute(sql, [timestamp, keyword, row.get("position"), *values])
            count += 1
        self.conn.commit()
        return count

    def insert_items(self, rows: Iterable[dict[str, Any]], ts: str | None = None) -> int:
        timestamp = ts or utc_now()
        sql = "INSERT INTO items_snapshot (ts," + ",".join(ITEM_COLUMNS) + ") VALUES (?," + ",".join("?" for _ in ITEM_COLUMNS) + ")"
        count = 0
        for row in rows:
            values = [row.get(column) for column in ITEM_COLUMNS]
            values[ITEM_COLUMNS.index("category_path")] = json.dumps(values[ITEM_COLUMNS.index("category_path")] or [], ensure_ascii=False)
            self.conn.execute(sql, [timestamp, *values])
            count += 1
        self.conn.commit()
        return count

    @staticmethod
    def _row(row: sqlite3.Row | None) -> dict[str, Any] | None:
        if row is None:
            return None
        data = dict(row)
        for key in ("badges", "category_path"):
            if key in data and isinstance(data[key], str):
                try:
                    data[key] = json.loads(data[key])
                except json.JSONDecodeError:
                    pass
        for key in ("official_store", "full_shipping", "free_shipping", "is_ad"):
            if key in data and data[key] is not None:
                data[key] = bool(data[key])
        return data

    def latest_listings(self, keyword: str | None = None, limit: int = 200) -> list[dict[str, Any]]:
        if keyword:
            rows = self.conn.execute("""SELECT l.* FROM listings_snapshot l
              JOIN (SELECT item_id, MAX(ts) ts FROM listings_snapshot WHERE keyword=? GROUP BY item_id) x
                ON x.item_id=l.item_id AND x.ts=l.ts WHERE l.keyword=? ORDER BY l.position LIMIT ?""", (keyword, keyword, limit)).fetchall()
        else:
            rows = self.conn.execute("""SELECT l.* FROM listings_snapshot l
              JOIN (SELECT item_id, MAX(ts) ts FROM listings_snapshot GROUP BY item_id) x
                ON x.item_id=l.item_id AND x.ts=l.ts ORDER BY l.ts DESC, l.position LIMIT ?""", (limit,)).fetchall()
        return [self._row(row) for row in rows if row]

    def latest_item(self, item_id: str) -> dict[str, Any] | None:
        """Latest detail-page snapshot, else the latest listing-card snapshot (watch runs only collect listings)."""
        out = self._row(self.conn.execute("SELECT * FROM latest_items WHERE item_id=? ORDER BY ts DESC LIMIT 1", (item_id,)).fetchone())
        if out is not None:
            out.setdefault("source", "item")
            return out
        out = self._row(self.conn.execute("SELECT * FROM listings_snapshot WHERE item_id=? ORDER BY ts DESC, is_ad ASC LIMIT 1", (item_id,)).fetchone())
        if out is not None:
            out["source"] = "listing"
            out["sold_text"] = out.get("sold_bucket_text")
        return out

    def growth(self, item_id: str, limit: int = 100) -> list[dict[str, Any]]:
        """sold_min deltas between consecutive snapshots, combining detail pages and listing cards."""
        rows = self.conn.execute(
            """
            WITH pts AS (
              SELECT ts, MAX(sold_min) sold_min FROM (
                SELECT ts, sold_min FROM items_snapshot WHERE item_id=? AND sold_min IS NOT NULL
                UNION ALL
                SELECT ts, sold_min FROM listings_snapshot WHERE item_id=? AND sold_min IS NOT NULL
              ) GROUP BY ts
            ), ordered AS (
              SELECT ts, sold_min, LAG(ts) OVER (ORDER BY ts) previous_ts, LAG(sold_min) OVER (ORDER BY ts) previous_sold_min FROM pts
            )
            SELECT ? AS item_id, ts, sold_min, previous_ts, previous_sold_min,
                   CASE WHEN previous_sold_min IS NULL THEN NULL ELSE sold_min - previous_sold_min END AS sold_delta
            FROM ordered ORDER BY ts DESC LIMIT ?
            """,
            (item_id, item_id, item_id, limit),
        ).fetchall()
        return [self._row(row) for row in rows if row]

    def export_rows(self, fmt: str) -> str:
        rows = self.latest_listings(limit=10000)
        if fmt == "json":
            return json.dumps(rows, ensure_ascii=False, indent=2)
        if fmt != "csv":
            raise ValueError("format must be json or csv")
        output = io.StringIO()
        fields = list(rows[0].keys()) if rows else ["item_id"]
        writer = csv.DictWriter(output, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({key: json.dumps(value, ensure_ascii=False) if isinstance(value, (list, dict)) else value for key, value in row.items()})
        return output.getvalue()
