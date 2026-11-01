"""Runtime configuration and Mercado Libre site metadata."""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class SiteConfig:
    code: str
    locale: str
    timezone: str
    home_host: str
    list_host: str
    item_host: str


SITES = {
    "MLM": SiteConfig("MLM", "es-MX", "America/Mexico_City", "www.mercadolibre.com.mx", "listado.mercadolibre.com.mx", "articulo.mercadolibre.com.mx"),
    "MLA": SiteConfig("MLA", "es-AR", "America/Argentina/Buenos_Aires", "www.mercadolibre.com.ar", "listado.mercadolibre.com.ar", "articulo.mercadolibre.com.ar"),
    "MLB": SiteConfig("MLB", "pt-BR", "America/Sao_Paulo", "www.mercadolivre.com.br", "lista.mercadolivre.com.br", "produto.mercadolivre.com.br"),
    "MCO": SiteConfig("MCO", "es-CO", "America/Bogota", "www.mercadolibre.com.co", "listado.mercadolibre.com.co", "articulo.mercadolibre.com.co"),
    "MLC": SiteConfig("MLC", "es-CL", "America/Santiago", "www.mercadolibre.cl", "listado.mercadolibre.cl", "articulo.mercadolibre.cl"),
}


class ConfigurationError(ValueError):
    """Raised when required runtime configuration is missing or invalid."""


def get_site(value: str | None = None) -> SiteConfig:
    code = (value or os.environ.get("MELI_SITE", "MLM")).strip().upper()
    try:
        return SITES[code]
    except KeyError as exc:
        raise ConfigurationError(f"Unsupported MELI_SITE: {code}; use MLM, MLA, MLB, MCO, or MLC") from exc


def profile_dir(value: str | None = None) -> str:
    path = (value or os.environ.get("MELI_PROFILE_DIR", "")).strip()
    if not path:
        raise ConfigurationError("MELI_PROFILE_DIR is required; point it to a browser profile you logged into manually")
    return path


def db_path(value: str | None = None) -> str:
    return (value or os.environ.get("MELI_DB", "data/meli.db")).strip() or "data/meli.db"


def api_port(value: int | None = None) -> int:
    raw = str(value if value is not None else os.environ.get("MELI_API_PORT", "18731"))
    try:
        port = int(raw)
    except ValueError as exc:
        raise ConfigurationError(f"Invalid MELI_API_PORT: {raw}") from exc
    if not 1 <= port <= 65535:
        raise ConfigurationError("MELI_API_PORT must be between 1 and 65535")
    return port
