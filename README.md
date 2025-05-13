[![License: NCPUL](https://img.shields.io/badge/license-NCPUL-blue.svg)](./LICENSE.md)


# Finanzguru ADB API

Make the balances shown in the [Finanzguru](https://finanzguru.de) Android app available as a REST API and insert custom virtual accounts automatically.

> **Status**: experimental – use at your own risk. Tested on Samsum Galaxy A13 5G.

## How it works

The script controls the Finanzguru app running on a USB‑connected Android device via **ADB** and *uiautomator*:

1. The device screen is captured as XML.
2. The Python code locates the UI elements that contain the desired information (account balances, etc.).
3. If necessary the screen is scrolled and tapped just like a human user would do.
4. Collected data are exposed through a small **FastAPI** server.

No Finanzguru or bank credentials ever leave your device.

### Flow diagram

```
┌──────────────┐     USB / adb      ┌───────────────────┐
│  Python app  │◀──────────────────▶│ Android device     │
│  (this repo) │                    │ – Finanzguru app   │
└──────────────┘     REST / JSON    │ – ADB daemon       │
           ▲────────────────────────┘
           │ 127.0.0.1:8000
   Your dashboard / scripts
```

## Features

* Automatic refresh of Finanzguru account balances on a schedule you define.
* Virtual accounts – pull data from arbitrary JSON APIs (e.g. exchanges) and merge them into your Finanzguru overview.
* Currency conversion for virtual accounts (uses Binance spot rates).
* Lightweight REST interface (`/accounts`, `/request_update`, `/update_running`).
* Runs on any machine with Python 3.9+ – no root, no Docker required.

## Repository layout

| File               | Purpose                                                                     |
| ------------------ | --------------------------------------------------------------------------- |
| `adb.py`           | Low‑level helper around *pure‑python‑adb* and *uiautomator* XML parsing.    |
| `finanzguru.py`    | High‑level client driving the Android UI and providing convenience helpers. |
| `app.py`           | FastAPI web server and scheduler.                                           |
| `requirements.txt` | Python dependencies.                                                        |
| `config.json`      | Your runtime configuration (not committed).                                 |

## Prerequisites

* Python 3.9 or newer
* An Android phone/tablet with:

  * Finanzguru installed and logged in
  * USB debugging enabled (`Developer options → USB debugging`)
  * *Allow USB debugging* prompt accepted for your host computer
* **ADB** available in your `$PATH` (install via Android SDK Platform Tools)

## Installation

```bash
# clone repository
$ git clone https://github.com/yniverz/finanzguru-adb-api
$ cd finanzguru-adb-api

# install dependencies (consider a virtualenv)
$ pip install -r requirements.txt
```

## Configuration

Create a `config.json` in the project root (it is ignored by Git thanks to `.gitignore`).

```json
{
  "timing": {
    "start_hour": 23,
    "interval_hours": 24
  },
  "device_pin": "1234",
  "server_settings": {
    "host": "0.0.0.0",
    "port": 8000
  },

  "api_accounts": [
    "Main Account",
    "Savings"
  ],

  "virtual_accounts": {
    "Bybit Trader": {
      "data_url": "https://example.com/rawDetails",
      "json_balance_key_path": ["balance"],
      "foreign_currency": "USDT"
    },
    "IG Trader": {
      "data_url": "https://example.com/get_balance",
      "json_balance_key_path": ["account", "balance"]
    }
  }
}
```

*All keys are optional – sensible defaults apply.*

## Running the service

```bash
$ python app.py
```

The script will:

1. Wait until the next scheduled `start_hour`.
2. Unlock the phone (if `device_pin` is set) and start Finanzguru.
3. Trigger a manual **bank refresh** by performing the swipe gesture.
4. Collect balances and launch the FastAPI server on [**http://127.0.0.1:8000**](http://127.0.0.1:8000).

Leave the process running (e.g. inside `tmux`, `screen`, or as a systemd service) to get daily updates.

### API endpoints

| Method | Path              | Description                                                                        |
| ------ | ----------------- | ---------------------------------------------------------------------------------- |
| `GET`  | `/accounts`       | Returns a JSON object with the latest balances and a Unix timestamp `last_update`. |
| `GET`  | `/request_update` | Triggers an asynchronous refresh immediately (HTTP 429 if already running).        |
| `GET`  | `/update_running` | Poll to see whether a refresh is still in progress. (`{"status": "busy"/"ok"}`)        |

Example response for `/accounts`:

```json
{
  "Main Account": 1234.56,
  "Savings": 420.00,
  "Bybit Trader": 99.87,
  "last_update": 1715671200
}
```

### Virtual accounts explained

Virtual accounts are any data sources that are **not** inside Finanzguru. You provide a URL that returns JSON and a list of keys (`json_balance_key_path`) to walk until a numeric balance is found. Values denominated in another currency can be converted to EUR with live rates from Binance.

## Security considerations

* Your device PIN is stored in **plain text** inside `config.json`. Make sure the file is readable only by you.
* The API binds to localhost by default; if you expose it publicly you must add authentication & TLS yourself.
* Finanzguru’s TOS likely prohibit automated interaction – proceed responsibly.

Pull requests are welcome! Please open an issue first to discuss major changes.

## Acknowledgements

* [Finanzguru](https://finanzguru.de) for a great personal finance app
* [pure‑python‑adb](https://github.com/Swind/pure-python-adb) for ADB access without the Android SDK
* The FastAPI & Pydantic teams
