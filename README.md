# Massive MCP Server (CSV + Charts)

Standalone FastMCP server that exposes [Massive](https://massive.com) (Polygon) market data to Claude and other MCP clients. Chart tools return **chart-ready CSV**; lookup tools return compact JSON.

## Tools

### CSV / chart tools

| Tool | Description |
|------|-------------|
| `get_stock_bars_csv` | OHLCV bars for a stock via REST API |
| `get_options_bars_csv` | OHLCV bars for an options contract via REST API (`O:` prefix optional) |
| `get_flat_file_bars_csv` | OHLCV bars from Massive Flat Files (S3 bulk data) |
| `get_technical_indicator_csv` | SMA / EMA / RSI / MACD series for a stock or option contract, oldest first for overlays |
| `get_trades_csv` | Tick-level trades for an option contract or stock *(requires trades entitlement)* |
| `get_quotes_csv` | Historical NBBO bid/ask quotes with mid + spread *(requires quotes entitlement)* |

Bar CSV columns: `datetime,open,high,low,close,volume,transactions`

### Options tools

| Tool | Description |
|------|-------------|
| `list_options_contracts` | Contract reference lookup with exact or ranged expiration/strike filters, `expired` + `as_of` for backtests |
| `get_option_contract_details` | Spec for one contract (exercise style, shares per contract, primary exchange) |
| `get_option_contract_snapshot` | One contract: IV, greeks, OI, day bar, quote/trade when entitled; flat `summary` + raw payload |
| `get_options_chain_snapshot` | Filtered chain (type, expiration window, strike band), auto-paginated up to 2500 contracts; `output=rows\|csv\|raw`; put/call volume + OI `summary` |
| `get_unified_snapshot` | Up to 250 mixed stock + option tickers in one call (multi-leg pricing) |
| `get_previous_day_bar` | Previous session OHLCV + VWAP (stock or option) |
| `get_daily_open_close` | Open/close plus pre-market and after-hours for one date (stock or option) |
| `get_last_trade` | Most recent trade *(requires trades entitlement)* |
| `screen_long_calls_from_chain` | Runs the long-call risk/reward screen directly on live chain snapshots, ranked by payoff ratio |

Snapshot rows report per-share prices. `mark` is the best available price (quote mid → FMV → last trade → session close → previous close) and `mark_source` says which one was used. Plans without quote entitlement return no bid/ask, so spread discipline can't be checked.

### Research tools (JSON)

| Tool | Description |
|------|-------------|
| `search_tickers` | Find symbols by name or ticker |
| `get_ticker_details` | Company / instrument metadata |
| `get_stock_snapshot` | Latest price snapshot (paid plan) |
| `list_flat_file_datasets` | Flat file catalog and S3 listing |
| `get_market_movers` | Top gainers or losers (paid plan) |
| `get_market_status` | Current open/closed/extended-hours status |
| `get_market_holidays` | Upcoming holidays and early closes |
| `list_exchanges` | Exchange reference (maps exchange IDs in trades/quotes) |
| `list_condition_codes` | Trade/quote condition code reference |
| `analyze_long_call_risk_reward` | Long-call spread + payoff ratio screen (single leg) |
| `analyze_long_call_risk_reward_batch` | Batch long-call screen from chain shortlist |
| `black_scholes_call_greeks` | BS price/greeks or IV solve when snapshot greeks are null |
| `covered_call_sim` | Covered-call P/L across a price × eval-date grid for 1..N scenarios. Premium and IV come from the live contract snapshot (bid / market IV) unless overridden. Returns long-format CSV + per-scenario metrics |

## Local Setup

```bash
cd Stock-MCP
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Edit `.env`:

```env
MASSIVE_API_KEY=your_rest_api_key
MASSIVE_S3_ACCESS_KEY=your_flat_files_access_key   # optional, for flat files
MASSIVE_S3_SECRET_KEY=your_flat_files_secret_key
```

Run locally:

```bash
fastmcp run app/mcp_server.py --transport http --host 127.0.0.1 --port 8082
```

MCP endpoint:

```text
http://127.0.0.1:8082/mcp
```

## Docker on Linux VPS

```bash
cp .env.example .env
# edit .env
docker compose -f deploy/docker-compose.yml up -d --build
```

The service binds to localhost:

```text
http://127.0.0.1:8082/mcp
```

## Traefik (recommended for VPS)

Expose the MCP server via Traefik with TLS. The container joins the external `traefik-public` network and is routed at your domain.

1. Create DNS A record: `mcp.kowens.tech` → your VPS IP.
2. Ensure Traefik is running with `providers.docker.network=traefik-public`.
3. Deploy:

```bash
docker compose -f deploy/docker-compose.yml up -d --build
```

Public MCP URL:

```text
https://mcp.kowens.tech/mcp
```

## OAuth for Claude Custom Connectors (recommended)

Claude Desktop / Claude.ai **Custom Connectors** use OAuth in the UI — clients do **not** edit config files. Stock-MCP uses FastMCP's OAuth proxy, which speaks MCP OAuth to Claude while authenticating users via GitHub or Google.

**Do not use Traefik Basic Auth with OAuth.** Basic Auth blocks MCP's `401` + discovery headers. The default `deploy/docker-compose.yml` has no Basic Auth middleware.

### 1. Create a GitHub OAuth App

1. GitHub → **Settings → Developer settings → OAuth Apps → New OAuth App**
2. **Homepage URL:** `https://mcp.kowens.tech`
3. **Authorization callback URL:** `https://mcp.kowens.tech/auth/callback`
4. Copy **Client ID** and generate a **Client secret**

For Google, use [Google Cloud Console](https://console.cloud.google.com/) with the same callback URL and set `MCP_OAUTH_PROVIDER=google`.

### 2. Configure `.env`

```env
MCP_AUTH_MODE=oauth
MCP_PUBLIC_BASE_URL=https://mcp.kowens.tech
MCP_OAUTH_PROVIDER=github
MCP_OAUTH_CLIENT_ID=your_github_client_id
MCP_OAUTH_CLIENT_SECRET=your_github_client_secret
# Recommended: openssl rand -base64 32
MCP_OAUTH_JWT_SIGNING_KEY=your_random_signing_key
```

### 3. Deploy

```bash
docker compose -f deploy/docker-compose.yml up -d --build
```

Verify discovery (should return JSON, not `401` from Traefik):

```bash
curl -s https://mcp.kowens.tech/.well-known/oauth-protected-resource/mcp | head
```

### 4. Client setup (no config files)

In **Claude Desktop** or **Claude.ai**:

1. **Settings → Connectors → Add custom connector**
2. **Name:** `Stock MCP` (any label)
3. **Remote MCP server URL:** `https://mcp.kowens.tech/mcp`
4. Leave **OAuth Client ID** and **OAuth Client Secret** blank (the server proxy handles registration)
5. Click **Add** → sign in with GitHub (or Google) when prompted

Clients never see your Massive API keys or server `.env` — they only complete OAuth.

### Legacy Basic Auth (N8N, scripts)

For tools that only support HTTP Basic Auth, use the optional Traefik overlay:

```bash
docker compose -f deploy/docker-compose.yml -f deploy/docker-compose.basic-auth.yml up -d
```

Set `MCP_AUTH_MODE=basic` and `MCP_BASIC_AUTH_USERS` in `.env`. **This is incompatible with Claude Custom Connectors.**

```bash
htpasswd -nbB mcp 'your-password' | sed 's/\$/\$\$/g'
```

## Cloudflare Tunnel (optional)

Expose the MCP server to Claude Projects without opening a public port on the VPS.

1. Create a remotely managed tunnel in Cloudflare Zero Trust.
2. Set `CLOUDFLARE_TUNNEL_TOKEN` in `.env`.
3. Add a public hostname route: `mcp-stocks.yourdomain.com` → `http://stock-mcp:8080`
4. Start with the tunnel profile:

```bash
docker compose -f deploy/docker-compose.yml --profile tunnel up -d --build
```

Claude remote MCP URL:

```text
https://mcp-stocks.yourdomain.com/mcp
```

## Claude Integration

1. Deploy with OAuth (see above).
2. Add a **Custom Connector** with `https://mcp.kowens.tech/mcp` (no config file editing).
3. Add to your project instructions:

> For charts, call `get_stock_bars_csv` or `get_flat_file_bars_csv` and parse the `csv` field. Always mention `truncated` and the date range in your analysis. For options, always filter `get_options_chain_snapshot` by expiration and strike band; use `output=csv` to chart IV smile or open interest by strike.

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `MASSIVE_API_KEY` | Yes | REST API key |
| `MASSIVE_S3_ACCESS_KEY` | Flat files only | S3 access key from Massive dashboard |
| `MASSIVE_S3_SECRET_KEY` | Flat files only | S3 secret key |
| `MAX_CSV_ROWS` | No | Row cap per CSV tool call (default 5000) |
| `MCP_PORT` | No | Host port for Docker (default 8082) |
| `MCP_AUTH_MODE` | No | `oauth` (default for public), `basic`, or `none` |
| `MCP_PUBLIC_BASE_URL` | OAuth | Public origin, e.g. `https://mcp.kowens.tech` |
| `MCP_OAUTH_PROVIDER` | OAuth | `github` or `google` |
| `MCP_OAUTH_CLIENT_ID` | OAuth | OAuth app client ID |
| `MCP_OAUTH_CLIENT_SECRET` | OAuth | OAuth app client secret |
| `MCP_OAUTH_JWT_SIGNING_KEY` | OAuth (recommended) | Stable key for token signing across restarts |
| `MCP_BASIC_AUTH_USERS` | Basic Auth overlay | htpasswd line for Traefik middleware |

## Testing

```bash
pytest tests/ -v
```

Optional integration tests (requires real API keys in `.env`):

```bash
RUN_INTEGRATION=1 pytest tests/test_integration.py -v
```

## Security

- Keep `.env` off Git; use `chmod 600 .env` on the VPS.
- Bind to `127.0.0.1` unless behind Cloudflare Tunnel or nginx.
- Do not log API keys.
- Consider Cloudflare WAF rate limiting on the public MCP hostname.

## API Reference Docs

- [`Rest_API_docs.md`](Rest_API_docs.md) — Massive REST API
- [`flat_files_docs.md`](flat_files_docs.md) — Massive Flat Files (S3)
