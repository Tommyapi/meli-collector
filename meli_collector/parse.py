"""Pure parsers for Mercado Libre search-card and product-page payloads."""

from __future__ import annotations

import json
import re
from html import unescape
from typing import Any, Iterable

from .config import get_site

_ID_RE = re.compile(r"\b(ML[MACB]|MCO|MLC)-?([0-9]{5,})\b", re.I)
_NUMBER_RE = re.compile(r"([0-9]+(?:[.,][0-9]+)?)\s*(mil|k|m)?", re.I)


def _norm_id(value: Any) -> str | None:
    if not value:
        return None
    m = _ID_RE.search(str(value))
    return f"{m.group(1).upper()}{m.group(2)}" if m else str(value)


def _number(value: Any) -> float | None:
    if value is None:
        return None
    text = str(value).strip().replace("\u00a0", " ")
    m = _NUMBER_RE.search(text.replace(" ", ""))
    if not m:
        return None
    raw = m.group(1)
    if "." in raw and "," in raw:
        raw = raw.replace(",", "")
    elif "," in raw:
        left, right = raw.split(",", 1)
        raw = f"{left}.{right}" if len(right) <= 2 else left + right
    try:
        number = float(raw)
    except ValueError:
        return None
    suffix = (m.group(2) or "").lower()
    if suffix in {"mil", "k"}:
        number *= 1000
    elif suffix == "m":
        number *= 1_000_000
    return number


def sold_min_from_text(text: Any) -> int | None:
    if not text:
        return None
    matches = list(_NUMBER_RE.finditer(unescape(str(text)).lower().replace(" ", "")))
    if not matches:
        return None
    number = _number(matches[-1].group(0))
    return int(number) if number is not None else None


def _json_text(text: str) -> str:
    return text.replace(r'\"', '"').replace(r"\u002F", "/").replace(r"\u0026", "&")


