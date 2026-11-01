# meli-collector

`meli-collector` is a small, general-purpose Mercado Libre snapshot collector. It uses a Scrapling browser session backed by a browser profile that **you** logged into manually, parses search cards and product pages, stores timestamped snapshots in SQLite, and exposes a read-only local HTTP API.

中文简介：这是一个通用的美客多搜索列表/商品页快照采集器。使用 Scrapling 登录态浏览器会话，数据保存到 SQLite，并提供 CLI 与只读本地 API。

## Scope and responsible use

Collect only public pages that you are authorized to access. Follow Mercado Libre terms, local law, and reasonable request rates. This project does not solve CAPTCHAs or account-verification challenges. If a challenge is detected, collection stops and the CLI returns `needs_human` for a person to review.

## Install

Python 3.10+ is required. A virtual environment is recommended:

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -e ".[test]"
```

## First login and configuration

1. Set `MELI_PROFILE_DIR` to a browser profile directory that you control.
2. Launch a visible session once (for example with `MELI_HEADLESS=0`) and manually sign in in the browser window.
3. Close the session after the login is complete; future runs reuse that profile.

Environment variables:

| Variable | Default | Meaning |
|---|---|---|
| `MELI_PROFILE_DIR` | required | Browser profile directory; login is manual |
| `MELI_SITE` | `MLM` | `MLM`, `MLA`, `MLB`, `MCO`, or `MLC` |
| `MELI_DB` | `data/meli.db` | SQLite database path |
| `MELI_API_PORT` | `18731` | Local API port |
| `MELI_HEADLESS` | `0` | Set `1` for headless operation after login |
| `MELI_WINDOW_POSITION` | unset | Optional browser window position, e.g. `0,0` |
| `MELI_WINDOW_SIZE` | unset | Optional browser window size, e.g. `1440,900` |

## CLI

```powershell
python cli.py search "stainless bottle" --pages 1
python cli.py item MLM1234567890
python cli.py watch --file keywords.txt --pages 1
python cli.py export --format json > latest.json
```

`--site`, `--profile-dir`, and `--db` override the corresponding environment variables. Search and item commands write snapshots; `export` only reads SQLite.

## Read-only API

```powershell
python api.py
curl.exe --max-time 10 http://127.0.0.1:18731/health
curl.exe --max-time 10 "http://127.0.0.1:18731/search?kw=stainless%20bottle"
curl.exe --max-time 10 http://127.0.0.1:18731/item/MLM1234567890
curl.exe --max-time 10 http://127.0.0.1:18731/growth/MLM1234567890
```

The API has no write endpoints. It reads the database selected by `MELI_DB`.

## Stored fields

Listing snapshots contain item/product IDs, title, current and previous price, discount, currency, seller label, official-store flag, rating, sold bucket, shipping flags, canonical URL, ad flag, position, keyword, and timestamp. Product snapshots additionally contain review count, condition, stock hint, sold lower bound, and category path. JSON arrays are stored as JSON text in SQLite and decoded by the API/CLI.

## Why this project is different

Many existing GitHub `mercadolibre-scraper` projects are tiny (often at or below two stars), rely on anonymous requests or a single HTML pass, and can be stopped by a login wall. This project instead keeps a user-owned logged-in browser session, supports five country site mappings, preserves timestamped SQLite history, and makes verification-wall handling explicit. It is intentionally smaller than hosted scraping services and does not include proxies, CAPTCHA solving, or account automation.

## Support / 打赏

Send each coin only on the network listed next to its address (wrong-network transfers cannot be recovered):

- USDT-TRC20: TNGdTwE6opH6rmUyoG1JUR7FSyEb4k273R
- USDT (ERC20/BEP20/Polygon) & ETH (Ethereum/Arbitrum/Base): 0x59c43144a862b351fa1086ae842d1327c9d91613
- BTC: 1RS6tWXHregLfEsiPzVUCUBuhgDg5uTSV
- USDT-Solana: HZguEXfTtLChNdJTxAYCbcGscaqikz8JYrEpUhEyeVd9

## License

MIT © 2026 Tommyapi
