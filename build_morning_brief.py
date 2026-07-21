"""Build the pre-open morning brief (data/morning_brief.json).

Runs before the futures day session opens (08:45 Taipei) and answers the one
question a trader has at that hour: how is today likely to open, and what did
yesterday's chips say about it.

Deliberately separate from build_static_data.py: it runs on a different
schedule, needs none of the T86 pipeline, and must not be able to break the
main data build.

Every section degrades independently -- a source that cannot be read is left
out of the payload rather than reported with a wrong or stale number.
"""

import datetime
import json
import os
import sys

import requests

from build_static_data import HEADERS, check_settlement_week

# TSM's ADR represents this many ordinary 2330 shares.
ADR_SHARES_PER_UNIT = 5

# When the TX day session starts trading (Taipei). Before this, TAIFEX cannot be
# serving live day prices, so identical day/night rows are just the night session.
DAY_SESSION_OPEN = datetime.time(8, 45)

US_INDICES = [
    ("^DJI", "道瓊工業"),
    ("^IXIC", "那斯達克"),
    ("^GSPC", "標普500"),
    ("^SOX", "費城半導體"),
]


def _pct_change(hist):
    """Latest close and its % change vs the prior close, or None if unusable."""
    if hist is None or len(hist) < 2:
        return None
    last = float(hist["Close"].iloc[-1])
    prev = float(hist["Close"].iloc[-2])
    if prev == 0:
        return None
    return {
        "Close": round(last, 2),
        "ChangePct": round((last / prev - 1) * 100, 2),
        "Date": hist.index[-1].strftime("%Y%m%d"),
    }


def fetch_us_markets():
    """Overnight US index closes. Sets the tone for the Taipei open."""
    import yfinance as yf

    result = []
    for ticker, label in US_INDICES:
        try:
            info = _pct_change(yf.Ticker(ticker).history(period="5d"))
        except Exception as e:
            print(f"Warning: US index {ticker} unavailable: {e}", file=sys.stderr)
            continue
        if info:
            result.append({"Name": label, **info})
    return result


def fetch_adr_premium(tw_close, tw_close_date):
    """TSM ADR close plus its premium over the 2330 Taipei close.

    The premium is what makes the ADR actionable rather than trivia: it prices
    in the overnight move that 2330 has not yet had a chance to reflect.
    Returns None unless every input is present, since a premium computed from a
    stale price or a missing FX rate would be actively misleading.
    """
    import yfinance as yf

    if not tw_close:
        return None
    try:
        adr_hist = yf.Ticker("TSM").history(period="5d")
        fx_hist = yf.Ticker("TWD=X").history(period="5d")
    except Exception as e:
        print(f"Warning: ADR/FX unavailable: {e}", file=sys.stderr)
        return None

    adr = _pct_change(adr_hist)
    if not adr or fx_hist is None or fx_hist.empty:
        return None

    fx_rate = float(fx_hist["Close"].iloc[-1])
    implied_twd = adr["Close"] * fx_rate / ADR_SHARES_PER_UNIT
    return {
        "Close": adr["Close"],
        "ChangePct": adr["ChangePct"],
        "Date": adr["Date"],
        "FxRate": round(fx_rate, 3),
        "ImpliedTwd": round(implied_twd, 1),
        "TwClose": tw_close,
        "TwCloseDate": tw_close_date,
        "PremiumPct": round((implied_twd / tw_close - 1) * 100, 2),
    }


def _query_tx_session(date_str, market_code):
    """One TX futures row from TAIFEX's daily report, or None."""
    from bs4 import BeautifulSoup

    formatted = f"{date_str[:4]}/{date_str[4:6]}/{date_str[6:]}"
    try:
        res = requests.post(
            "https://www.taifex.com.tw/cht/3/futDailyMarketReport",
            data={
                "queryType": "2",
                "marketCode": market_code,
                "commodity_id": "TX",
                "queryDate": formatted,
            },
            headers=HEADERS,
            timeout=20,
        )
    except Exception as e:
        print(f"Warning: TAIFEX session query failed for {formatted}: {e}",
              file=sys.stderr)
        return None
    if res.status_code != 200:
        return None

    for row in BeautifulSoup(res.text, "html.parser").find_all("tr"):
        cells = [c.get_text().strip() for c in row.find_all(["td", "th"])]
        if len(cells) > 7 and cells[0] == "TX":
            return cells
    return None


def fetch_night_session(date_str, prev_close, prev_close_date,
                        day_session_open=True, prev_day_row=None):
    """The overnight TX futures session that belongs to `date_str`.

    TAIFEX files the 15:00->05:00 session under the *following* trading day, so
    querying today returns last night's session -- the cleanest read on how the
    market wants to gap at the open.

    Two ways that read can go wrong, guarded separately:

    1. Once the day session is live, TAIFEX serves the running day price under
       *both* market codes, so an intraday run would publish the current price
       as if it were last night's close. Identical rows therefore mean pollution
       -- but only while the day session can actually be trading.

       Before the open there is no day data to serve and TAIFEX echoes the night
       session under both codes, so identical rows there are simply the night
       session. (A date with no session at all returns nothing under either code
       rather than stale data, so an echo cannot be mistaken for a real session.)

    2. If the night report is not published yet, a stale row could stand in for
       it. Compared against the previous session's row to catch that.
    """
    night = _query_tx_session(date_str, "1")
    if not night:
        return None

    if day_session_open:
        day = _query_tx_session(date_str, "0")
        if day and day[:8] == night[:8]:
            print("Warning: day session is trading and TAIFEX returns the same row "
                  "for both market codes; withholding the night-session signal.",
                  file=sys.stderr)
            return None

    if prev_day_row and night[:8] == prev_day_row[:8]:
        print("Warning: night row is identical to the previous session; treating "
              "it as not yet published.", file=sys.stderr)
        return None

    try:
        close = float(night[5].replace(",", ""))
    except (ValueError, IndexError):
        return None

    payload = {
        "Contract": night[1],
        "Open": night[2],
        "High": night[3],
        "Low": night[4],
        "Close": close,
    }
    if prev_close:
        payload["PrevClose"] = prev_close
        payload["PrevCloseDate"] = prev_close_date
        payload["GapPoints"] = round(close - prev_close, 1)
        payload["GapPct"] = round((close / prev_close - 1) * 100, 2)
    return payload