def _component_map(components: Iterable[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {str(c.get("type") or c.get("id")): c for c in components if isinstance(c, dict)}


def _component_text(component: dict[str, Any] | None) -> str:
    if not component:
        return ""
    for key in ("text", "alt_text", "label"):
        value = component.get(key)
        if isinstance(value, str):
            return value
        if isinstance(value, dict) and isinstance(value.get("text"), str):
            return value["text"]
    for value in component.values():
        if isinstance(value, dict):
            found = _component_text(value)
            if found:
                return found
        elif isinstance(value, list):
            for child in value:
                if isinstance(child, dict):
                    found = _component_text(child)
                    if found:
                        return found
    return ""


def _canonical(item_id: str | None, url: str | None, product_id: str | None, site: str) -> str | None:
    cfg = get_site(site)
    if url and "click1." not in url and cfg.item_host in url:
        return url if url.startswith("http") else "https://" + url
    if item_id:
        m = _ID_RE.search(item_id)
        if m:
            return f"https://{cfg.item_host}/{m.group(1).upper()}-{m.group(2)}"
    if product_id:
        return f"https://{cfg.home_host}/p/{product_id}"
    return None


def _parse_card(card: dict[str, Any], position_fallback: int, site: str) -> dict[str, Any] | None:
    polycard = card.get("polycard", card)
    if not isinstance(polycard, dict):
        return None
    metadata = polycard.get("metadata") or {}
    item_id = _norm_id(metadata.get("id") or metadata.get("item_id"))
    if not item_id:
        return None
    product_id = _norm_id(metadata.get("product_id"))
    components = _component_map(polycard.get("components") or [])
    title_obj = components.get("title", {}).get("title", {})
    title = title_obj.get("text") if isinstance(title_obj, dict) else None
    seller_obj = components.get("seller", {}).get("seller", {})
    seller = ""
    official = False
    if isinstance(seller_obj, dict):
        for value in seller_obj.get("values") or []:
            label = (value.get("label") or {}).get("text") if isinstance(value, dict) else None
            if label:
                seller = label
            icon = (value.get("icon") or {}).get("alt_text", "") if isinstance(value, dict) else ""
            official = official or "oficial" in str(icon).lower() or "cockade" in str(value).lower()
        if not seller:
            seller = str(seller_obj.get("text") or "").replace("{label}", "").strip()
        official = official or "oficial" in str(seller_obj).lower()
    seller = re.sub(r"\{[^}]+\}", "", seller).strip()
    review = components.get("review_compacted", {}).get("review_compacted", {})
    review_text = str(review.get("alt_text") or "")
    rating = None
    for source in [review_text] + [str(v.get("label", {}).get("text", "")) for v in review.get("values", []) if isinstance(v, dict)]:
        match = re.search(r"(?:calificaci[oó]n\s*)?([0-5](?:[.,][0-9])?)", source, re.I)
        if match:
            rating = float(match.group(1).replace(",", "."))
            break
    price_obj = components.get("price", {}).get("price", {})
    current = price_obj.get("current_price") or {}
    previous = (price_obj.get("price_labels") or [{}])[0]
    original = next((v.get("price", {}).get("value") for v in previous.get("values") or [] if isinstance(v, dict) and isinstance(v.get("price"), dict)), None)
    shipping_text = json.dumps(components.get("shipping_v2") or {}, ensure_ascii=False).lower()
    highlight = polycard.get("float_highlight_generic", {}).get("highlight", {}).get("text")
    badges = [highlight] if highlight else []
    if isinstance(components.get("highlight"), dict):
        text = _component_text(components["highlight"])
        if text and text not in badges:
            badges.append(text)
    sold_min = sold_min_from_text(review_text)
    if sold_min is None and isinstance(metadata.get("tracks", {}).get("sold_quantity"), (int, float)):
        sold_min = int(metadata["tracks"]["sold_quantity"])
        review_text = f"+{sold_min} vendidos"
    url = str(metadata.get("url") or "")
    is_ad = str(metadata.get("is_pad", "")).lower() == "true" or "click1." in url or "is_advertising=true" in str(metadata.get("url_fragments"))
    try:
        position = int(metadata.get("item_position"))
        if position < 1:
            raise ValueError
    except (TypeError, ValueError):
        position = position_fallback
    return {
        "item_id": item_id, "product_id": product_id, "title": title or "", "price": current.get("value"),
        "original_price": original, "discount_pct": price_obj.get("discount_pct"),
        "currency": current.get("currency") or price_obj.get("currency") or "LOCAL",
        "seller": seller, "official_store": bool(official), "rating": rating,
        "sold_bucket_text": review_text, "sold_min": sold_min, "badges": badges,
        "full_shipping": "full" in shipping_text, "free_shipping": "gratis" in shipping_text or "free_shipping" in shipping_text,
        "canonical_url": _canonical(item_id, url, product_id, site), "is_ad": bool(is_ad), "position": position,
    }


def parse_list_scripts(script_text: str, site: str = "MLM") -> list[dict[str, Any]]:
    if not script_text:
        return []
    decoder = json.JSONDecoder()
    cards: dict[str, dict[str, Any]] = {}
    text = _json_text(script_text)
    for match in re.finditer(r'\{"id":"POLYCARD"', text):
        try:
            raw, _ = decoder.raw_decode(text[match.start():])
        except json.JSONDecodeError:
            continue
        parsed = _parse_card(raw, len(cards) + 1, site)
        if parsed and (parsed["item_id"] not in cards or cards[parsed["item_id"]].get("is_ad")):
            cards[parsed["item_id"]] = parsed
    return list(cards.values())


def _extract_initial_state(html: str) -> dict[str, Any] | None:
    try:
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, "html.parser")
        script = soup.find("script", id="__NORDIC_RENDERING_CTX__")
        text = (script.string or script.get_text()) if script else ""
        if "_n.ctx.r=" not in text:
            return None
        start = text.index("_n.ctx.r=") + len("_n.ctx.r=")
        end = text.index(";_n.ctx.r.assets", start)
        payload = json.loads(text[start:end])
        return payload.get("appProps", {}).get("pageProps", {}).get("initialState")
    except Exception:
        return None


def parse_detail_html(html: str, site: str = "MLM") -> dict[str, Any]:
    state = _extract_initial_state(html) or {}
    components = state.get("components") or {}
    header = components.get("header") or {}
    price_obj = (components.get("price") or {}).get("price") or {}
    seller_obj = (components.get("seller_summary") or {}).get("seller") or {}
    filters = str(state.get("filters", ""))
    item_id = _norm_id(filters.split(":", 1)[-1] if ":" in filters else None) or _norm_id((components.get("bookmark") or {}).get("item_id"))
    product_id = _norm_id(state.get("id"))
    reviews = header.get("reviews") or {}
    subtitle = str(header.get("subtitle") or (header.get("subtitle_label") or {}).get("accessibility_text") or "")
    condition = subtitle.split("|", 1)[0].strip() or None
    available = components.get("available_quantity") or {}
    picker = available.get("picker") or {}
    stock_hint = picker.get("description") or (components.get("stock_information") or {}).get("title")
    breadcrumb = components.get("breadcrumb") or {}
    category_path = [((x.get("label") or {}).get("text") or "") for x in breadcrumb.get("categories", []) if isinstance(x, dict)]
    if not state:
        try:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html, "html.parser")
            title_node = soup.select_one("h1.ui-pdp-title") or soup.select_one("h1")
            subtitle_node = soup.select_one(".ui-pdp-subtitle")
            price_node = soup.select_one(".ui-pdp-price__second-line .andes-money-amount__fraction")
            canonical = (soup.find("meta", property="og:url") or {}).get("content", "")
            match = _ID_RE.search(canonical or "")
            item_id = item_id or _norm_id(match.group(0) if match else None)
            sold_text = subtitle_node.get_text(" ", strip=True) if subtitle_node else ""
            return {"item_id": item_id, "product_id": product_id, "title": title_node.get_text(" ", strip=True) if title_node else "", "price": _number(price_node.get_text() if price_node else None), "seller": "", "rating": None, "reviews_count": None, "sold_text": sold_text, "sold_min": sold_min_from_text(sold_text), "condition": None, "stock_hint": None, "category_path": []}
        except Exception:
            pass
    return {"item_id": item_id, "product_id": product_id, "title": header.get("title") or "", "price": price_obj.get("value"), "seller": seller_obj.get("name") or "", "rating": reviews.get("rating"), "reviews_count": reviews.get("amount"), "sold_text": subtitle, "sold_min": sold_min_from_text(subtitle), "condition": condition, "stock_hint": stock_hint, "category_path": category_path}


parse_list_page = parse_list_scripts
parse_item_page = parse_detail_html
