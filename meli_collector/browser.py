"""Scrapling browser-session wrapper for an already-authenticated profile."""

from __future__ import annotations

import os
import random
import time
from typing import Any, Callable

from .config import SiteConfig, get_site, profile_dir
from .parse import parse_detail_html, parse_list_scripts


class VerificationWall(RuntimeError):
    """Raised when a human verification page is detected."""


class MeliBrowser:
    def __init__(self, profile: str | None = None, site: str | None = None, max_pages: int = 30, headless: bool | None = None) -> None:
        self.user_data_dir = profile_dir(profile)
        self.site: SiteConfig = get_site(site)
        self.max_pages = max(1, int(max_pages))
        self.headless = bool(headless if headless is not None else os.environ.get("MELI_HEADLESS", "0").lower() in {"1", "true", "yes"})
        self._session = None

    def __enter__(self) -> "MeliBrowser":
        from scrapling.fetchers import StealthySession

        flags: list[str] = []
        if os.environ.get("MELI_WINDOW_POSITION"):
            flags.append(f"--window-position={os.environ['MELI_WINDOW_POSITION']}")
        if os.environ.get("MELI_WINDOW_SIZE"):
            flags.append(f"--window-size={os.environ['MELI_WINDOW_SIZE']}")
        self._session = StealthySession(
            headless=self.headless, real_chrome=True, network_idle=False, timeout=60000,
            user_data_dir=self.user_data_dir, locale=self.site.locale, timezone_id=self.site.timezone,
            extra_flags=flags,
        )
        self._session.__enter__()
        return self

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        if self._session is not None:
            self._session.__exit__(exc_type, exc, tb)
            self._session = None

    @staticmethod
    def _wall(page: Any) -> bool:
        url = str(getattr(page, "url", "") or "").lower()
        if "captcha" in url or "account-verification" in url:
            return True
        try:
            text = str(page.title() or "").lower()
        except Exception:
            text = ""
        return "captcha" in text or "account-verification" in text

    def _run(self, action: Callable[[Any], Any]) -> Any:
        if self._session is None:
            raise RuntimeError("MeliBrowser must be used as a context manager")
        result: dict[str, Any] = {}

        def flow(page: Any) -> None:
            page.set_default_timeout(30000)
            result["value"] = action(page)

        self._session.fetch(f"https://{self.site.home_host}/", wait=1000, page_action=flow)
        return result.get("value")

    def search(self, keywords: str, pages: int = 1) -> list[dict[str, Any]]:
        pages = max(1, min(int(pages), self.max_pages))

        def action(page: Any) -> list[dict[str, Any]]:
            all_rows: list[dict[str, Any]] = []
            slug = "-".join(keywords.strip().split())
            for page_no in range(1, pages + 1):
                url = f"https://{self.site.list_host}/{slug}"
                if page_no > 1:
                    url += f"_Desde_{(page_no - 1) * 48 + 1}_NoIndex_True"  # plain _Desde_N redirects to page 1
                page.goto(url, wait_until="domcontentloaded")
                page.wait_for_timeout(3500)
                if self._wall(page):
                    raise VerificationWall(f"verification wall: {page.url}")
                for _ in range(4):
                    page.mouse.wheel(0, 900)
                    page.wait_for_timeout(500)
                scripts = page.evaluate("() => [...document.querySelectorAll('script')].map(s=>s.textContent||'').filter(t=>t.includes('polycard')).join(' @@@ ')")
                all_rows.extend(parse_list_scripts(scripts or "", self.site.code))
                if page_no < pages:
                    time.sleep(random.uniform(6, 15))
            unique: dict[str, dict[str, Any]] = {}
            for row in all_rows:
                old = unique.get(row["item_id"])
                if old is None or (old.get("is_ad") and not row.get("is_ad")):
                    unique[row["item_id"]] = row
            return list(unique.values())

        return self._run(action)

    def items(self, ids: list[str]) -> list[dict[str, Any]]:
        clean_ids = [str(value).strip().upper().replace("-", "") for value in ids if str(value).strip()]

        def action(page: Any) -> list[dict[str, Any]]:
            rows: list[dict[str, Any]] = []
            for index, item_id in enumerate(clean_ids):
                prefix = item_id[:3]
                page.goto(f"https://{self.site.item_host}/{prefix}-{item_id[3:]}", wait_until="domcontentloaded")
                page.wait_for_timeout(4500)
                if self._wall(page):
                    raise VerificationWall(f"verification wall: {page.url}")
                rows.append(parse_detail_html(page.content(), self.site.code))
                if index + 1 < len(clean_ids):
                    time.sleep(random.uniform(6, 15))
            return rows

        return self._run(action)