def load_prev_day_tx_row(date_str):
    """Previous trading day's TX day-session row: the gap baseline, and the
    reference for spotting a night report that has not been published yet."""
    return _query_tx_session(date_str, "0")


def row_close(row):
    if not row:
        return None
    try:
        return float(row[5].replace(",", ""))
    except (ValueError, IndexError):
        return None


def summarize_chips(streaks_path="data/streaks.json",
                    futures_path="data/futures_options.json", top_n=5):
    """Yesterday's chip story, read from what the main build already published."""
    summary = {}

    try:
        with open(futures_path, "r", encoding="utf-8") as f:
            futures = json.load(f)
    except Exception:
        futures = None

    if futures:
        history = futures.get("FuturesHistory") or []
        if history:
            latest = history[0]
            summary["ForeignFuturesNet"] = {
                "Date": latest.get("Date"),
                "Net": latest.get("Foreign_Net"),
            }
            if len(history) > 1 and latest.get("Foreign_Net") is not None:
                prev_net = history[1].get("Foreign_Net")
                if prev_net is not None:
                    summary["ForeignFuturesNet"]["Change"] = (
                        latest["Foreign_Net"] - prev_net
                    )
        options = futures.get("Options") or {}
        if options.get("MaxCallStrike") and options.get("MaxPutStrike"):
            summary["OptionLevels"] = {
                "Resistance": options["MaxCallStrike"],
                "ResistanceOI": options.get("MaxCallOI"),
                "Support": options["MaxPutStrike"],
                "SupportOI": options.get("MaxPutOI"),
                "ActiveMonth": options.get("ActiveMonth"),
            }

    try:
        with open(streaks_path, "r", encoding="utf-8") as f:
            streaks = json.load(f)
    except Exception:
        return summary

    rows = streaks.get("Data") or []
    summary["ChipDate"] = streaks.get("Date")

    def top_by(field, positive=True):
        picked = [r for r in rows if (r.get(field) or 0) > 0] if positive \
            else [r for r in rows if (r.get(field) or 0) < 0]
        picked.sort(key=lambda r: abs(r.get(field) or 0), reverse=True)
        return [
            {
                "Symbol": r["Symbol"],
                "Name": r["Name"],
                "Streak": r[field],
                "Close": r.get("Close"),
                "Change": r.get("Change"),
            }
            for r in picked[:top_n]
        ]

    summary["ForeignBuyStreak"] = top_by("Foreign_Streak", True)
    summary["TrustBuyStreak"] = top_by("Trust_Streak", True)

    # Funds that only just started buying: tomorrow's streak, if it holds.
    fresh = [r for r in rows if (r.get("Trust_Streak") or 0) == 1]
    fresh.sort(key=lambda r: r.get("Trust_Latest") or 0, reverse=True)
    summary["TrustFreshBuys"] = [
        {
            "Symbol": r["Symbol"],
            "Name": r["Name"],
            "Shares": r.get("Trust_Latest"),
            "Close": r.get("Close"),
        }
        for r in fresh[:top_n]
    ]
    return summary


def load_2330_close(streaks_path="data/streaks.json"):
    try:
        with open(streaks_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return None, None
    for row in data.get("Data") or []:
        if row.get("Symbol") == "2330":
            return row.get("Close"), data.get("Date")
    return None, data.get("Date")


def main():
    taipei_now = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=8)
    today_str = taipei_now.strftime("%Y%m%d")

    tw_close, chip_date = load_2330_close()

    chips = summarize_chips()
    prev_day_row = load_prev_day_tx_row(chip_date) if chip_date else None
    prev_close = row_close(prev_day_row)

    # The TX day session opens at 08:45 Taipei. Before then it cannot be the
    # source of what TAIFEX returns, which is what makes the identical-rows
    # check meaningful rather than a false alarm.
    day_session_open = taipei_now.time() >= DAY_SESSION_OPEN

    night = fetch_night_session(today_str, prev_close, chip_date,
                                day_session_open=day_session_open,
                                prev_day_row=prev_day_row)
    is_settlement, settlement_date = check_settlement_week(today_str)

    brief = {
        "Date": today_str,
        "GeneratedAt": taipei_now.strftime("%Y-%m-%dT%H:%M:%S+08:00"),
        "UsMarkets": fetch_us_markets(),
        "Adr": fetch_adr_premium(tw_close, chip_date),
        "NightSession": night,
        "Chips": chips,
        "Settlement": {
            "IsSettlementWeek": is_settlement,
            "SettlementDate": settlement_date,
            "IsSettlementDay": settlement_date == (
                f"{today_str[:4]}/{today_str[4:6]}/{today_str[6:]}"
            ),
        },
    }

    os.makedirs("data", exist_ok=True)
    with open("data/morning_brief.json", "w", encoding="utf-8") as f:
        json.dump(brief, f, ensure_ascii=False, indent=2)
    print("Saved data/morning_brief.json")


if __name__ == "__main__":
    main()
