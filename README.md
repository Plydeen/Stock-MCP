# Massive MCP Server (CSV + Charts)

Standalone FastMCP server that exposes [Massive](https://massive.com) (Polygon) market data to Claude and other MCP clients. Chart tools return **chart-ready CSV**; lookup tools return compact JSON.

## Tools

### CSV / chart tools

| Tool | Description |
|------|-------------|
| `get_stock_bars_csv` | OHLCV bars for a stock via REST API |
| `get_options_bars_csv` | OHLCV bars for an options contract via REST API |
| `get_flat_file_bars_csv` | OHLCV bars from Massive Flat Files (S3 bulk data) |

CSV columns: `datetime,open,high,low,close,volume,transactions`

### Research tools (JSON)

| Tool | Description |
|------|-------------|
| `search_tickers` | Find symbols by name or ticker |
| `get_ticker_details` | Company / instrument metadata |
| `get_stock_snapshot` | Latest price snapshot (paid plan) |
| `list_options_contracts` | Options chain contract lookup |
| `get_options_chain_snapshot` | Full chain snapshot (paid plan) |
| `list_flat_file_datasets` | Flat file catalog and S3 listing |
| `get_market_movers` | Top gainers or losers (paid plan) |

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

1. Deploy the MCP server (local, VPS, or via Cloudflare Tunnel).
2. In a Claude Project, add a remote MCP server with your `/mcp` URL.
3. Add to your project instructions:

> For charts, call `get_stock_bars_csv` or `get_flat_file_bars_csv` and parse the `csv` field. Always mention `truncated` and the date range in your analysis.

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `MASSIVE_API_KEY` | Yes | REST API key |
| `MASSIVE_S3_ACCESS_KEY` | Flat files only | S3 access key from Massive dashboard |
| `MASSIVE_S3_SECRET_KEY` | Flat files only | S3 secret key |
| `MAX_CSV_ROWS` | No | Row cap per CSV tool call (default 5000) |
| `MCP_PORT` | No | Host port for Docker (default 8082) |

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
