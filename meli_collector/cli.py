"""Command-line entry point for meli-collector."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .browser import MeliBrowser, VerificationWall
from .config import ConfigurationError, db_path, get_site
from .store import Store


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="meli-collector")
    parser.add_argument("--db", default=None, help="SQLite path (or MELI_DB)")
    parser.add_argument("--profile-dir", default=None, help="Browser profile directory (or MELI_PROFILE_DIR)")
    parser.add_argument("--site", default=None, choices=["MLM", "MLA", "MLB", "MCO", "MLC"], help="Mercado Libre site (or MELI_SITE)")
    sub = parser.add_subparsers(dest="command", required=True)
    search = sub.add_parser("search", help="Collect search results")
    search.add_argument("keyword")
    search.add_argument("--pages", type=int, default=1)
    item = sub.add_parser("item", help="Collect product details")
    item.add_argument("item_id", nargs="+")
    watch = sub.add_parser("watch", help="Collect keywords from a file")
    watch.add_argument("--file", required=True)
    watch.add_argument("--pages", type=int, default=1)
    export = sub.add_parser("export", help="Export latest listing snapshot")
    export.add_argument("--format", choices=["json", "csv"], required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    database = db_path(args.db)
    try:
        if args.command == "export":
            with Store(database) as store:
                print(store.export_rows(args.format))
            return 0
        get_site(args.site)
        with Store(database) as store, MeliBrowser(args.profile_dir, args.site) as browser:
            if args.command == "search":
                rows = browser.search(args.keyword, args.pages)
                print(json.dumps({"keyword": args.keyword, "count": store.insert_listings(args.keyword, rows), "rows": rows}, ensure_ascii=False))
            elif args.command == "item":
                rows = browser.items(args.item_id)
                print(json.dumps({"count": store.insert_items(rows), "rows": rows}, ensure_ascii=False))
            else:
                keywords = [line.strip() for line in Path(args.file).read_text(encoding="utf-8").splitlines() if line.strip() and not line.lstrip().startswith("#")]
                result = []
                for keyword in keywords:
                    rows = browser.search(keyword, args.pages)
                    result.append({"keyword": keyword, "count": store.insert_listings(keyword, rows)})
                print(json.dumps(result, ensure_ascii=False))
        return 0
    except VerificationWall as exc:
        status = {"status": "needs_human", "reason": str(exc)}
        Path(database).parent.mkdir(parents=True, exist_ok=True)
        (Path(database).parent / "status.json").write_text(json.dumps(status, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(status, ensure_ascii=False), file=sys.stderr)
        return 2
    except (ConfigurationError, OSError, ValueError) as exc:
        print(f"error: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
