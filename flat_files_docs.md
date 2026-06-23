# Massive Flat Files — Complete Reference

> **Delivery Method:** S3-compatible endpoint (compressed CSV)
> **S3 Endpoint:** `https://files.massive.com`
> **S3 Bucket:** `flatfiles`
> **File Format:** Gzipped CSV (`.csv.gz`) with header row
> **Availability:** Data for each trading day available by ~11:00 AM ET the following day
> **Timestamps:** Unix nanosecond UTC unless otherwise noted

---

## Table of Contents

1. [Overview](#overview)
2. [S3 Access Setup](#s3-access-setup)
   - [AWS S3 CLI](#aws-s3-cli)
   - [Rclone](#rclone)
   - [MinIO](#minio)
   - [Python Boto3 SDK](#python-boto3-sdk)
3. [Dataset Categories Summary](#dataset-categories-summary)
4. [Stocks Flat Files — 4 datasets](#stocks-flat-files)
5. [Options Flat Files — 4 datasets](#options-flat-files)
6. [Futures Flat Files — 16 datasets](#futures-flat-files)
7. [Indices Flat Files — 3 datasets](#indices-flat-files)
8. [Forex Flat Files — 3 datasets](#forex-flat-files)
9. [Crypto Flat Files — 3 datasets](#crypto-flat-files)
10. [Data Conventions & Notes](#data-conventions--notes)

---

## Overview

Massive **Flat Files** deliver extensive historical market data as compressed CSV files via an S3-compatible interface. They are the ideal choice when you need:

- **Bulk historical data** without thousands of REST API calls
- **Backtesting** at scale across full market history
- **Data pipeline ingestion** into data warehouses, research environments, or quantitative systems

For smaller on-demand queries, use the **REST API**. For real-time streams, use the **WebSocket API**.

### Key Facts

- All files are **gzip-compressed CSVs** (`.csv.gz`)
- Every file includes a **header row** identifying each column
- Files are organized by `{asset_class}/{dataset}/{year}/{month}/{YYYY-MM-DD}.csv.gz`
- Data is available by **~11:00 AM ET** the following trading day
- All data is **unadjusted** (except where noted) — prices and volumes are not adjusted for splits, dividends, or other corporate actions. Use the REST API `adjusted=true` flag or apply adjustments manually using the Splits endpoint.

### S3 Path Prefixes by Asset Class

| Asset Class   | S3 Prefix            |
|---------------|----------------------|
| Stocks (SIP)  | `us_stocks_sip`      |
| Options (OPRA)| `us_options_opra`    |
| Futures (CBOT)| `us_futures_cbot`    |
| Futures (CME) | `us_futures_cme`     |
| Futures (NYMEX)| `us_futures_nymex`  |
| Futures (COMEX)| `us_futures_comex`  |
| Indices       | `us_indices`         |
| Forex         | `global_forex`       |
| Crypto        | `global_crypto`      |

---

## S3 Access Setup

### Credentials

Obtain your **S3 Access Key** and **Secret Key** from your [Massive Dashboard](https://massive.com/dashboard). An active subscription with Flat Files access is required.

| Setting        | Value                        |
|----------------|------------------------------|
| Endpoint       | `https://files.massive.com`  |
| Bucket Name    | `flatfiles`                  |

---

### AWS S3 CLI

**Install:** [AWS CLI official site](https://aws.amazon.com/cli/)

```bash
# Configure credentials
aws configure set aws_access_key_id YOUR_ACCESS_KEY
aws configure set aws_secret_access_key YOUR_SECRET_KEY

# List all files in the bucket
aws s3 ls s3://flatfiles/ --endpoint-url https://files.massive.com

# Download a specific file
aws s3 cp s3://flatfiles/us_stocks_sip/trades_v1/2025/11/2025-11-05.csv.gz . \
  --endpoint-url https://files.massive.com
```

---

### Rclone

**Install:** [rclone.org](https://rclone.org)

```bash
# Create remote configuration
rclone config create s3massive s3 \
  env_auth=false \
  access_key_id=YOUR_ACCESS_KEY \
  secret_access_key=YOUR_SECRET_KEY \
  endpoint=https://files.massive.com

# List files
rclone ls s3massive:flatfiles

# Download a file
rclone copy s3massive:flatfiles/us_stocks_sip/trades_v1/2025/11/2025-11-05.csv.gz .
```

---

### MinIO

**Install:** [MinIO docs](https://min.io/docs/minio/linux/reference/minio-mc.html)

```bash
# Set alias in config (~/.mc/config.json)
mc alias set s3massive https://files.massive.com YOUR_ACCESS_KEY YOUR_SECRET_KEY

# List files
mc ls s3massive/flatfiles

# View first 4 lines of a compressed file
mc cat s3massive/flatfiles/us_stocks_sip/trades_v1/2025/11/2025-11-05.csv.gz | gzcat | head -4

# Download a file
mc cp s3massive/flatfiles/us_stocks_sip/trades_v1/2025/11/2025-11-05.csv.gz .
```

---

### Python Boto3 SDK

**Install:** `pip install boto3`

```python
import boto3
from botocore.config import Config

# Initialize session with credentials
session = boto3.Session(
    aws_access_key_id='YOUR_ACCESS_KEY',
    aws_secret_access_key='YOUR_SECRET_KEY',
)

# Create S3 client pointing to Massive endpoint
s3 = session.client(
    's3',
    endpoint_url='https://files.massive.com',
    config=Config(signature_version='s3v4'),
)

# --- LIST files by prefix ---
paginator = s3.get_paginator('list_objects_v2')

# Available prefixes:
#   'us_stocks_sip'     — U.S. Stocks
#   'us_options_opra'   — U.S. Options
#   'us_futures_cbot'   — Futures (CBOT)
#   'us_futures_cme'    — Futures (CME)
#   'us_futures_nymex'  — Futures (NYMEX)
#   'us_futures_comex'  — Futures (COMEX)
#   'us_indices'        — U.S. Indices
#   'global_forex'      — Global Forex
#   'global_crypto'     — Global Crypto

prefix = 'us_stocks_sip'

for page in paginator.paginate(Bucket='flatfiles', Prefix=prefix):
    for obj in page['Contents']:
        print(obj['Key'])

# --- DOWNLOAD a specific file ---
bucket_name = 'flatfiles'
object_key = 'us_stocks_sip/trades_v1/2025/11/2025-11-05.csv.gz'
local_file_path = './' + object_key.split('/')[-1]

s3.download_file(bucket_name, object_key, local_file_path)
```

---

## Dataset Categories Summary

| Category | Datasets | Free Tier | Paid Plans Start At  | Notes                          |
|----------|:--------:|-----------|----------------------|-------------------------------|
| Stocks   | 4        | No        | $29/mo (Starter)     | History from Sep 10, 2003     |
| Options  | 4        | No        | $29/mo (Starter)     | History from Jun 2, 2014      |
| Futures  | 16       | No        | $29/mo (Starter)     | History from Apr 3, 2017      |
| Indices  | 3        | No        | $49/mo (Starter)     | History from Feb 14, 2023     |
| Forex    | 3        | No        | $49/mo (Starter)     | History from Sep 25, 2009     |
| Crypto   | 3        | No        | $49/mo (Starter)     | History from Nov 1, 2013      |

> **Note:** No Flat Files datasets are included on any free-tier plan. All require a paid subscription.

---

## Stocks Flat Files

**S3 Prefix:** `us_stocks_sip`
**Total Datasets:** 4
**Coverage:** All 19 major U.S. stock exchanges, FINRA trading facilities (NYSE TRF, Nasdaq TRF Carteret, Nasdaq TRF Chicago), and dark pools. Data is consolidated from regulated Securities Information Processors (SIPs).
**Data Note:** All data is **unadjusted**. Use REST API `adjusted=true` or the Splits endpoint to apply adjustments.

**Market Sessions Captured:**
| Session      | Hours (ET)         |
|--------------|--------------------|
| Pre-Market   | 4:00 AM – 9:30 AM  |
| Regular      | 9:30 AM – 4:00 PM  |
| After-Hours  | 4:00 PM – 8:00 PM  |

**Timestamps:** Unix nanoseconds, UTC.

---

### Stocks — Day Aggregates

**S3 Path:** `us_stocks_sip/day_aggs_v1`
**Description:** Candlestick OHLCV data at per-day granularity across all U.S. equities. One file per trading day.
**History:** Records date back to **September 10, 2003**

**Plan Access & History Depth:**

| Plan               | Access     | History  |
|--------------------|------------|----------|
| Stocks Basic (Free)| ✗          | —        |
| Stocks Starter     | End-of-day | 5 years  |
| Stocks Developer   | End-of-day | 10 years |
| Stocks Advanced    | End-of-day | All history |

**Schema:**

| Column         | Type               | Description                                                              |
|----------------|--------------------|--------------------------------------------------------------------------|
| `ticker`       | string             | Exchange symbol (e.g., `AAPL`)                                           |
| `volume`       | number             | Total trading volume for the day                                         |
| `open`         | number             | Opening price for the day                                                |
| `close`        | number             | Closing price for the day                                                |
| `high`         | number             | Highest price during the day                                             |
| `low`          | number             | Lowest price during the day                                              |
| `window_start` | timestamp (integer)| Unix nanosecond timestamp for the start of the aggregate window (UTC)    |
| `transactions` | integer            | Number of transactions during the day                                    |

**Sample Data:**
ticker,volume,open,close,high,low,window_start,transactions
AAPL,4930,200.29,200.5,200.63,200.29,1744792500000000000,129
BCC,248274,61.68,61.99,62.565,61.41,1680033600000000000,1250

---

### Stocks — Minute Aggregates

**S3 Path:** `us_stocks_sip/minute_aggs_v1`
**Description:** Candlestick OHLCV data at per-minute granularity across all U.S. equities. One file per trading day.
**History:** Records date back to **September 10, 2003**

**Plan Access & History Depth:**

| Plan               | Access     | History  |
|--------------------|------------|----------|
| Stocks Basic (Free)| ✗          | —        |
| Stocks Starter     | End-of-day | 5 years  |
| Stocks Developer   | End-of-day | 10 years |
| Stocks Advanced    | End-of-day | All history |

**Schema:**

| Column         | Type               | Description                                                              |
|----------------|--------------------|--------------------------------------------------------------------------|
| `ticker`       | string             | Exchange symbol (e.g., `MSFT`)                                           |
| `volume`       | number             | Total trading volume for the minute                                      |
| `open`         | number             | Opening price for the minute                                             |
| `close`        | number             | Closing price for the minute                                             |
| `high`         | number             | Highest price during the minute                                          |
| `low`          | number             | Lowest price during the minute                                           |
| `window_start` | timestamp (integer)| Unix nanosecond timestamp for the start of the 1-minute window (UTC)     |
| `transactions` | integer            | Number of transactions during the minute                                 |

**Sample Data:**
ticker,volume,open,close,high,low,window_start,transactions
MSFT,1975,276.75,275.52,276.75,275.25,16799904000000000,83
MSFT,2349,275.2,274.46,275.2,274.46,16799904600000000,99

---

### Stocks — Trades

**S3 Path:** `us_stocks_sip/trades_v1`
**Description:** Tick-level, nanosecond-timestamped trade data from all major U.S. exchanges and dark pools (NYSE, Nasdaq, Cboe, FINRA, etc.). One file per trading day.
**History:** Records date back to **September 10, 2003**

**Plan Access & History Depth:**

| Plan               | Access     | History   |
|--------------------|------------|-----------|
| Stocks Basic (Free)| ✗          | —         |
| Stocks Starter     | ✗          | —         |
| Stocks Developer   | End-of-day | 10 years  |
| Stocks Advanced    | End-of-day | All history |

**Schema:**

| Column                 | Type               | Description                                                                                                    |
|------------------------|--------------------|----------------------------------------------------------------------------------------------------------------|
| `ticker`               | string             | Exchange symbol (e.g., `MSFT`)                                                                                 |
| `conditions`           | integer            | List of condition codes (multiple conditions appear comma-separated in quotes). See Trade Conditions reference. |
| `correction`           | integer            | Trade correction indicator                                                                                     |
| `exchange`             | integer            | Exchange ID. See Exchanges reference for mapping.                                                              |
| `id`                   | string             | Trade ID — unique per combination of ticker, exchange, and TRF                                                 |
| `participant_timestamp`| integer            | Nanosecond Unix timestamp when the trade was generated at the exchange                                         |
| `price`                | number             | Trade price — actual dollar value per whole share                                                              |
| `sequence_number`      | integer            | Increasing, unique per ticker symbol; not always sequential; resets each trading day                           |
| `sip_timestamp`        | integer            | Nanosecond Unix timestamp when the SIP received this trade from the exchange                                   |
| `size`                 | number             | Trade size (volume in shares)                                                                                  |
| `tape`                 | integer            | Which tape the ticker is listed on: `1` = Tape A (NYSE), `2` = Tape B (NYSE ARCA/American), `3` = Tape C (Nasdaq) |
| `trf_id`               | integer            | ID for the Trade Reporting Facility where the trade took place                                                 |
| `trf_timestamp`        | integer            | Nanosecond Unix timestamp when the TRF received this trade                                                     |

**Sample Data:**
ticker,conditions,correction,exchange,id,participant_timestamp,price,sequence_number,sip_timestamp,size,tape,trf_id,trf_timestamp
MSFT,"12,37",0,11,1,1679990400018025984,276.16,1550,1679990400018381329,55,3,0,0

---

### Stocks — Quotes

**S3 Path:** `us_stocks_sip/quotes_v1`
**Description:** Top-of-book NBBO quotes with nanosecond timestamps from all major U.S. exchanges and dark pools. One file per trading day.
**History:** Records date back to **September 10, 2003**

**Plan Access & History Depth:**

| Plan               | Access     | History     |
|--------------------|------------|-------------|
| Stocks Basic (Free)| ✗          | —           |
| Stocks Starter     | ✗          | —           |
| Stocks Developer   | ✗          | —           |
| Stocks Advanced    | End-of-day | All history |

**Schema:**

| Column                 | Type               | Description                                                                                                                                                                              |
|------------------------|--------------------|------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| `ticker`               | string             | Exchange symbol                                                                                                                                                                           |
| `ask_exchange`         | integer            | Ask exchange ID                                                                                                                                                                           |
| `ask_price`            | number             | Ask price                                                                                                                                                                                 |
| `ask_size`             | number             | Ask size. **Before Nov 3, 2025:** number of round lots (e.g., 2 = 200 shares). **On/after Nov 3, 2025:** direct share count per SEC MDI Rules. Divide by `round_lot` from Ticker Overview API to convert back. |
| `bid_exchange`         | integer            | Bid exchange ID                                                                                                                                                                           |
| `bid_price`            | number             | Bid price                                                                                                                                                                                 |
| `bid_size`             | number             | Bid size. Same round-lot vs. share-count convention change as `ask_size` above.                                                                                                          |
| `conditions`           | integer            | List of condition codes (comma-separated in quotes if multiple)                                                                                                                          |
| `indicators`           | integer            | List of indicator codes (comma-separated in quotes if multiple)                                                                                                                          |
| `participant_timestamp`| integer            | Nanosecond Unix timestamp when the quote was generated at the exchange                                                                                                                   |
| `sequence_number`      | integer            | Increasing, unique per ticker symbol; resets each trading day                                                                                                                            |
| `sip_timestamp`        | integer            | Nanosecond Unix timestamp when the SIP received this quote                                                                                                                               |
| `tape`                 | integer            | `1` = Tape A (NYSE), `2` = Tape B (NYSE ARCA/American), `3` = Tape C (Nasdaq)                                                                                                          |
| `trf_timestamp`        | integer            | Nanosecond Unix timestamp when the TRF received this quote                                                                                                                               |

> **Important:** `ask_size` and `bid_size` changed semantics on **November 3, 2025** due to SEC MDI Rules. Pre-2025-11-03 values are in round lots; on/after that date they are in shares.

---

## Options Flat Files

**S3 Prefix:** `us_options_opra`
**Total Datasets:** 4
**Coverage:** All 17 U.S. options exchanges via OPRA (Options Price Reporting Authority).

**Exchanges:** NYSE American Options, BOX, CBOE, Cboe EDGX, Cboe C2, Cboe BZX, Nasdaq NOM, Nasdaq PHLX, Nasdaq BX, Nasdaq ISE, Nasdaq GEMX, Nasdaq MRX, MIAX Emerald, MIAX Pearl, MIAX Sapphire, MEMX Options.

**Market Hours:** Monday–Friday, 9:30 AM – 4:00 PM ET (regular hours only).
**Timestamps:** Unix nanoseconds, UTC.

---

### Options — Day Aggregates

**S3 Path:** `us_options_opra/day_aggs_v1`
**Description:** Candlestick OHLCV data at per-day granularity from all U.S. options markets. One file per trading day.
**History:** Records date back to **June 2, 2014**

**Plan Access & History Depth:**

| Plan                   | Access     | History  |
|------------------------|------------|----------|
| Options Basic (Free)   | ✗          | —        |
| Options Starter        | End-of-day | 2 years  |
| Options Developer      | End-of-day | 4 years  |
| Options Advanced       | End-of-day | All history |

**Schema:**

| Column         | Type               | Description                                                    |
|----------------|--------------------|----------------------------------------------------------------|
| `ticker`       | string             | Options contract symbol (e.g., `O:SPY230327P00390000`)         |
| `volume`       | number             | Total trading volume for the day                               |
| `open`         | number             | Opening price                                                  |
| `close`        | number             | Closing price                                                  |
| `high`         | number             | Highest price                                                  |
| `low`          | number             | Lowest price                                                   |
| `window_start` | timestamp (integer)| Unix nanosecond timestamp for start of the aggregate window    |
| `transactions` | integer            | Number of transactions during the day                          |

**Sample Data:**
ticker,volume,open,close,high,low,window_start,transactions
O:SPY230327P00390000,200,11.82,9.83,11.82,8.09,1678680000000000000,62
O:IWM230327C00137000,1,35.77,35.77,35.77,35.77,1679889600000000000,1

---

### Options — Minute Aggregates

**S3 Path:** `us_options_opra/minute_aggs_v1`
**Description:** Candlestick OHLCV data at per-minute granularity from all U.S. options markets.
**History:** Records date back to **June 2, 2014**

**Plan Access & History Depth:**

| Plan                   | Access     | History  |
|------------------------|------------|----------|
| Options Basic (Free)   | ✗          | —        |
| Options Starter        | End-of-day | 2 years  |
| Options Developer      | End-of-day | 4 years  |
| Options Advanced       | End-of-day | All history |

**Schema:** Same columns as Day Aggregates (`ticker`, `volume`, `open`, `close`, `high`, `low`, `window_start`, `transactions`). `window_start` represents the start of a 1-minute window.

---

### Options — Trades

**S3 Path:** `us_options_opra/trades_v1`
**Description:** Tick-level trades with nanosecond timestamps from all U.S. options markets (CBOE, NYSE, Nasdaq, etc.).
**History:** Records date back to **June 2, 2014**

**Plan Access & History Depth:**

| Plan                   | Access     | History  |
|------------------------|------------|----------|
| Options Basic (Free)   | ✗          | —        |
| Options Starter        | ✗          | —        |
| Options Developer      | End-of-day | 4 years  |
| Options Advanced       | End-of-day | All history |

**Schema:**

| Column                 | Type    | Description                                                                                        |
|------------------------|---------|----------------------------------------------------------------------------------------------------|
| `ticker`               | string  | Options contract symbol (e.g., `O:SPY230327P00390000`)                                             |
| `conditions`           | integer | List of condition codes (comma-separated if multiple). See Trade Conditions reference.              |
| `correction`           | integer | Trade correction indicator                                                                         |
| `exchange`             | integer | Exchange ID. See Exchanges reference for mapping.                                                  |
| `participant_timestamp`| integer | Nanosecond Unix timestamp when the trade was generated at the exchange                             |
| `price`                | number  | Trade price — actual dollar value per whole share                                                  |
| `sip_timestamp`        | integer | Nanosecond Unix timestamp when the SIP (OPRA) received this trade                                 |
| `size`                 | number  | Trade size (volume)                                                                                |

**Sample Data:**
ticker,conditions,correction,exchange,participant_timestamp,price,sip_timestamp,size
O:SPY230327P00390000,232,0,312,1678715620948000000,11.82,1678715620948000000,1

---

### Options — Quotes

**S3 Path:** `us_options_opra/quotes_v1`
**Description:** Top-of-book quotes with nanosecond timestamps from all U.S. options markets.
**History:** Records date back to **March 7, 2022**

**Plan Access & History Depth:**

| Plan                   | Access     | History     |
|------------------------|------------|-------------|
| Options Basic (Free)   | ✗          | —           |
| Options Starter        | ✗          | —           |
| Options Developer      | ✗          | —           |
| Options Advanced       | End-of-day | All history |

**Schema:**

| Column            | Type    | Description                                                                                                     |
|-------------------|---------|-----------------------------------------------------------------------------------------------------------------|
| `ticker`          | string  | Options contract symbol                                                                                         |
| `ask_exchange`    | integer | Ask exchange ID                                                                                                 |
| `ask_price`       | number  | Ask price                                                                                                       |
| `ask_size`        | number  | Ask size — number of round lot orders at the given ask price (100 shares per lot; ask_size of 2 = 200 shares)  |
| `bid_exchange`    | integer | Bid exchange ID                                                                                                 |
| `bid_price`       | number  | Bid price                                                                                                       |
| `bid_size`        | number  | Bid size — number of round lot orders at the given bid price                                                    |
| `sequence_number` | integer | Sequence in which events occurred; increasing, unique per ticker; resets each trading day                       |
| `sip_timestamp`   | integer | Nanosecond Unix timestamp when OPRA received this quote                                                         |

**Sample Data:**
ticker,ask_exchange,ask_price,ask_size,bid_exchange,bid_price,bid_size,sequence_number,sip_timestamp
O:SPY241220P00720000,309,326.77,1,309,321.77,1,81779,1680010200067217664

---

## Futures Flat Files

**S3 Prefixes:** `us_futures_cbot`, `us_futures_cme`, `us_futures_nymex`, `us_futures_comex`
**Total Datasets:** 16 (4 dataset types × 4 exchanges)
**Coverage:** CME, CBOT, COMEX, NYMEX — direct exchange feeds.
**Timezone:** Central Time (CT)

**Market Hours:**
| Exchange Group   | Start              | End                |
|------------------|--------------------|--------------------|
| CME & CBOT       | Sunday 5:00 PM CT  | Friday 5:45 PM CT  |
| COMEX & NYMEX    | Sunday 5:00 PM CT  | Friday 4:00 PM CT  |

**History:** Records date back to **April 3, 2017**

---

### Futures Dataset Types

All four dataset types exist for each of the four exchanges (CBOT, CME, NYMEX, COMEX).

#### Dataset Type Matrix

| Dataset Type       | CBOT S3 Path                    | CME S3 Path                    | NYMEX S3 Path                    | COMEX S3 Path                    |
|--------------------|----------------------------------|--------------------------------|----------------------------------|----------------------------------|
| Session Aggregates | `us_futures_cbot/session_aggs_v1`| `us_futures_cme/session_aggs_v1`| `us_futures_nymex/session_aggs_v1`| `us_futures_comex/session_aggs_v1`|
| Minute Aggregates  | `us_futures_cbot/minute_aggs_v1` | `us_futures_cme/minute_aggs_v1` | `us_futures_nymex/minute_aggs_v1` | `us_futures_comex/minute_aggs_v1` |
| Trades             | `us_futures_cbot/trades_v1`      | `us_futures_cme/trades_v1`      | `us_futures_nymex/trades_v1`      | `us_futures_comex/trades_v1`      |
| Quotes             | `us_futures_cbot/quotes_v1`      | `us_futures_cme/quotes_v1`      | `us_futures_nymex/quotes_v1`      | `us_futures_comex/quotes_v1`      |

---

### Futures — Session Aggregates (all 4 exchanges)

**Description:** Candlestick OHLCV data aggregated from all trades during each full trading session. One row per contract per session. Includes dollar volume.

**Plan Access & History Depth:**

| Plan                   | Access     | History  |
|------------------------|------------|----------|
| Futures Basic (Free)   | ✗          | —        |
| Futures Starter        | End-of-day | 2 years  |
| Futures Developer      | End-of-day | 5 years  |
| Futures Advanced       | End-of-day | All history |

**Schema:**

| Column             | Type               | Description                                                                       |
|--------------------|--------------------|-----------------------------------------------------------------------------------|
| `ticker`           | string             | Futures contract symbol (e.g., `1OZZ5-1OZG6`)                                    |
| `exchange`         | integer            | Exchange ID                                                                       |
| `session_end_date` | string             | Trading date — end of the trading session — in `YYYY-MM-DD` format               |
| `window_start`     | timestamp (integer)| Unix nanosecond timestamp for the start of the aggregate window                   |
| `open`             | number             | Opening price for the session                                                     |
| `high`             | number             | Highest price during the session                                                  |
| `low`              | number             | Lowest price during the session                                                   |
| `close`            | number             | Closing price for the session                                                     |
| `volume`           | number             | Total trading volume during the session                                           |
| `dollar_volume`    | number             | Total dollar volume of all transactions in the session (price × volume aggregate) |
| `transactions`     | integer            | Number of transactions during the session                                         |

**Sample Data:**
ticker,exchange,session_end_date,window_start,open,high,low,close,volume,dollar_volume,transactions
1OZZ5-1OZG6,2,2025-08-25,1756082400000,-28,-28,-28,-28,2,-56,1

---

### Futures — Minute Aggregates (all 4 exchanges)

**Description:** Candlestick OHLCV data at per-minute granularity, aggregated from all trades.

**Plan Access & History Depth:** Same as Session Aggregates (Starter: 2 yrs, Developer: 5 yrs, Advanced: All)

**Schema:** Same columns as Session Aggregates but without `dollar_volume`. `window_start` represents a 1-minute window start.

| Column             | Type               | Description                                    |
|--------------------|--------------------|------------------------------------------------|
| `ticker`           | string             | Futures contract symbol                        |
| `exchange`         | integer            | Exchange ID                                    |
| `session_end_date` | string             | Trading date in `YYYY-MM-DD` format            |
| `window_start`     | timestamp (integer)| Unix nanosecond timestamp for 1-minute window  |
| `open`             | number             | Opening price                                  |
| `high`             | number             | Highest price                                  |
| `low`              | number             | Lowest price                                   |
| `close`            | number             | Closing price                                  |
| `volume`           | number             | Trading volume                                 |
| `transactions`     | integer            | Number of transactions                         |

---

### Futures — Trades (all 4 exchanges)

**Description:** Tick-level trades with nanosecond timestamps for each exchange.

**Plan Access & History Depth:**

| Plan                   | Access     | History  |
|------------------------|------------|----------|
| Futures Basic (Free)   | ✗          | —        |
| Futures Starter        | ✗          | —        |
| Futures Developer      | End-of-day | 5 years  |
| Futures Advanced       | End-of-day | All history |

**Schema:**

| Column             | Type               | Description                                                                                    |
|--------------------|--------------------|------------------------------------------------------------------------------------------------|
| `ticker`           | string             | Futures contract symbol                                                                        |
| `timestamp`        | timestamp (integer)| Nanosecond precision timestamp when the trade was generated at the exchange                    |
| `sequence_number`  | integer            | Increasing, unique per ticker; not always sequential; resets each trading session              |
| `conditions`       | string             | List of condition codes (e.g., `[401]`)                                                        |
| `price`            | number             | Trade price — dollar value per whole contract                                                  |
| `size`             | integer            | Total number of contracts exchanged between buyers and sellers                                 |
| `correction`       | integer            | Trade correction indicator                                                                     |
| `exchange`         | integer            | Exchange ID                                                                                    |
| `session_end_date` | string             | Trading date in `YYYY-MM-DD` format                                                            |

**Sample Data:**
ticker,timestamp,sequence_number,conditions,price,size,correction,exchange,session_end_date
0TFV5,1754843586948.6707,27,[401],0.05,1,0,1,2025-08-11
BZ:BF G6-H6-J6,1755006388859.057,381026,[401],0.02,1,0,1,2025-08-12

---

### Futures — Quotes (all 4 exchanges)

**Description:** Top-of-book quotes with nanosecond timestamps for each exchange.

**Plan Access & History Depth:**

| Plan                   | Access     | History  |
|------------------------|------------|----------|
| Futures Basic (Free)   | ✗          | —        |
| Futures Starter        | ✗          | —        |
| Futures Developer      | End-of-day | 5 years  |
| Futures Advanced       | End-of-day | All history |

**Schema:**

| Column             | Type    | Description                                                                                     |
|--------------------|---------|-------------------------------------------------------------------------------------------------|
| `ticker`           | string  | Futures contract symbol                                                                         |
| `timestamp`        | integer | Unix millisecond timestamp of the quote                                                         |
| `ask_timestamp`    | integer | Timestamp when the ask price was submitted to the exchange                                      |
| `ask_price`        | number  | Ask price                                                                                       |
| `ask_size`         | number  | Ask size — number of round lot orders at the ask price (100 shares/lot; size 2 = 200 shares)   |
| `bid_timestamp`    | integer | Timestamp when the bid price was submitted to the exchange                                      |
| `bid_price`        | number  | Bid price                                                                                       |
| `bid_size`         | number  | Bid size — number of round lot orders at the bid price                                          |
| `exchange`         | integer | Exchange ID                                                                                     |
| `session_end_date` | string  | Trading date in `YYYY-MM-DD` format                                                             |

**Sample Data:**
ticker,timestamp,ask_timestamp,ask_price,ask_size,bid_timestamp,bid_price,bid_size,exchange,session_end_date
QMH5-QMJ5,1738623616654.0586,1738623616645.3,0.55,74,1738623614912.2527,0.525,20,1,2025-02-04

> **Note:** `bid_price` and `bid_size` can be `null` when no bid is present.

---

## Indices Flat Files

**S3 Prefix:** `us_indices`
**Total Datasets:** 3
**Coverage:** 10,000+ indices from S&P, Nasdaq, Dow Jones, FTSE Russell, MSCI, Morningstar, Cboe Global Indices (CGI), Cboe CCCY, Societe Generale.
**Market Hours:** Monday–Friday, 9:30 AM – 4:00 PM ET (some indices update pre/after-hours).
**Timestamps:** Unix nanoseconds, UTC.
**History:** Records date back to **February 14, 2023**

**Plan Access & History Depth:**

| Plan                   | Access     | History     |
|------------------------|------------|-------------|
| Indices Basic (Free)   | ✗          | —           |
| Indices Starter        | End-of-day | All history |
| Indices Advanced       | End-of-day | All history |

---

### Indices — Day Aggregates

**S3 Path:** `us_indices/day_aggs_v1`
**Description:** Candlestick data with daily OHLC values aggregated from all ticks throughout each trading day.

**Schema:**

| Column         | Type               | Description                                                    |
|----------------|--------------------|----------------------------------------------------------------|
| `ticker`       | string             | Index symbol (e.g., `I:AAVE100`, `I:XNDXTRND`)                |
| `open`         | number             | Opening value for the day                                      |
| `close`        | number             | Closing value for the day                                      |
| `high`         | number             | Highest value during the day                                   |
| `low`          | number             | Lowest value during the day                                    |
| `window_start` | timestamp (integer)| Unix nanosecond timestamp for start of the aggregate window    |

> **Note:** Indices Day Aggregates do **not** include `volume` or `transactions` columns (indices are not traded directly).

**Sample Data:**
ticker,open,close,high,low,window_start
I:AAVE100,96.767,99.2175,100.4065,95.5217,1701756000000000000
I:XNDXTRND,2755.6953,2759.323,2763.9738,2748.6122,1701756000000000000

---

### Indices — Minute Aggregates

**S3 Path:** `us_indices/minute_aggs_v1`
**Description:** Candlestick data with minute-by-minute