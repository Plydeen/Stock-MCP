# Massive REST API — Complete Reference

> **Base URL:** `https://api.massive.com`  
> **Protocol:** HTTPS  
> **Data Format:** JSON  
> **Authentication:** API Key (query string or Bearer token)

---

## Table of Contents

1. [Overview](#overview)
2. [Authentication](#authentication)
3. [Response Format](#response-format)
4. [Client Libraries](#client-libraries)
5. [Asset Categories Summary](#asset-categories-summary)
6. [Stocks API (46 endpoints)](#stocks-api)
7. [Options API (19 endpoints)](#options-api)
8. [Futures API (9 endpoints)](#futures-api)
9. [Indices API (13 endpoints)](#indices-api)
10. [Forex API (19 endpoints)](#forex-api)
11. [Crypto API (20 endpoints)](#crypto-api)
12. [Economy API (4 endpoints)](#economy-api)
13. [Alternative Data API (2 endpoints)](#alternative-data-api)
14. [Partners API (15 endpoints)](#partners-api)
15. [Infrastructure & Data Flow](#infrastructure--data-flow)
16. [Pricing Plans](#pricing-plans)

---

## Overview

The **Massive REST API** delivers historical and real-time financial market data over HTTPS. It is designed for on-demand queries and request/response integrations across a broad set of asset classes:

- **Stocks** — All 19 U.S. exchanges, dark pools, FINRA TRFs, OTC markets
- **Options** — All 17 U.S. options exchanges via OPRA
- **Futures** — CME, CBOT, COMEX, NYMEX
- **Indices** — 10,000+ indices (S&P, Nasdaq, Dow Jones, MSCI, FTSE Russell, Cboe, and more)
- **Forex** — Global currency pairs, 24/5
- **Crypto** — Global digital assets, 24/7
- **Economy** — Federal Reserve macroeconomic indicators
- **Alternative** — European consumer spending (Fable Data)
- **Partners** — Benzinga, ETF Global, TMX/Wall Street Horizon

For bulk historical downloads, use **Flat Files**. For live streams, use the **WebSocket API**.

---

## Authentication

You must include your unique API key with every request. It can be provided in two ways:

### Option 1: Query String Parameter

https://api.massive.com/v3/reference/dividends?apiKey=YOUR_API_KEY

### Option 2: Authorization Header (Bearer Token)

```http
GET /v3/reference/dividends HTTP/1.1
Host: api.massive.com
Authorization: Bearer YOUR_API_KEY
```

### Getting Your API Key

1. Sign up or log in at [massive.com](https://massive.com)
2. Visit your **Dashboard** to find your API key
3. Keep your API key **secure** — do not share it publicly

> **Pro Tip:** Omitting or using an invalid API key returns an authorization error.

---

## Response Format

All REST endpoints return structured **JSON**. The root-level envelope is consistent across all endpoints:

```json
{
  "results": [
    {
      "cash_amount": 0.25,
      "currency": "USD",
      "declaration_date": "2024-10-31",
      "dividend_type": "CD",
      "ex_dividend_date": "2024-11-08",
      "frequency": 4,
      "id": "E416a068758f...",
      "pay_date": "2024-11-14",
      "record_date": "2024-11-11",
      "ticker": "AAPL"
    }
  ],
  "status": "OK",
  "request_id": "5a8e1e551dc3a1c2c203744543b40399"
}
```

| Field        | Type   | Description                                      |
|--------------|--------|--------------------------------------------------|
| `results`    | Array  | Array of data objects (trades, quotes, tickers, etc.) |
| `status`     | String | `"OK"` on success, error message otherwise       |
| `request_id` | String | Unique identifier for the request (for support)  |
| `count`      | Number | Number of results returned (present on many endpoints) |

---

## Client Libraries

While manual HTTPS requests work fine, official client libraries are recommended for production use. They handle authentication, request formatting, retry logic, and JSON parsing.

| Language   | Repository                          |
|------------|-------------------------------------|
| Python     | GitHub — Python Client              |
| Go         | GitHub — Go Client                  |
| Kotlin/JVM | GitHub — JVM Client                 |
| JavaScript | GitHub — JavaScript Client          |

---

## Asset Categories Summary

| Category    | Endpoint Count | Free Tier | Paid Plans Start At |
|-------------|---------------|-----------|---------------------|
| Stocks      | 46            | Yes       | $29/mo              |
| Options     | 19            | Yes       | $29/mo              |
| Futures     | 9             | Yes       | $29/mo              |
| Indices     | 13            | Yes       | $49/mo              |
| Forex       | 19            | Yes       | $49/mo              |
| Crypto      | 20            | Yes       | $49/mo              |
| Economy     | 4             | Yes (all plans) | Included       |
| Alternative | 2             | No        | $99/mo              |
| Partners    | 15            | No        | $99/mo              |

---

## Stocks API

**Coverage:** All 19 U.S. stock exchanges, FINRA trading facilities, OTC markets, and dark pools.  
**Timezone:** Eastern Time (ET) — timestamps returned as Unix UTC.  
**Market Sessions:**
- Pre-Market: 4:00 AM – 9:30 AM ET
- Regular: 9:30 AM – 4:00 PM ET
- After-Hours: 4:00 PM – 8:00 PM ET

**Data Sources:** SIP feeds (CTA for Tapes A & B, UTP/Nasdaq for Tape C), direct exchange feeds, FINRA ATS reporting.  
**Infrastructure:** Equinix NJ (primary, co-located with exchanges) + ORD11 Chicago (redundancy).

---

### Tickers

#### All Tickers
**GET** `/v3/reference/tickers`  
Retrieve a comprehensive list of ticker symbols across all asset classes (stocks, indices, forex, crypto). Includes symbol, name, market, currency, and active status.  
**Use Cases:** Asset discovery, data integration, filtering/selection, application development.  
**Plan:** Stocks Basic (Free)+

#### Ticker Overview
**GET** `/v3/reference/tickers/{ticker}`  
Deep details for a single active ticker: primary exchange, CIK, composite FIGI, share class FIGI, market cap, industry classification, key dates, and branding assets (logos, icons). For delisted tickers, use All Tickers with `active=false`.  
**Use Cases:** Company research, data integration, application enhancement, due diligence & compliance.  
**Plan:** Stocks Basic (Free)+

#### Ticker Types
**GET** `/v3/reference/tickers/types`  
List of all ticker types supported by Massive, categorized across asset classes, markets, and instruments.  
**Use Cases:** Data classification, filtering mechanisms, educational reference, system integration.  
**Plan:** Stocks Basic (Free)+

#### Related Tickers
**GET** `/v1/related-companies/{ticker}`  
Tickers related to a given ticker, identified via news coverage and returns analysis. Useful for peer and competitor discovery.  
**Use Cases:** Peer identification, comparative analysis, portfolio diversification, market research.  
**Plan:** Stocks Basic (Free)+

---

### Aggregate Bars (OHLC)

#### Custom Bars
**GET** `/v2/aggs/ticker/{stocksTicker}/range/{multiplier}/{timespan}/{from}/{to}`  
Historical OHLC + volume aggregates over a custom date range and time interval (ET). Only qualifying trades are included. Empty intervals indicate no eligible trades. Supports pre-market, regular, and after-hours sessions.  
**Parameters:** `multiplier` (e.g., `5`), `timespan` (e.g., `minute`, `hour`, `day`), `from` (date), `to` (date)  
**Use Cases:** Data visualization, technical analysis, backtesting, market research.  
**Plan:** Stocks Basic (Free)+

#### Daily Market Summary
**GET** `/v2/aggs/grouped/locale/us/market/stocks/{date}`  
OHLC, volume, and VWAP for all U.S. stocks on a single trading date — entire market in one request.  
**Use Cases:** Market overview, bulk data processing, historical research, portfolio comparison.  
**Plan:** Stocks Basic (Free)+

#### Daily Ticker Summary
**GET** `/v1/open-close/{stocksTicker}/{date}`  
Opening and closing prices for a specific stock on a given date, including pre-market and after-hours prices.  
**Use Cases:** Daily performance analysis, historical data collection, after-hours insights, portfolio tracking.  
**Plan:** Stocks Basic (Free)+

#### Previous Day Bar
**GET** `/v2/aggs/ticker/{stocksTicker}/prev`  
Previous trading day's OHLC + volume for a specific ticker.  
**Use Cases:** Baseline comparison, technical analysis, market research, daily reporting.  
**Plan:** Stocks Basic (Free)+

---

### Snapshots

#### Single Ticker Snapshot
**GET** `/v2/snapshot/locale/us/markets/stocks/tickers/{stocksTicker}`  
Most recent snapshot for a single ticker: latest trade, quote, and aggregated data (minute, day, previous day). Cleared at 3:30 AM EST, repopulated from 4:00 AM EST.  
**Use Cases:** Focused monitoring, real-time analysis, price alerts, investor relations.  
**Plan:** Stocks Starter ($29/mo)+

#### Full Market Snapshot
**GET** `/v2/snapshot/locale/us/markets/stocks/tickers`  
Comprehensive snapshot of 10,000+ actively traded U.S. tickers in a single response. Cleared at 3:30 AM EST.  
**Use Cases:** Market overview, bulk data processing, heat maps/dashboards, automated monitoring.  
**Plan:** Stocks Starter ($29/mo)+

#### Unified Snapshot
**GET** `/v3/snapshot`  
Snapshots across multiple asset classes (stocks, options, forex, crypto) in one request. Returns last trade, last quote, OHLC, and volume.  
**Use Cases:** Cross-market analysis, diversified portfolio monitoring, global market insights, multi-asset trading strategies.  
**Plan:** Stocks Starter ($29/mo)+

#### Top Market Movers
**GET** `/v2/snapshot/locale/us/markets/stocks/{direction}`  
Top 20 gainers or losers by percentage change from previous close. Only tickers with minimum 10,000 volume are included. `direction` = `gainers` or `losers`.  
**Use Cases:** Market movers identification, trading strategies, market sentiment analysis, portfolio adjustments.  
**Plan:** Stocks Starter ($29/mo)+

---

### Trades & Quotes

#### Trades
**GET** `/v3/trades/{stockTicker}`  
Tick-level trade data for a ticker in a defined time range. Each record includes price, size, exchange, conditions, and precise timestamps. Foundational for OHLC construction.  
**Use Cases:** Intraday analysis, algorithmic trading, market microstructure research, compliance.  
**Plan:** Stocks Starter ($29/mo)+

#### Last Trade
**GET** `/v2/last/trade/{stocksTicker}`  
Most recent available trade: price, size, exchange, and timestamp.  
**Use Cases:** Trade monitoring, price updates, market snapshot.  
**Plan:** Stocks Starter ($29/mo)+

#### Quotes (NBBO)
**GET** `/v3/quotes/{stockTicker}`  
Historical National Best Bid and Offer (NBBO) quotes over a defined time range. Includes bid/ask prices, sizes, exchanges, and timestamps.  
**Use Cases:** Historical quote analysis, liquidity evaluation, algorithmic backtesting, strategy refinement.  
**Plan:** Stocks Starter ($29/mo)+

#### Last Quote (NBBO)
**GET** `/v2/last/nbbo/{stocksTicker}`  
Most recent NBBO quote: bid/ask prices, sizes, exchange details, and timestamp.  
**Use Cases:** Price display, spread analysis, market monitoring.  
**Plan:** Stocks Starter ($29/mo)+

---

### Technical Indicators

#### SMA — Simple Moving Average
**GET** `/v1/indicators/sma/{stockTicker}`  
Average price across N periods, smoothing fluctuations to reveal trends.  
**Use Cases:** Trend analysis, SMA crossover signals, support/resistance identification, entry/exit timing.  
**Plan:** Stocks Basic (Free)+

#### EMA — Exponential Moving Average
**GET** `/v1/indicators/ema/{stockTicker}`  
Moving average weighted toward recent prices for faster trend detection.  
**Use Cases:** Trend identification, EMA crossover signals, dynamic support/resistance, volatility-adjusted strategies.  
**Plan:** Stocks Basic (Free)+

#### MACD — Moving Average Convergence/Divergence
**GET** `/v1/indicators/macd/{stockTicker}`  
Momentum indicator derived from two moving averages. Identifies trend strength, direction, and potential signals.  
**Use Cases:** Momentum analysis, crossover signal generation, overbought/oversold conditions, trend confirmation.  
**Plan:** Stocks Basic (Free)+

#### RSI — Relative Strength Index
**GET** `/v1/indicators/rsi/{stockTicker}`  
Oscillator (0–100) measuring speed and magnitude of price changes. Above 70 = overbought; below 30 = oversold.  
**Use Cases:** Overbought/oversold detection, divergence analysis, trend confirmation, entry/exit strategy refinement.  
**Plan:** Stocks Basic (Free)+

---

### Market Operations

#### Exchanges
**GET** `/v3/reference/exchanges`  
List of all known exchanges with identifiers, names, and market types.  
**Plan:** Stocks Basic (Free)+

#### Market Holidays
**GET** `/v1/marketstatus/upcoming`  
Upcoming market holidays and open/close times. Forward-looking only.  
**Plan:** Stocks Basic (Free)+

#### Market Status
**GET** `/v1/marketstatus/now`  
Current trading status for all exchanges — open, closed, pre-market, or after-hours.  
**Plan:** Stocks Basic (Free)+

#### Condition Codes
**GET** `/v3/reference/conditions`  
Unified list of trade and quote conditions from CTA, UTP, OPRA, and FINRA. Includes how each condition affects OHLC and volume calculations.  
**Plan:** Stocks Basic (Free)+

---

### Corporate Actions

#### IPOs
**GET** `/vX/reference/ipos`  
Comprehensive IPO data from 2008 onward: issuer name, ticker, security type, IPO date, shares offered, price ranges, issue prices, and offering sizes. Filter by status: `pending`, `new`, `rumors`, `historical`.  
**Use Cases:** IPO research, market trend analysis, investment screening, historical event comparison.  
**Plan:** Stocks Basic (Free)+

#### Splits *(Deprecated)*
**GET** `/v3/reference/splits`  
Historical stock split events with execution dates and ratio factors.  
**Plan:** Stocks Basic (Free)+

#### Splits *(Current)*
**GET** `/stocks/v1/splits`  
Historical stock splits with execution dates, ratios, and adjustment factors for normalizing historical prices.  
**Use Cases:** Historical analysis, price adjustments, data consistency, modeling.  
**Plan:** Stocks Basic (Free)+

#### Dividends *(Deprecated)*
**GET** `/v3/reference/dividends`  
Historical cash dividends with declaration, ex-dividend, record, and pay dates plus payout amounts.  
**Plan:** Stocks Basic (Free)+

#### Dividends *(Current)*
**GET** `/stocks/v1/dividends`  
Historical cash dividends with all dates, payout amounts, and adjustment factors for normalizing historical data.  
**Use Cases:** Income analysis, total return calculations, dividend strategies, tax planning.  
**Plan:** Stocks Basic (Free)+

#### Ticker Events
**GET** `/vX/reference/tickers/{id}/events`  
Timeline of key events for a ticker, CUSIP, or Composite FIGI. Covers ticker changes/rebranding. *(Experimental)*  
**Use Cases:** Historical reference for symbol changes, data continuity, record-keeping.  
**Plan:** Stocks Basic (Free)+

---

### Fundamentals

#### Balance Sheets
**GET** `/stocks/financials/v1/balance-sheets`  
Quarterly and annual balance sheet data: assets, liabilities, and equity positions at specific points in time.  
**Use Cases:** Financial analysis, company valuation, asset assessment, debt analysis, equity research.  
**Plan:** Stocks Starter + Financials & Ratios Expansion ($29/mo add-on), or Stocks Developer ($79/mo)+

#### Cash Flow Statements
**GET** `/stocks/financials/v1/cash-flow-statements`  
Quarterly, annual, and TTM cash flows: operating, investing, and financing. TTM sums four quarters of data.  
**Use Cases:** Cash flow analysis, liquidity assessment, operational efficiency, investment activity tracking.  
**Plan:** Stocks Starter + Financials & Ratios Expansion ($29/mo add-on), or Stocks Developer ($79/mo)+

#### Income Statements
**GET** `/stocks/financials/v1/income-statements`  
Revenue, expenses, and net income across quarterly, annual, and TTM periods.  
**Use Cases:** Profitability analysis, revenue trend analysis, expense management, earnings assessment.  
**Plan:** Stocks Starter + Financials & Ratios Expansion ($29/mo add-on), or Stocks Developer ($79/mo)+

#### Ratios
**GET** `/stocks/financials/v1/ratios`  
Valuation, profitability, liquidity, and leverage ratios calculated daily using TTM financials combined with daily stock prices.  
**Use Cases:** Company valuation, comparative analysis, financial health assessment, investment screening.  
**Plan:** Stocks Starter + Financials & Ratios Expansion ($29/mo add-on), or Stocks Developer ($79/mo)+

#### Short Interest
**GET** `/stocks/v1/short-interest`  
Aggregated short interest reported to FINRA by broker-dealers on a two-week cadence. Indicates bearish sentiment and short-squeeze potential.  
**Use Cases:** Market sentiment analysis, short-squeeze prediction, risk management, strategy refinement.  
**Plan:** Stocks Basic (Free)+

#### Short Volume
**GET** `/stocks/v1/short-volume`  
Daily aggregated short sale volume from FINRA off-exchange venues and ATS platforms. Captures daily short-selling activity (vs. outstanding positions).  
**Use Cases:** Intraday sentiment analysis, short-sale trend identification, liquidity analysis, strategy optimization.  
**Plan:** Stocks Basic (Free)+

#### Float
**GET** `/stocks/vX/float`  
Latest free float (shares available for public trading) for a ticker. Excludes insider, restricted, and strategic holdings. Reflects public reporting with potential lag.  
**Use Cases:** Liquidity analysis, volatility modeling, position sizing, market impact estimation, ownership analysis.  
**Plan:** Stocks Basic (Free)+

---

### Filings & Disclosures

#### EDGAR Index
**GET** `/stocks/filings/vX/index`  
Master index of all SEC EDGAR filings: form types, filing dates, CIKs, tickers, issuer names, accession numbers, and links to SEC.gov documents.  
**Use Cases:** Automated filing discovery/monitoring, regulatory compliance alerts, due diligence, competitive intelligence, historical disclosure research.  
**Plan:** Stocks Basic (Free)+

#### 10-K Sections
**GET** `/stocks/filings/10-K/vX/sections`  
Clean plain-text extracts of key 10-K narrative sections (Business, Risk Factors). AI-ready structured format.  
**Use Cases:** NLP/text analysis, automated risk profiling, competitive benchmarking, topic modeling, LLM knowledge base construction.  
**Plan:** Stocks Basic (Free)+

#### 8-K Text
**GET** `/stocks/filings/8-K/vX/text`  
Parsed plain-text of Form 8-K Items sections. Covers major material events: acquisitions, leadership changes, material contracts, and significant developments.  
**Use Cases:** Real-time event detection, event-driven trading, automated news digestion, M&A tracking, corporate action timelines.  
**Plan:** Stocks Basic (Free)+

#### 13-F Filings
**GET** `/stocks/filings/vX/13-F`  
Quarterly institutional holdings from SEC Form 13-F (managers with ≥$100M AUM). Includes equity positions, share counts, market values, investment discretion, and voting authority.  
**Use Cases:** Institutional ownership tracking, hedge fund strategy replication, portfolio overlap analysis, activist monitoring, smart-money flow analysis.  
**Plan:** Stocks Basic (Free)+

#### Risk Factors
**GET** `/stocks/filings/vX/risk-factors`  
Standardized, machine-readable risk factor disclosures from SEC filings. Each factor categorized using a consistent taxonomy for cross-company and cross-time comparison.  
**Use Cases:** Risk trend analysis, cross-company comparison, compliance tools, classification models, investment research.  
**Plan:** Stocks Basic (Free)+

#### Risk Categories
**GET** `/stocks/taxonomies/vX/risk-factors`  
Full hierarchical taxonomy (primary, secondary, tertiary categories) used to classify risk factors. Includes descriptions and examples.  
**Use Cases:** Risk classification models, category-level analytics and dashboards, cross-company comparison, quantitative risk scoring, thematic monitoring.  
**Plan:** Stocks Basic (Free)+

#### Form 3
**GET** `/stocks/filings/vX/form-3`  
SEC Form 3 filings reporting initial beneficial ownership by corporate insiders (directors, officers, 10%+ shareholders). Establishes baseline ownership.  
**Use Cases:** Tracking new insider positions, executive/director ownership monitoring, due diligence, ownership databases, regulatory compliance.  
**Plan:** Stocks Basic (Free)+

#### Form 4
**GET** `/stocks/filings/vX/form-4`  
SEC Form 4 filings disclosing all changes in beneficial ownership by insiders. Must be filed within 2 business days of any transaction. Includes dates, prices, share amounts, and transaction codes.  
**Use Cases:** Real-time insider trading monitoring, management confidence analysis, large trade detection, Section 16 compliance, historical insider behavior studies.  
**Plan:** Stocks Basic (Free)+

#### News
**GET** `/v2/reference/news`  
Recent news articles for a ticker: summaries, source details, sentiment analysis, associated tickers, and publisher metadata.  
**Use Cases:** Market sentiment analysis, investment research, automated monitoring, portfolio strategy refinement.  
**Plan:** Stocks Basic (Free)+

---

## Options API

**Coverage:** All 17 U.S. options exchanges via OPRA (Options Price Reporting Authority).  
**Timezone:** Eastern Time (ET) — timestamps as Unix UTC.  
**Market Hours:** Monday–Friday, 9:30 AM – 4:00 PM ET (primarily regular hours).  
**Data Volume:** ~3 TB of options data processed and stored per trading day.

**Exchanges Covered:**
NYSE American Options, BOX, CBOE, Cboe EDGX, Cboe C2, Cboe BZX, Nasdaq NOM, Nasdaq PHLX, Nasdaq BX, Nasdaq ISE, Nasdaq GEMX, Nasdaq MRX, MIAX Emerald, MIAX Pearl, MIAX Sapphire, MEMX Options (16 listed; OPRA consolidates all 17).

---

### Contracts

#### All Contracts
**GET** `/v3/reference/options/contracts`  
Index of all options contracts (active and expired), filterable by underlying ticker. Includes contract type (call/put), exercise style, expiration, and strike price.  
**Use Cases:** Market availability analysis, strategy development, research and modeling, contract exploration.  
**Plan:** Options Basic (Free)+

#### Contract Overview
**GET** `/v3/reference/options/contracts/{options_ticker}`  
Full details for a specific contract: type, exercise style, expiration, strike, shares per contract, underlying ticker, and primary exchange.  
**Use Cases:** Contract specification reference, option chain analysis, strategy development, portfolio integration.  
**Plan:** Options Basic (Free)+

---

### Aggregate Bars (OHLC)

#### Custom Bars
**GET** `/v2/aggs/ticker/{optionsTicker}/range/{multiplier}/{timespan}/{from}/{to}`  
Historical OHLC + volume for a specific options contract over a custom range and interval. Only qualifying trades included; empty intervals indicate no activity.  
**Use Cases:** Data visualization, technical analysis, backtesting strategies, market research.  
**Plan:** Options Basic (Free)+

#### Daily Ticker Summary
**GET** `/v1/open-close/{optionsTicker}/{date}`  
Opening and closing prices for a specific options contract on a given date, including pre/after-hours prices.  
**Use Cases:** Daily performance analysis, historical data collection, after-hours insights, portfolio tracking.  
**Plan:** Options Basic (Free)+

#### Previous Day Bar
**GET** `/v2/aggs/ticker/{optionsTicker}/prev`  
Previous trading day's OHLC + volume for a specific options contract.  
**Use Cases:** Baseline comparison, technical analysis, market research, daily reporting.  
**Plan:** Options Basic (Free)+

---

### Snapshots

#### Option Contract Snapshot
**GET** `/v3/snapshot/options/{underlyingAsset}/{optionContract}`  
Comprehensive snapshot of a single options contract: break-even price, day-over-day changes, implied volatility, open interest, Greeks (delta, gamma, theta, vega), latest quote and trade, and underlying asset price.  
**Use Cases:** Trade evaluation, market analysis, risk assessment, strategy refinement.  
**Plan:** Options Starter ($29/mo)+

#### Option Chain Snapshot
**GET** `/v3/snapshot/options/{underlyingAsset}`  
Full options chain snapshot for an underlying ticker: all contracts with pricing, Greeks, IV, quotes, trades, and open interest.  
**Use Cases:** Market overview, strategy comparison, research and modeling, portfolio refinement.  
**Plan:** Options Starter ($29/mo)+

#### Unified Snapshot
**GET** `/v3/snapshot`  
Multi-asset snapshot (stocks, options, forex, crypto) in one request.  
**Plan:** Options Starter ($29/mo)+

---

### Trades & Quotes

#### Trades
**GET** `/v3/trades/{optionsTicker}`  
Tick-level trade data for an options ticker: price, size, exchange, conditions, and timestamps.  
**Use Cases:** Intraday analysis, algorithmic trading, market microstructure research, compliance.  
**Plan:** Options Starter ($29/mo)+

#### Last Trade
**GET** `/v2/last/trade/{optionsTicker}`  
Most recent trade for a specific options contract.  
**Use Cases:** Trade monitoring, price updates, market snapshot.  
**Plan:** Options Starter ($29/mo)+

#### Quotes
**GET** `/v3/quotes/{optionsTicker}`  
Historical bid/ask quotes for an options contract: prices, sizes, exchange IDs, and timestamps.  
**Use Cases:** Historical quote analysis, market interest evaluation, algorithmic backtesting, strategy refinement.  
**Plan:** Options Starter ($29/mo)+

---

### Technical Indicators

#### SMA | **GET** `/v1/indicators/sma/{optionsTicker}` — **Plan:** Options Basic (Free)+
#### EMA | **GET** `/v1/indicators/ema/{optionsTicker}` — **Plan:** Options Basic (Free)+
#### MACD | **GET** `/v1/indicators/macd/{optionsTicker}` — **Plan:** Options Basic (Free)+
#### RSI | **GET** `/v1/indicators/rsi/{optionsTicker}` — **Plan:** Options Basic (Free)+

---

### Market Operations

#### Exchanges | **GET** `/v3/reference/exchanges` — **Plan:** Options Basic (Free)+
#### Market Holidays | **GET** `/v1/marketstatus/upcoming` — **Plan:** Options Basic (Free)+
#### Market Status | **GET** `/v1/marketstatus/now` — **Plan:** Options Basic (Free)+
#### Condition Codes | **GET** `/v3/reference/conditions` — **Plan:** Options Basic (Free)+

---

## Futures API

**Coverage:** CME, CBOT, COMEX, NYMEX  
**Timezone:** Central Time (CT) — all data standardized to CT.

**Market Hours:**
- CME & CBOT: Sunday 5:00 PM CT – Friday 5:45 PM CT (daily maintenance varies)
- COMEX & NYMEX: Sunday 5:00 PM CT – Friday 4:00 PM CT
- Crypto Futures (CME): Starting May 29, 2026 — nearly 24/7 with short weekly maintenance window

---

### Contracts

#### Contracts
**GET** `/futures/v1/contracts`  
Full contract index with filters for product code, trade dates, active status, and date. Returns ticker, first/last trade dates, days to maturity, exchange code, order limits. Single contract lookups return full specs: settlement dates, tick sizes, and trading/risk fields. Supports point-in-time lookups.  
**Use Cases:** Historical research, trading system integration, portfolio workflows, risk management.  
**Plan:** All Futures plans (Free)+

#### Products
**GET** `/futures/v1/products`  
Complete futures product universe: product codes, names, exchange IDs, sector, asset class, product type, settlement method, pricing/quotation details. Filterable by name, exchange, sector, asset class, product type, or date.  
**Use Cases:** Product specification, historical product checks, risk management, trading system integration.  
**Plan:** All Futures plans (Free)+

#### Schedules
**GET** `/futures/v1/schedules`  
Trading schedules for futures markets: session open/close times, intraday breaks, and holiday/special event adjustments. Filterable by `session_end_date` or product code. All times in UTC.  
**Use Cases:** Schedule planning, market analysis, strategy alignment, risk and operations management.  
**Plan:** All Futures plans (Free)+

---

### Aggregate Bars (OHLC)

#### Custom Bars
**GET** `/futures/v1/aggs/{ticker}`  
Historical OHLC + volume for a futures contract over a custom range and interval (CT). Constructed from all trades in the period. Empty intervals indicate inactivity.  
**Use Cases:** Market monitoring, technical analysis, backtesting, trading strategy development.  
**Plan:** All Futures plans (Free)+

---

### Snapshots

#### Futures Contracts Snapshot
**GET** `/futures/v1/snapshot`  
Real-time snapshots for a set of futures contracts: latest trade, quote, session metrics (OHLC, volume), and settlement prices. Filterable by ticker or product code with pagination.  
**Use Cases:** Real-time trading systems, intraday analysis, performance monitoring, portfolio valuation.  
**Plan:** Futures Developer ($79/mo)+

---

### Trades & Quotes

#### Trades
**GET** `/futures/v1/trades/{ticker}`  
Tick-level trade data: price, size, session start date, and precise timestamps.  
**Use Cases:** Intraday analysis, algorithmic trading, backtesting, market research.  
**Plan:** Futures Developer ($79/mo)+

#### Quotes
**GET** `/futures/v1/quotes/{ticker}`  
Quote data: best bid/offer prices, sizes, and timestamps.  
**Use Cases:** Liquidity analysis, price discovery, strategy refinement, market research.  
**Plan:** Futures Developer ($79/mo)+

---

### Market Operations

#### Market Status | **GET** `/futures/v1/market-status`  
Real-time status (open, pause, close) for specific futures products with exchange/product codes and evaluation timestamps.  
**Plan:** All Futures plans (Free)+

#### Exchanges | **GET** `/futures/v1/exchanges`  
List of supported futures exchanges with codes, names, and details.  
**Plan:** All Futures plans (Free)+

---

## Indices API

**Coverage:** 10,000+ indices from S&P, Nasdaq, Dow Jones, MSCI, FTSE Russell, Morningstar, Cboe, Societe Generale, and more.  
**Timezone:** Eastern Time (ET) — timestamps as Unix UTC.  
**Market Hours:** Monday–Friday, 9:30 AM – 4:00 PM ET (some indices update pre/after-hours).

**Note:** Indices aggregate from underlying securities — they do not produce trade-based OHLC but index-value-based OHLC.

---

### Tickers
#### All Tickers | **GET** `/v3/reference/tickers` — **Plan:** All Indices plans (Free)+
#### Ticker Overview | **GET** `/v3/reference/tickers/{ticker}` — **Plan:** All Indices plans (Free)+

---

### Aggregate Bars (OHLC)

#### Custom Bars
**GET** `/v2/aggs/ticker/{indicesTicker}/range/{multiplier}/{timespan}/{from}/{to}`  
Historical OHLC and value aggregates for an index over a custom range and interval (ET). Derived from index values, not trades.  
**Use Cases:** Data visualization, market trend analysis, benchmark comparisons, research and modeling.  
**Plan:** All Indices plans (Free)+

#### Previous Day Bar | **GET** `/v2/aggs/ticker/{indicesTicker}/prev` — **Plan:** All Indices plans (Free)+

#### Daily Ticker Summary | **GET** `/v1/open-close/{indicesTicker}/{date}` — **Plan:** All Indices plans (Free)+

---

### Snapshots

#### Indices Snapshot
**GET** `/v3/snapshot/indices`  
Snapshot for one or more indices: current value, recent performance metrics, and trading session details.  
**Use Cases:** Market condition assessment, economic sentiment tracking, portfolio context, integrated analysis.  
**Plan:** Indices Starter ($49/mo)+

#### Unified Snapshot | **GET** `/v3/snapshot` — **Plan:** Indices Starter ($49/mo)+

---

### Technical Indicators
#### SMA | **GET** `/v1/indicators/sma/{indicesTicker}` — **Plan:** All Indices plans (Free)+
#### EMA | **GET** `/v1/indicators/ema/{indicesTicker}` — **Plan:** All Indices plans (Free)+
#### MACD | **GET** `/v1/indicators/macd/{indicesTicker}` — **Plan:** All Indices plans (Free)+
#### RSI | **GET** `/v1/indicators/rsi/{indicesTicker}` — **Plan:** All Indices plans (Free)+

---

### Market Operations
#### Market Holidays | **GET** `/v1/marketstatus/upcoming` — **Plan:** All Indices plans (Free)+
#### Market Status | **GET** `/v1/marketstatus/now` — **Plan:** All Indices plans (Free)+

---

## Forex API

**Coverage:** Global currency pairs from banks, financial institutions, and market makers.  
**Timezone:** All data standardized to UTC.  
**Market Hours:** 24 hours/day, 5 days/week.  

**Note:** Forex OHLC aggregates are generated from quoted bid/ask prices (not executed trades).

---

### Tickers
#### All Tickers | **GET** `/v3/reference/tickers` — **Plan:** Currencies Basic (Free)+
#### Ticker Overview | **GET** `/v3/reference/tickers/{ticker}` — **Plan:** Currencies Basic (Free)+

#### Currency Conversion
**GET** `/v1/conversion/{from}/{to}`  
Real-time currency conversion rates between any two supported currencies. Returns most recent bid/ask and the converted amount.  
**Use Cases:** Cross-border transactions, currency hedging, travel expense planning, dynamic pricing.  
**Plan:** Currencies Starter ($49/mo)+

---

### Aggregate Bars (OHLC)

#### Custom Bars
**GET** `/v2/aggs/ticker/{forexTicker}/range/{multiplier}/{timespan}/{from}/{to}`  
Historical OHLC + volume for a currency pair over a custom range and interval. Generated from quoted bid/ask prices.  
**Plan:** Currencies Basic (Free)+

#### Daily Market Summary | **GET** `/v2/aggs/grouped/locale/global/market/fx/{date}` — **Plan:** Currencies Basic (Free)+
#### Previous Day Bar | **GET** `/v2/aggs/ticker/{forexTicker}/prev` — **Plan:** Currencies Basic (Free)+

---

### Snapshots

#### Single Ticker Snapshot
**GET** `/v2/snapshot/locale/global/markets/forex/tickers/{ticker}`  
Latest snapshot for a single forex pair: quote data and aggregated data (minute, day, previous day). Cleared at 12:00 AM EST.  
**Plan:** Currencies Starter ($49/mo)+

#### Full Market Snapshot | **GET** `/v2/snapshot/locale/global/markets/forex/tickers` — **Plan:** Currencies Starter ($49/mo)+
#### Unified Snapshot | **GET** `/v3/snapshot` — **Plan:** Currencies Starter ($49/mo)+

#### Top Market Movers
**GET** `/v2/snapshot/locale/global/markets/forex/{direction}`  
Top 20 gaining or losing forex pairs by percentage change. Cleared at 12:00 AM EST.  
**Plan:** Currencies Starter ($49/mo)+

---

### Quotes

#### Quotes (BBO)
**GET** `/v3/quotes/{fxTicker}`  
Historical Best Bid and Offer quotes for a forex pair: bid/ask prices, exchange IDs, and timestamps.  
**Plan:** Currencies Starter ($49/mo)+

#### Last Quote
**GET** `/v1/last_quote/currencies/{from}/{to}`  
Most recent bid, ask, exchange, and timestamp for a currency pair.  
**Plan:** Currencies Starter ($49/mo)+

---

### Technical Indicators
#### SMA | **GET** `/v1/indicators/sma/{fxTicker}` — **Plan:** Currencies Basic (Free)+
#### EMA | **GET** `/v1/indicators/ema/{fxTicker}` — **Plan:** Currencies Basic (Free)+
#### MACD | **GET** `/v1/indicators/macd/{fxTicker}` — **Plan:** Currencies Basic (Free)+
#### RSI | **GET** `/v1/indicators/rsi/{fxTicker}` — **Plan:** Currencies Basic (Free)+

---

### Market Operations
#### Exchanges | **GET** `/v3/reference/exchanges` — **Plan:** Currencies Basic (Free)+
#### Market Holidays | **GET** `/v1/marketstatus/upcoming` — **Plan:** Currencies Basic (Free)+
#### Market Status | **GET** `/v1/marketstatus/now` — **Plan:** Currencies Basic (Free)+

---

## Crypto API

**Coverage:** Major global cryptocurrency exchanges (Coinbase, Bitfinex, Bitstamp, Kraken; Binance not active since 2021).  
**Timezone:** All data standardized to UTC.  
**Market Hours:** 24/7 continuous.

**Note:** Crypto markets are decentralized — Massive aggregates directly from each exchange (no single consolidator).

---

### Tickers
#### All Tickers | **GET** `/v3/reference/tickers` — **Plan:** Currencies Basic (Free)+
#### Ticker Overview | **GET** `/v3/reference/tickers/{ticker}` — **Plan:** Currencies Basic (Free)+

---

### Aggregate Bars (OHLC)

#### Custom Bars
**GET** `/v2/aggs/ticker/{cryptoTicker}/range/{multiplier}/{timespan}/{from}/{to}`  
Historical OHLC + volume for a crypto pair over a custom range and interval (UTC). Derived from qualifying trades.  
**Plan:** Currencies Basic (Free)+

#### Daily Market Summary
`GET /v2/aggs/grouped/locale/global/market/fx/{date}`
OHLC, volume, and VWAP for all forex tickers on a specified date in one request.
**Plan:** Currencies Basic (Free)+

#### Previous Day Bar
`GET /v2/aggs/ticker/{forexTicker}/prev`
Previous day's OHLC + volume for a specific currency pair.
**Plan:** Currencies Basic (Free)+

---

### Snapshots

#### Single Ticker Snapshot
`GET /v2/snapshot/locale/global/markets/forex/tickers/{ticker}`
Latest snapshot for a single forex pair: quote data and aggregated data (minute, day, previous day). Cleared at 12:00 AM EST.
**Plan:** Currencies Starter ($49/mo)+

#### Full Market Snapshot
`GET /v2/snapshot/locale/global/markets/forex/tickers`
Comprehensive snapshot of the entire forex market. Cleared at 12:00 AM EST; repopulated from 4:00 AM EST.
**Plan:** Currencies Starter ($49/mo)+

#### Unified Snapshot
`GET /v3/snapshot`
Multi-asset snapshot (stocks, options, forex, crypto).
**Plan:** Currencies Starter ($49/mo)+

#### Top Market Movers
`GET /v2/snapshot/locale/global/markets/forex/{direction}`
Top 20 gaining or losing forex pairs by percentage change from prior close. Cleared at 12:00 AM EST. `{direction}