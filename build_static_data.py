import os
import sys
import json
import time
import argparse
import datetime
import requests
import pandas as pd
import io

# Shared HTTP headers - was previously copy-pasted identically in 6 places.
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36"
}

# Stop walking the TAIFEX calendar once this many days in a row fail to fetch.
MAX_CONSECUTIVE_TAIFEX_FAILURES = 5

def _clean_int(val):
    """Strip thousands separators and parse an int. None-safe, never raises."""
    if val is None:
        return 0
    val_str = str(val).replace(",", "").strip()
    try:
        return int(val_str)
    except ValueError:
        return 0

def _clean_float(val):
    """Strip thousands separators and parse a float. None-safe, never raises."""
    if val is None:
        return 0.0
    val_str = str(val).replace(",", "").strip()
    try:
        return float(val_str)
    except ValueError:
        return 0.0

# Ensure directories exist
os.makedirs("data", exist_ok=True)
os.makedirs("data/cache", exist_ok=True)

def is_in_ipython():
    return False

def western_to_roc_date(date_str):
    year = int(date_str[:4])
    month = date_str[4:6]
    day = date_str[6:]
    roc_year = year - 1911
    return f"{roc_year}/{month}/{day}"

def fetch_data_with_cache(url, cache_path, is_today=False, delay=0.8):
    # For today's date we prefer fresh data; ignore cached file if present
    if os.path.exists(cache_path) and not is_today:
        with open(cache_path, "r", encoding="utf-8") as f:
            try:
                data = json.load(f)
                return data
            except Exception:
                # If cache is corrupted, fall back to fetching
                pass
                
    headers = HEADERS
    
    url_name = url.split("?")[0].split("/")[-1]
    
    for attempt in range(3):
        print(f"Fetching {url_name} (Attempt {attempt+1})...")
        time.sleep(delay if attempt == 0 else 2.0)
        try:
            response = requests.get(url, headers=headers, timeout=25)
            if response.status_code == 200:
                data = response.json()
                
                has_data = False
                if "stat" in data and data["stat"] == "OK" and "data" in data and len(data["data"]) > 0:
                    has_data = True
                elif "aaData" in data and len(data["aaData"]) > 0:
                    has_data = True
                elif "tables" in data and len(data["tables"]) > 0 and len(data["tables"][0].get("data", [])) > 0:
                    has_data = True
                    
                if has_data:
                    with open(cache_path, "w", encoding="utf-8") as f:
                        json.dump(data, f, ensure_ascii=False, indent=2)
                    return data
                else:
                    if not is_today:
                        no_data_content = {"stat": "NO_DATA"}
                        with open(cache_path, "w", encoding="utf-8") as f:
                            json.dump(no_data_content, f, ensure_ascii=False, indent=2)
                        return no_data_content
                    return data
            else:
                print(f"Server returned status code {response.status_code} for {url_name} on attempt {attempt+1}")
        except Exception as e:
            print(f"Error fetching {url_name} on attempt {attempt+1}: {e}", file=sys.stderr)
            
    return None

def parse_twse_t86(api_response):
    fields = [f.strip() for f in api_response.get("fields", [])]
    data = api_response.get("data", [])
    
    try:
        idx_symbol = fields.index("證券代號")
    except ValueError:
        idx_symbol = 0
    try:
        idx_name = fields.index("證券名稱")
    except ValueError:
        idx_name = 1
        
    idx_foreign = -1
    for f in ["外陸資買賣超股數(不含外資自營商)", "外陸資買賣超股數", "外資及陸資買賣超股數(不含外資自營商)", "外資及陸資買賣超股數"]:
        if f in fields:
            idx_foreign = fields.index(f)
            break
    if idx_foreign == -1:
        idx_foreign = 4
        
    idx_trust = -1
    if "投信買賣超股數" in fields:
        idx_trust = fields.index("投信買賣超股數")
    else:
        idx_trust = 10
        
    idx_dealer = -1
    if "自營商買賣超股數" in fields:
        idx_dealer = fields.index("自營商買賣超股數")
    else:
        idx_dealer = 11
        
    idx_dealer_prop = -1
    for f in ["自營商買賣超股數(自行買賣)", "自營商(自行買賣)買賣超股數"]:
        if f in fields:
            idx_dealer_prop = fields.index(f)
            break
        
    idx_dealer_hedge = -1
    for f in ["自營商買賣超股數(避險)", "自營商(避險)買賣超股數"]:
        if f in fields:
            idx_dealer_hedge = fields.index(f)
            break
        
    idx_total = -1
    if "三大法人買賣超股數" in fields:
        idx_total = fields.index("三大法人買賣超股數")
    else:
        idx_total = 18
        
    def get_val_safe(row, idx):
        if idx >= 0 and idx < len(row):
            return _clean_int(row[idx])
        return 0

    rows = []
    for r in data:
        symbol = str(r[idx_symbol]).strip() if idx_symbol < len(r) else ""
        name = str(r[idx_name]).strip() if idx_name < len(r) else ""
        
        foreign = get_val_safe(r, idx_foreign)
        trust = get_val_safe(r, idx_trust)
        dealer = get_val_safe(r, idx_dealer)
        dealer_prop = get_val_safe(r, idx_dealer_prop) if idx_dealer_prop != -1 else 0
        dealer_hedge = get_val_safe(r, idx_dealer_hedge) if idx_dealer_hedge != -1 else 0
        total = get_val_safe(r, idx_total)
        
        rows.append({
            "Symbol": symbol,
            "Name": name,
            "Foreign": foreign,
            "Trust": trust,
            "Dealer": dealer,
            "DealerProp": dealer_prop,
            "DealerHedge": dealer_hedge,
            "Total": total
        })
    return pd.DataFrame(rows)

def parse_tpex_t86(api_response):
    data = []
    if "tables" in api_response and len(api_response["tables"]) > 0:
        data = api_response["tables"][0].get("data", [])
    elif "aaData" in api_response:
        data = api_response["aaData"]
        
    rows = []
    for r in data:
        if len(r) >= 24:
            symbol = str(r[0]).strip()
            name = str(r[1]).strip()
            
            foreign = _clean_int(r[10])
            trust = _clean_int(r[13])
            dealer = _clean_int(r[22])
            dealer_prop = _clean_int(r[16])
            dealer_hedge = _clean_int(r[19])
            total = _clean_int(r[23])
            
            rows.append({
                "Symbol": symbol,
                "Name": name,
                "Foreign": foreign,
                "Trust": trust,
                "Dealer": dealer,
                "DealerProp": dealer_prop,
                "DealerHedge": dealer_hedge,
                "Total": total
            })
        elif len(r) >= 19:
            symbol = str(r[0]).strip()
            name = str(r[1]).strip()
            
            foreign = _clean_int(r[4])
            trust = _clean_int(r[10])
            dealer = _clean_int(r[17])
            dealer_prop = 0
            dealer_hedge = 0
            total = _clean_int(r[18])
            
            rows.append({
                "Symbol": symbol,
                "Name": name,
                "Foreign": foreign,
                "Trust": trust,
                "Dealer": dealer,
                "DealerProp": dealer_prop,
                "DealerHedge": dealer_hedge,
                "Total": total
            })
    return pd.DataFrame(rows)

def load_t86_both_markets(date_str, cache_dir, is_today=False):
    twse_url = f"https://www.twse.com.tw/rwd/zh/fund/T86?response=json&date={date_str}&selectType=ALLBUT0999"
    twse_cache = os.path.join(cache_dir, f"T86_{date_str}.json")
    twse_data = fetch_data_with_cache(twse_url, twse_cache, is_today)

    if twse_data is None:
        # Every retry failed, so we cannot tell a holiday from an outage here.
        # Say so rather than reporting "no data" and letting the day disappear.
        raise T86FetchError(f"TWSE T86 unavailable for {date_str}")

    if twse_data.get("stat") == "NO_DATA":
        if not is_today:
            tpex_cache = os.path.join(cache_dir, f"TPEX_T86_{date_str}.json")
            if not os.path.exists(tpex_cache):
                try:
                    with open(tpex_cache, "w", encoding="utf-8") as f:
                        json.dump({"stat": "NO_DATA"}, f)
                except Exception:
                    pass
        return None

    roc_date = western_to_roc_date(date_str)
    tpex_url = f"https://www.tpex.org.tw/web/stock/3insti/daily_trade/3itrade_hedge_result.php?l=zh-tw&o=json&se=EW&t=D&d={roc_date}"
    tpex_cache = os.path.join(cache_dir, f"TPEX_T86_{date_str}.json")
    tpex_data = fetch_data_with_cache(tpex_url, tpex_cache, is_today)

    if tpex_data is None:
        # TWSE answered but TPEx did not: publishing now would record a
        # listed-only day and corrupt every OTC streak. Treat the whole day as
        # unknown so the caller keeps whatever was published before.
        raise T86FetchError(f"TPEx T86 unavailable for {date_str}")

    has_twse = twse_data.get("stat") == "OK" and "data" in twse_data and len(twse_data["data"]) > 0
    has_tpex = False
    if tpex_data:
        if "aaData" in tpex_data and len(tpex_data["aaData"]) > 0:
            has_tpex = True
        elif "tables" in tpex_data and len(tpex_data["tables"]) > 0 and len(tpex_data["tables"][0].get("data", [])) > 0:
            has_tpex = True
            
    if not (has_twse or has_tpex):
        return None
        
    df_twse = pd.DataFrame()
    if has_twse:
        df_twse = parse_twse_t86(twse_data)
        df_twse["Market"] = "上市 (TWSE)"
        
    df_tpex = pd.DataFrame()
    if has_tpex:
        df_tpex = parse_tpex_t86(tpex_data)
        df_tpex["Market"] = "上櫃 (TPEx)"
        
    df_combined = pd.concat([df_twse, df_tpex], ignore_index=True)
    return df_combined


def collect_t86_history(latest_date_str, cache_dir, n=20, today_str=None,
                        skip_today=False):
    """Collect the latest `n` trading days of T86 data, newest first.

    Walks calendar weekdays backwards and asks TWSE/TPEx about each one directly.
    T86 itself is the source of the streak data, so it -- not Yahoo's ^TWII
    calendar -- decides which days are trading days: a day TWSE reports as
    NO_DATA is a holiday and skipped over.

    Streaks are derived over a contiguous window, so a day that fails to fetch is
    NOT skipped: doing so would splice the days on either side together and
    inflate every streak count. Instead the window is truncated at the gap,
    yielding a shorter but never-corrupted history that self-heals once the
    upstream day comes back. (Contrast fetch of per-day OI, where an isolated
    missing day is harmless and merely skipped.)

    Returns (history, truncated_at) where history is a list of (date_str, df)
    newest first, and truncated_at is the date that cut the window short (or None).
    """
    history = []
    truncated_at = None
    current = datetime.datetime.strptime(latest_date_str, "%Y%m%d").date()
    checked = 0

    while len(history) < n and checked < n * 4:
        checked += 1
        if current.weekday() in (5, 6):
            current -= datetime.timedelta(days=1)
            continue

        date_str = current.strftime("%Y%m%d")
        is_today = (date_str == today_str)
        if is_today and skip_today:
            # Today's session data is not out yet; don't treat it as a gap.
            current -= datetime.timedelta(days=1)
            continue

        try:
            df = load_t86_both_markets(date_str, cache_dir, is_today)
        except T86FetchError as e:
            print(f"Warning: T86 unavailable for {date_str}; truncating streak "
                  f"window here: {e}", file=sys.stderr)
            truncated_at = date_str
            break

        if df is not None:
            history.append((date_str, df))
        current -= datetime.timedelta(days=1)

    return history, truncated_at


def load_daily_quotes(date_str, cache_dir):
    """Listed-market OHLC for one past date, cached by date.

    Listed only, on purpose. TPEx's quote endpoint takes no date parameter and
    always answers with the most recent session, so asking it for an older date
    returns today's prices wearing that date's label -- which would quietly
    corrupt every average and return built on top of it. OTC prices are
    therefore left out of historical loads: callers see a missing symbol, which
    they already handle, instead of a plausible wrong number.

    Historical days never change, so caching keeps a 20-day walk to one live
    fetch per run instead of twenty.
    """
    cache_path = os.path.join(cache_dir, f"quotes_twse_{date_str}.json")
    if os.path.exists(cache_path):
        try:
            with open(cache_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass

    try:
        quotes = scrape_twse_quotes(date_str) or {}
    except Exception as e:
        print(f"Warning: TWSE quotes unavailable for {date_str}: {e}", file=sys.stderr)
        return {}

    if quotes:
        os.makedirs(cache_dir, exist_ok=True)
        with open(cache_path, "w", encoding="utf-8") as f:
            json.dump(quotes, f, ensure_ascii=False)
    return quotes


def load_daily_typical_prices(date_str, cache_dir):
    """Whole-market typical price ((H+L+C)/3) for one date.

    Typical price stands in for the day's average execution price; it is a
    closer proxy than the close alone for flow spread across a session.
    """
    prices = {}
    for sym, q in load_daily_quotes(date_str, cache_dir).items():
        high, low, close = q.get("High") or 0, q.get("Low") or 0, q.get("Close") or 0
        if close > 0 and high > 0 and low > 0:
            prices[sym] = round((high + low + close) / 3, 2)
        elif close > 0:
            prices[sym] = close
    return prices


def load_daily_closes(date_str, cache_dir):
    """Whole-market closing prices for one date."""
    return {
        sym: q["Close"]
        for sym, q in load_daily_quotes(date_str, cache_dir).items()
        if q.get("Close")
    }


def compute_streak_avg_prices(day_dfs, cache_dir, columns=("Foreign", "Trust")):
    """Share-weighted average price across each symbol's current streak.

    This is NOT a cost basis. T86 reports *net* shares, so a day of "+1000"
    may be ten thousand bought against nine thousand sold; weighting price by
    net flow yields a reference level for the streak, not what anyone paid.
    Named and surfaced accordingly.

    Only streaks of two days or more get a value: a single day's average is
    just that day's price and would dress up nothing as insight.

    Coverage is effectively listed-only, since historical prices come from the
    one endpoint that honours a date (see load_daily_quotes). OTC symbols get
    no value rather than a wrong one.
    """
    if not day_dfs:
        return {}

    dates = [d for d, _ in day_dfs]
    prices_by_date = {}
    for date_str in dates:
        try:
            prices_by_date[date_str] = load_daily_typical_prices(date_str, cache_dir)
        except Exception as e:
            print(f"Warning: prices unavailable for {date_str}: {e}", file=sys.stderr)
            prices_by_date[date_str] = {}

    # Per-day {symbol: shares} for each tracked column, newest first.
    shares_by_day = []
    for _, df in day_dfs:
        day_map = {}
        for col in columns:
            if col in df.columns:
                day_map[col] = dict(zip(df["Symbol"], df[col]))
            else:
                day_map[col] = {}
        shares_by_day.append(day_map)

    symbols = set()
    for _, df in day_dfs:
        symbols.update(df["Symbol"].tolist())

    result = {}
    for sym in symbols:
        entry = {}
        for col in columns:
            first = shares_by_day[0][col].get(sym, 0) or 0
            if first == 0:
                continue
            buying = first > 0

            weighted, total = 0.0, 0.0
            days = 0
            for i, date_str in enumerate(dates):
                shares = shares_by_day[i][col].get(sym, 0) or 0
                if buying and shares <= 0:
                    break
                if not buying and shares >= 0:
                    break
                price = prices_by_date.get(date_str, {}).get(sym)
                if not price:
                    # A missing price would silently reweight the average, so
                    # stop here rather than average over an incomplete streak.
                    break
                weighted += abs(shares) * price
                total += abs(shares)
                days += 1

            if days >= 2 and total > 0:
                entry[col] = round(weighted / total, 2)
        if entry:
            result[sym] = entry
    return result


SCOREBOARD_SIGNALS = [
    ("ForeignBuy", "Foreign_Streak", "外資連買"),
    ("TrustBuy", "Trust_Streak", "投信連買"),
]
SCOREBOARD_TOP_N = 10
SCOREBOARD_MIN_STREAK = 3
SCOREBOARD_MAX_ENTRIES = 120


def _pick_signal_stocks(rows, streak_field, top_n=SCOREBOARD_TOP_N,
                        min_streak=SCOREBOARD_MIN_STREAK):
    """The stocks a signal would have flagged after this session's close."""
    picked = [r for r in rows if (r.get(streak_field) or 0) >= min_streak]
    picked.sort(key=lambda r: (r.get(streak_field) or 0), reverse=True)
    return [
        {"Symbol": r["Symbol"], "Name": r["Name"], "Streak": r[streak_field]}
        for r in picked[:top_n]
    ]


def update_scoreboard(latest_date, rows, cache_dir, path="data/scoreboard.json"):
    """Record what each signal flagged, and score it once the next day is in.

    A signal computed from session T's chips is only actionable from T+1, so an
    entry is written on T with no result and filled in on the next run that sees
    a later trading day. Scoring never touches the day the signal was formed --
    that would be reading tomorrow's paper.

    The ledger is append-only and self-contained: it accumulates as the site
    runs rather than being recomputed, so a bad day upstream cannot silently
    rewrite past results.
    """
    try:
        with open(path, "r", encoding="utf-8") as f:
            board = json.load(f)
    except Exception:
        board = {"Entries": []}

    entries = board.get("Entries") or []

    # 1. Score any entry still waiting for a follow-up session.
    closes_today = None
    for entry in entries:
        if entry.get("EvalDate") or entry.get("SignalDate") >= latest_date:
            continue
        if closes_today is None:
            closes_today = load_daily_closes(latest_date, cache_dir)
        closes_signal = load_daily_closes(entry["SignalDate"], cache_dir)
        if not closes_signal or not closes_today:
            continue

        scored = []
        for stock in entry.get("Stocks", []):
            before = closes_signal.get(stock["Symbol"])
            after = closes_today.get(stock["Symbol"])
            if not before or not after:
                continue
            stock["Return"] = round((after / before - 1) * 100, 2)
            scored.append(stock["Return"])

        if scored:
            entry["EvalDate"] = latest_date
            entry["AvgReturn"] = round(sum(scored) / len(scored), 2)
            entry["WinRate"] = round(
                100.0 * sum(1 for r in scored if r > 0) / len(scored), 1
            )
            entry["Scored"] = len(scored)

    # 2. Open an entry for this session, unless one already exists.
    for key, field, label in SCOREBOARD_SIGNALS:
        if any(e.get("Signal") == key and e.get("SignalDate") == latest_date
               for e in entries):
            continue
        stocks = _pick_signal_stocks(rows, field)
        if stocks:
            entries.append({
                "Signal": key,
                "Label": label,
                "SignalDate": latest_date,
                "EvalDate": None,
                "Stocks": stocks,
            })

    entries.sort(key=lambda e: (e.get("SignalDate"), e.get("Signal")), reverse=True)
    del entries[SCOREBOARD_MAX_ENTRIES:]

    # 3. Roll the scored entries up per signal.
    summary = {}
    for key, field, label in SCOREBOARD_SIGNALS:
        scored = [e for e in entries if e.get("Signal") == key and e.get("EvalDate")]
        if not scored:
            continue
        returns = [e["AvgReturn"] for e in scored]
        summary[key] = {
            "Label": label,
            "Sessions": len(scored),
            "AvgReturn": round(sum(returns) / len(returns), 2),
            # Share of *sessions* that came out ahead. Deliberately not named
            # WinRate: that field on an entry means share of *stocks*, and one
            # name for two denominators invites misreading.
            "PositiveSessionRate": round(
                100.0 * sum(1 for r in returns if r > 0) / len(returns), 1
            ),
            "BestReturn": max(returns),
            "WorstReturn": min(returns),
        }

    board = {
        "UpdatedFor": latest_date,
        "Note": ("訊號於當日收盤後產生，報酬以次一交易日收盤價計算，未計交易成本。"
                 "報酬僅涵蓋可取得歷史股價的上市個股，Scored 為實際計入檔數。"),
        "Summary": summary,
        "Entries": entries,
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(board, f, ensure_ascii=False, indent=2)
    return board


def calculate_streaks(df_list):
    all_symbols = set()
    symbol_to_name = {}
    symbol_to_market = {}
    
    for df in df_list:
        for _, row in df.iterrows():
            sym = row["Symbol"]
            all_symbols.add(sym)
            symbol_to_name[sym] = row["Name"]
            symbol_to_market[sym] = row["Market"]
            
    symbol_data = {}
    for sym in all_symbols:
        symbol_data[sym] = {
            "Foreign": [0] * len(df_list),
            "Trust": [0] * len(df_list),
            "Dealer": [0] * len(df_list),
            "DealerProp": [0] * len(df_list),
            "DealerHedge": [0] * len(df_list),
            "Total": [0] * len(df_list)
        }
        
    for i, df in enumerate(df_list):
        df_indexed = df.set_index("Symbol")
        for sym in all_symbols:
            if sym in df_indexed.index:
                row = df_indexed.loc[sym]
                if isinstance(row, pd.DataFrame):
                    row = row.iloc[0]
                symbol_data[sym]["Foreign"][i] = row["Foreign"]
                symbol_data[sym]["Trust"][i] = row["Trust"]
                symbol_data[sym]["Dealer"][i] = row["Dealer"]
                symbol_data[sym]["DealerProp"][i] = row["DealerProp"] if "DealerProp" in row else 0
                symbol_data[sym]["DealerHedge"][i] = row["DealerHedge"] if "DealerHedge" in row else 0
                symbol_data[sym]["Total"][i] = row["Total"]
                
    def get_streak_days(vals):
        if not vals or vals[0] == 0:
            return 0
        is_buying = vals[0] > 0
        streak = 0
        for val in vals:
            if is_buying and val > 0:
                streak += 1
            elif not is_buying and val < 0:
                streak -= 1
            else:
                break
        return streak

    streak_results = []
    for sym in sorted(all_symbols):
        data = symbol_data[sym]
        foreign_streak = get_streak_days(data["Foreign"])
        trust_streak = get_streak_days(data["Trust"])
        dealer_streak = get_streak_days(data["Dealer"])
        dealer_prop_streak = get_streak_days(data["DealerProp"])
        dealer_hedge_streak = get_streak_days(data["DealerHedge"])
        total_streak = get_streak_days(data["Total"])
        
        streak_results.append({
            "Symbol": sym,
            "Name": symbol_to_name[sym],
            "Market": symbol_to_market[sym],
            "Foreign_Streak": foreign_streak,
            "Foreign_Latest": data["Foreign"][0],
            "Trust_Streak": trust_streak,
            "Trust_Latest": data["Trust"][0],
            "Dealer_Streak": dealer_streak,
            "Dealer_Latest": data["Dealer"][0],
            "DealerProp_Streak": dealer_prop_streak,
            "DealerProp_Latest": data["DealerProp"][0],
            "DealerHedge_Streak": dealer_hedge_streak,
            "DealerHedge_Latest": data["DealerHedge"][0],
            "Total_Streak": total_streak,
            "Total_Latest": data["Total"][0]
        })
        
    return pd.DataFrame(streak_results)

class UpstreamFetchError(Exception):
    """An upstream source was unreachable or returned an unusable response.

    Kept separate from a genuine no-data day (reported as None) so that a
    transport failure is never mistaken for "this day has no data".
    """


class TaifexFetchError(UpstreamFetchError):
    """TAIFEX could not be reached for a given day."""


class T86FetchError(UpstreamFetchError):
    """TWSE's T86 endpoint could not be reached for a given day."""


def fetch_taifex_futures_oi(date_str, cache_dir, is_today=False):
    # Today's figures are still provisional until TAIFEX settles them, so they are
    # neither read from nor written to the cache -- otherwise an early-afternoon
    # run would pin a half-finished number for good.
    cache_path = os.path.join(cache_dir, f"futures_oi_{date_str}.json")
    if os.path.exists(cache_path) and not is_today:
        with open(cache_path, "r", encoding="utf-8") as f:
            try:
                data = json.load(f)
                if "TX" in data:
                    return data
            except Exception:
                pass

    formatted_date = f"{date_str[:4]}/{date_str[4:6]}/{date_str[6:]}"
    url = "https://www.taifex.com.tw/cht/3/futContractsDate"
    payload = {"queryDate": formatted_date}
    headers = HEADERS

    print(f"Fetching Futures OI from TAIFEX for {formatted_date}...")
    time.sleep(1.0)

    try:
        res = requests.post(url, data=payload, headers=headers, timeout=15)
    except Exception as e:
        raise TaifexFetchError(f"{formatted_date}: request failed: {e}") from e

    if res.status_code != 200:
        raise TaifexFetchError(f"{formatted_date}: HTTP {res.status_code}")

    try:
        from bs4 import BeautifulSoup
        res.encoding = 'utf-8'
        soup = BeautifulSoup(res.text, "html.parser")
        rows = soup.find_all("tr")

        contracts = {}

        for i, r in enumerate(rows):
            cells = [td.get_text().strip() for td in r.find_all(["td", "th"])]
            if len(cells) > 1:
                contract_name = cells[1]
                if contract_name in ["臺股期貨", "小型臺指期貨", "微型臺指期貨"]:
                    dealers_long = _clean_int(cells[9])
                    dealers_short = _clean_int(cells[11])
                    dealers_net = _clean_int(cells[13])

                    cells_trust = [td.get_text().strip() for td in rows[i+1].find_all(["td", "th"])]
                    trust_long = _clean_int(cells_trust[7])
                    trust_short = _clean_int(cells_trust[9])
                    trust_net = _clean_int(cells_trust[11])

                    cells_foreign = [td.get_text().strip() for td in rows[i+2].find_all(["td", "th"])]
                    foreign_long = _clean_int(cells_foreign[7])
                    foreign_short = _clean_int(cells_foreign[9])
                    foreign_net = _clean_int(cells_foreign[11])

                    key = "TX" if contract_name == "臺股期貨" else ("MTX" if contract_name == "小型臺指期貨" else "TMF")
                    contracts[key] = {
                        "Dealers": {"Long": dealers_long, "Short": dealers_short, "Net": dealers_net},
                        "Trust": {"Long": trust_long, "Short": trust_short, "Net": trust_net},
                        "Foreign": {"Long": foreign_long, "Short": foreign_short, "Net": foreign_net}
                    }
    except Exception as e:
        raise TaifexFetchError(f"{formatted_date}: parse failed: {e}") from e

    if "TX" not in contracts:
        # Page came back fine but holds no TX contract: a non-trading day.
        return None

    result = {
        "Date": date_str,
        "Dealers": contracts["TX"]["Dealers"],
        "Trust": contracts["TX"]["Trust"],
        "Foreign": contracts["TX"]["Foreign"],
        "TX": contracts["TX"],
        "MTX": contracts.get("MTX", None),
        "TMF": contracts.get("TMF", None)
    }

    if not is_today:
        os.makedirs(cache_dir, exist_ok=True)
        with open(cache_path, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
    return result


def collect_futures_oi_history(latest_date_str, cache_dir, n=20, today_str=None):
    """Collect the latest `n` days of futures OI, newest first.

    Walks calendar weekdays backwards and asks TAIFEX about each one directly.
    TAIFEX is the authority on which days have futures data, so this deliberately
    does not reuse the Yahoo-derived trading-day list or the T86 results: a gap in
    either of those must not decide whether OI gets fetched.
    """
    history = []
    failed_dates = []
    consecutive_failures = 0
    current = datetime.datetime.strptime(latest_date_str, "%Y%m%d").date()
    checked = 0

    while len(history) < n and checked < n * 4:
        checked += 1
        if current.weekday() in (5, 6):
            current -= datetime.timedelta(days=1)
            continue

        date_str = current.strftime("%Y%m%d")
        try:
            oi_data = fetch_taifex_futures_oi(date_str, cache_dir, is_today=(date_str == today_str))
        except TaifexFetchError as e:
            # Do not treat an outage as a holiday: note it and keep the slot open
            # so the merge below preserves whatever was published previously.
            print(f"Warning: futures OI unavailable for {date_str}: {e}", file=sys.stderr)
            failed_dates.append(date_str)
            consecutive_failures += 1
            if consecutive_failures >= MAX_CONSECUTIVE_TAIFEX_FAILURES:
                # TAIFEX is down rather than merely quiet; stop hammering it and let
                # the merge keep the published history until the next run.
                print(f"Giving up on TAIFEX after {consecutive_failures} consecutive "
                      f"failures.", file=sys.stderr)
                break
            oi_data = None
        else:
            consecutive_failures = 0

        if oi_data:
            history.append((date_str, oi_data))
        current -= datetime.timedelta(days=1)

    if failed_dates:
        print(f"Warning: {len(failed_dates)} day(s) could not be fetched from TAIFEX: "
              f"{', '.join(failed_dates)}", file=sys.stderr)
    return history


def flatten_oi_entry(date_str, oi):
    """Turn a raw TAIFEX OI record into the flat shape stored in futures_options.json."""
    tx = oi["TX"] if "TX" in oi else oi
    entry = {
        "Date": date_str,
        "Foreign_Net": tx["Foreign"]["Net"],
        "Trust_Net": tx["Trust"]["Net"],
        "Dealer_Net": tx["Dealers"]["Net"],
        "Total_Net": tx["Foreign"]["Net"] + tx["Trust"]["Net"] + tx["Dealers"]["Net"],
    }
    for key in ("MTX", "TMF"):
        sub = oi.get(key)
        entry[f"{key}_Foreign_Net"] = sub["Foreign"]["Net"] if sub else None
        entry[f"{key}_Trust_Net"] = sub["Trust"]["Net"] if sub else None
        entry[f"{key}_Dealer_Net"] = sub["Dealers"]["Net"] if sub else None
        entry[f"{key}_Total_Net"] = (
            sub["Foreign"]["Net"] + sub["Trust"]["Net"] + sub["Dealers"]["Net"]
        ) if sub else None
    return entry


def load_published_futures_history(path="data/futures_options.json"):
    """Read the FuturesHistory already published on disk, newest first."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f).get("FuturesHistory") or []
    except Exception:
        return []


def merge_futures_history(published_entries, fresh_entries, n=20):
    """Merge freshly fetched entries over previously published ones, newest first.

    History is append-only: a day that once reached futures_options.json is never
    dropped just because an upstream source temporarily stopped reporting it.
    """
    by_date = {}
    for entry in published_entries:
        if isinstance(entry, dict) and entry.get("Date"):
            by_date[entry["Date"]] = entry
    for entry in fresh_entries:
        by_date[entry["Date"]] = entry
    return sorted(by_date.values(), key=lambda e: e["Date"], reverse=True)[:n]

def fetch_taifex_options_max_oi(date_str, cache_dir):
    cache_path = os.path.join(cache_dir, f"options_oi_{date_str}.json")
    if os.path.exists(cache_path):
        with open(cache_path, "r", encoding="utf-8") as f:
            try:
                return json.load(f)
            except Exception:
                pass
                
    formatted_date = f"{date_str[:4]}/{date_str[4:6]}/{date_str[6:]}"
    url = "https://www.taifex.com.tw/cht/3/optDailyMarketReport"
    payload = {
        "queryDate": formatted_date,
        "commodity_id": "TXO",
        "MarketCode": "0"
    }
    headers = HEADERS
    
    print(f"Fetching Options OI from TAIFEX for {formatted_date}...")
    time.sleep(1.0)
    
    try:
        from bs4 import BeautifulSoup
        from collections import defaultdict
        res = requests.post(url, data=payload, headers=headers, timeout=15)
        if res.status_code == 200:
            soup = BeautifulSoup(res.text, "html.parser")
            rows = soup.find_all("tr")
            
            month_oi = defaultdict(int)
            row_data = []
            
            for r in rows:
                cells = [td.get_text().strip() for td in r.find_all(["td", "th"])]
                if len(cells) >= 16 and cells[0] == "TXO":
                    month = cells[1]
                    strike = int(cells[3])
                    cp = cells[4]
                    try:
                        oi = int(cells[15].replace(",", "").strip())
                    except ValueError:
                        oi = 0
                    month_oi[month] += oi
                    row_data.append({
                        "Month": month,
                        "Strike": strike,
                        "CP": cp,
                        "OI": oi
                    })
            
            if month_oi:
                active_month = max(month_oi, key=month_oi.get)
                
                call_oi = defaultdict(int)
                put_oi = defaultdict(int)
                
                for item in row_data:
                    if item["Month"] == active_month:
                        if item["CP"] == "Call":
                            call_oi[item["Strike"]] += item["OI"]
                        elif item["CP"] == "Put":
                            put_oi[item["Strike"]] += item["OI"]
                
                max_call_strike = max(call_oi, key=call_oi.get)
                max_call_val = call_oi[max_call_strike]
                
                max_put_strike = max(put_oi, key=put_oi.get)
                max_put_val = put_oi[max_put_strike]
                
                result = {
                    "Date": date_str,
                    "ActiveMonth": active_month,
                    "MaxCallStrike": max_call_strike,
                    "MaxCallOI": max_call_val,
                    "MaxPutStrike": max_put_strike,
                    "MaxPutOI": max_put_val
                }
                
                with open(cache_path, "w", encoding="utf-8") as f:
                    json.dump(result, f, ensure_ascii=False, indent=2)
                return result
    except Exception as e:
        print(f"Error parsing options OI: {e}", file=sys.stderr)
    return None

def check_settlement_week(date_str):
    try:
        year = int(date_str[:4])
        month = int(date_str[4:6])
        day = int(date_str[6:])
        current_date = datetime.date(year, month, day)
        
        first_day_of_month = datetime.date(year, month, 1)
        first_weekday = first_day_of_month.weekday()
        
        days_to_wed = (2 - first_weekday) % 7
        first_wed = first_day_of_month + datetime.timedelta(days=days_to_wed)
        third_wed = first_wed + datetime.timedelta(days=14)
        
        settlement_mon = third_wed - datetime.timedelta(days=2)
        
        if settlement_mon <= current_date <= third_wed:
            return True, third_wed.strftime("%Y/%m/%d")
    except Exception:
        pass
    return False, None

def generate_trend_chart(futures_history, cache_dir):
    import yfinance as yf
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    
    try:
        import matplotlib.font_manager as fm
        font_path = "data/cache/NotoSansCJKtc-Regular.otf"
        if not os.path.exists(font_path):
            print("Downloading Noto Sans CJK TC Font...")
            font_url = "https://github.com/googlefonts/noto-cjk/raw/main/Sans/OTF/TraditionalChinese/NotoSansCJKtc-Regular.otf"
            res = requests.get(font_url, timeout=30)
            if res.status_code == 200:
                with open(font_path, "wb") as f:
                    f.write(res.content)
        if os.path.exists(font_path):
            fm.fontManager.addfont(font_path)
            font_name = fm.FontProperties(fname=font_path).get_name()
            matplotlib.rcParams['font.sans-serif'] = [font_name, 'sans-serif']
    except Exception as e:
        print(f"Warning: Failed to setup custom font: {e}", file=sys.stderr)
        matplotlib.rcParams['font.sans-serif'] = ['Microsoft JhengHei', 'SimHei', 'sans-serif']
        
    matplotlib.rcParams['axes.unicode_minus'] = False
    
    dates = [item["Date"] for item in futures_history]
    foreign_nets = [item["Foreign_Net"] for item in futures_history]
    
    if not dates:
        return None, []
        
    start_date_str = f"{dates[0][:4]}-{dates[0][4:6]}-{dates[0][6:]}"
    end_date = datetime.datetime.strptime(dates[-1], "%Y%m%d") + datetime.timedelta(days=2)
    end_date_str = end_date.strftime("%Y-%m-%d")
    
    try:
        print("Downloading Index prices from Yahoo Finance...")
        ticker = yf.Ticker("^TWII")
        hist = ticker.history(start=start_date_str, end=end_date_str)
        if hist.empty:
            print("Failed to download index quotes.", file=sys.stderr)
            return None, []
            
        hist.index = hist.index.strftime("%Y%m%d")
        
        aligned_dates = []
        aligned_prices = []
        aligned_nets = []
        
        for d, net in zip(dates, foreign_nets):
            if d in hist.index:
                aligned_dates.append(f"{d[4:6]}/{d[6:]}")
                aligned_prices.append(hist.loc[d]["Close"])
                aligned_nets.append(net)
                
        if not aligned_dates:
            print("Failed to align dates.", file=sys.stderr)
            return None, []
            
        fig, ax1 = plt.subplots(figsize=(10, 5))
        
        color = 'tab:blue'
        ax1.set_xlabel('交易日', fontweight='bold')
        ax1.set_ylabel('大盤收盤指數', color=color, fontweight='bold')
        ax1.plot(aligned_dates, aligned_prices, color=color, marker='o', linewidth=2, label='大盤指數')
        ax1.tick_params(axis='y', labelcolor=color)
        ax1.grid(True, linestyle='--', alpha=0.5)
        
        ax2 = ax1.twinx()
        color = 'tab:red'
        ax2.set_ylabel('外資期貨淨未平倉口數 (口)', color=color, fontweight='bold')
        
        bar_colors = ['#ff4d4d' if val >= 0 else '#22c55e' for val in aligned_nets]
        bars = ax2.bar(aligned_dates, aligned_nets, color=bar_colors, alpha=0.35, width=0.4, label='外資淨 OI')
        
        for bar in bars:
            height = bar.get_height()
            label_y = height + (1000 if height >= 0 else -3000)
            ax2.text(bar.get_x() + bar.get_width()/2., label_y,
                     f'{int(height):,}',
                     ha='center', va='bottom', fontsize=8, color='black', alpha=0.7)
                     
        ax2.axhline(0, color='gray', linestyle='-', linewidth=0.8, alpha=0.5)
        ax2.tick_params(axis='y', labelcolor=color)
        
        plt.title('台股大盤指數與外資期貨淨未平倉口數走勢疊圖', fontsize=14, fontweight='bold')
        fig.tight_layout()
        
        output_path = "data/futures_trend.png"
        plt.savefig(output_path, dpi=300)
        plt.close()
        print(f"Chart generated and saved to: {output_path}")
        return output_path, aligned_prices
    except Exception as e:
        print(f"Error generating chart: {e}", file=sys.stderr)
    return None, []

def scrape_daily_sbl_data(date_str, cache_dir):
    sbl_map = {}
    headers = HEADERS
    
    taipei_now = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=8)
    is_today = (date_str == taipei_now.strftime("%Y%m%d"))

    # 1. TWSE (TWT93U)
    twse_success = False
    twse_cache = os.path.join(cache_dir, f"SBL_TWSE_{date_str}.json")
    
    if os.path.exists(twse_cache):
        with open(twse_cache, "r", encoding="utf-8") as f:
            try:
                cached_data = json.load(f)
                if "data" in cached_data and len(cached_data["data"]) > 0:
                    for row in cached_data["data"]:
                        if len(row) >= 13:
                            sym = str(row[0]).strip()
                            sbl_map[sym] = {
                                "SBL_Sold": _clean_int(row[9]),
                                "SBL_Returned": _clean_int(row[10]),
                                "SBL_Balance": _clean_int(row[12])
                            }
                    twse_success = True
            except Exception:
                pass
                
    if not twse_success:
        for attempt in range(3):
            try:
                url_twse = f"https://www.twse.com.tw/exchangeReport/TWT93U?response=json&date={date_str}"
                print(f"Fetching TWSE SBL for {date_str} (Attempt {attempt+1})...")
                res = requests.get(url_twse, headers=headers, timeout=20)
                if res.status_code == 200:
                    data = res.json()
                    if "data" in data and len(data["data"]) > 0:
                        with open(twse_cache, "w", encoding="utf-8") as f:
                            json.dump(data, f, ensure_ascii=False, indent=2)
                        for row in data["data"]:
                            if len(row) >= 13:
                                sym = str(row[0]).strip()
                                sbl_map[sym] = {
                                    "SBL_Sold": _clean_int(row[9]),
                                    "SBL_Returned": _clean_int(row[10]),
                                    "SBL_Balance": _clean_int(row[12])
                                }
                        twse_success = True
                        break
                    elif data.get("stat") == "NO_DATA" or ("data" in data and len(data["data"]) == 0):
                        print(f"TWSE SBL returned empty or NO_DATA on attempt {attempt+1}")
                        if not is_today:
                            with open(twse_cache, "w", encoding="utf-8") as f:
                                json.dump(data, f, ensure_ascii=False, indent=2)
                        twse_success = True
                        break
                else:
                    print(f"TWSE SBL returned status code {res.status_code} on attempt {attempt+1}")
            except Exception as e:
                print(f"Error fetching TWSE SBL on attempt {attempt+1}: {e}", file=sys.stderr)
            if not twse_success and attempt < 2:
                time.sleep(2)
                
        if not twse_success:
            print("Warning: Failed to fetch TWSE SBL data after 3 attempts. SBL data will default to 0.", file=sys.stderr)

    # 2. TPEx (margin_sbl)
    tpex_success = False
    tpex_cache = os.path.join(cache_dir, f"SBL_TPEX_{date_str}.json")
    
    if os.path.exists(tpex_cache):
        with open(tpex_cache, "r", encoding="utf-8") as f:
            try:
                cached_data = json.load(f)
                if "tables" in cached_data and len(cached_data["tables"]) > 0:
                    table_data = cached_data["tables"][0].get("data", [])
                    for row in table_data:
                        if len(row) >= 13:
                            sym = str(row[0]).strip()
                            sbl_map[sym] = {
                                "SBL_Sold": _clean_int(row[9]),
                                "SBL_Returned": _clean_int(row[10]),
                                "SBL_Balance": _clean_int(row[12])
                            }
                    tpex_success = True
            except Exception:
                pass
                
    if not tpex_success:
        roc_date = western_to_roc_date(date_str)
        for attempt in range(3):
            try:
                url_tpex = f"https://www.tpex.org.tw/web/stock/margin_trading/margin_sbl/margin_sbl_result.php?l=zh-tw&d={roc_date}&s=0,asc,0&o=json"
                print(f"Fetching TPEx SBL for {roc_date} (Attempt {attempt+1})...")
                res = requests.get(url_tpex, headers=headers, timeout=25)
                if res.status_code == 200:
                    data = res.json()
                    if "tables" in data and len(data["tables"]) > 0 and len(data["tables"][0].get("data", [])) > 0:
                        with open(tpex_cache, "w", encoding="utf-8") as f:
                            json.dump(data, f, ensure_ascii=False, indent=2)
                        table_data = data["tables"][0].get("data", [])
                        for row in table_data:
                            if len(row) >= 13:
                                sym = str(row[0]).strip()
                                sbl_map[sym] = {
                                    "SBL_Sold": _clean_int(row[9]),
                                    "SBL_Returned": _clean_int(row[10]),
                                    "SBL_Balance": _clean_int(row[12])
                                }
                        tpex_success = True
                        break
                    else:
                        print(f"TPEx SBL returned empty or invalid data on attempt {attempt+1}")
                        if not is_today:
                            with open(tpex_cache, "w", encoding="utf-8") as f:
                                json.dump(data, f, ensure_ascii=False, indent=2)
                        tpex_success = True
                        break
                else:
                    print(f"TPEx SBL returned status code {res.status_code} on attempt {attempt+1}")
            except Exception as e:
                print(f"Error fetching TPEx SBL on attempt {attempt+1}: {e}", file=sys.stderr)
            if not tpex_success and attempt < 2:
                time.sleep(2)
                
        if not tpex_success:
            print("Warning: Failed to fetch TPEx SBL data after 3 attempts. SBL data will default to 0.", file=sys.stderr)
            
    return sbl_map

def scrape_daily_stock_quotes(date_str):
    quotes_map = {}
    headers = HEADERS
    
    quotes_map.update(scrape_twse_quotes(date_str))

    # 2. TPEx
    tpex_success = False
    for attempt in range(3):
        try:
            url_tpex = "https://www.tpex.org.tw/openapi/v1/tpex_mainboard_daily_close_quotes"
            print(f"Fetching TPEx OpenAPI quotes (Attempt {attempt+1})...")
            res = requests.get(url_tpex, headers=headers, timeout=25)
            if res.status_code == 200:
                data = res.json()
                print(f"Parsing TPEx quotes ({len(data)} stocks)...")
                for r in data:
                    sym = str(r.get("SecuritiesCompanyCode", "")).strip()

                    vol = _clean_float(r.get("TradingShares", 0)) // 1000
                    open_p = _clean_float(r.get("Open", 0))
                    high_p = _clean_float(r.get("High", 0))
                    low_p = _clean_float(r.get("Low", 0))
                    close_p = _clean_float(r.get("Close", 0))
                    change_val = _clean_float(r.get("Change", 0))

                    quotes_map[sym] = {
                        "Open": open_p,
                        "High": high_p,
                        "Low": low_p,
                        "Close": close_p,
                        "Change": change_val,
                        "Volume": int(vol)
                    }
                tpex_success = True
                break
            else:
                print(f"TPEx returned status code {res.status_code} on attempt {attempt+1}")
        except Exception as e:
            print(f"Error fetching TPEx daily quotes on attempt {attempt+1}: {e}", file=sys.stderr)
        if not tpex_success and attempt < 2:
            time.sleep(2)

    if not tpex_success:
        raise RuntimeError("Failed to fetch TPEx daily quotes after 3 attempts.")

    return quotes_map


def scrape_twse_quotes(date_str):
    """Listed-market OHLC for `date_str`. TWSE's endpoint honours the date."""
    quotes_map = {}
    headers = HEADERS

    twse_success = False
    for attempt in range(3):
        try:
            url_twse = f"https://www.twse.com.tw/rwd/zh/afterTrading/MI_INDEX?response=json&date={date_str}&type=ALLBUT0999"
            print(f"Fetching TWSE MI_INDEX for {date_str} (Attempt {attempt+1})...")
            res = requests.get(url_twse, headers=headers, timeout=20)
            if res.status_code == 200:
                data = res.json()
                if "tables" in data and len(data["tables"]) > 8:
                    table = data["tables"][8]
                    fields = table.get("fields", [])
                    rows = table.get("data", [])
                    
                    if "證券代號" in fields:
                        print(f"Parsing TWSE quotes ({len(rows)} stocks)...")
                        for r in rows:
                            if len(r) >= 11:
                                sym = str(r[0]).strip()
                                vol = str(r[2]).replace(",", "").strip()
                                open_p = str(r[5]).replace(",", "").strip()
                                high_p = str(r[6]).replace(",", "").strip()
                                low_p = str(r[7]).replace(",", "").strip()
                                close_p = str(r[8]).replace(",", "").strip()
                                
                                vol_val = _clean_float(vol) // 1000
                                open_val = _clean_float(open_p)
                                high_val = _clean_float(high_p)
                                low_val = _clean_float(low_p)
                                close_val = _clean_float(close_p)
                                
                                change_sign = str(r[9]).strip()
                                change_val = _clean_float(str(r[10]).replace(",", "").strip())
                                if "-" in change_sign or "綠" in change_sign:
                                    change_val = -change_val
                                    
                                quotes_map[sym] = {
                                    "Open": open_val,
                                    "High": high_val,
                                    "Low": low_val,
                                    "Close": close_val,
                                    "Change": change_val,
                                    "Volume": int(vol_val)
                                }
                        twse_success = True
                        break
                elif data.get("stat") == "NO_DATA":
                    print(f"TWSE returned NO_DATA on attempt {attempt+1}")
            else:
                print(f"TWSE returned status code {res.status_code} on attempt {attempt+1}")
        except Exception as e:
            print(f"Error fetching TWSE daily quotes on attempt {attempt+1}: {e}", file=sys.stderr)
        if not twse_success and attempt < 2:
            time.sleep(2)

    if not twse_success:
        raise RuntimeError("Failed to fetch TWSE daily quotes after 3 attempts.")

    return quotes_map

def load_market_summary(date_str, cache_dir, is_today=False):
    twse_url = f"https://www.twse.com.tw/rwd/zh/fund/BFI82U?response=json&dayDate={date_str}&type=day"
    twse_cache = os.path.join(cache_dir, f"BFI82U_{date_str}.json")
    twse_data = fetch_data_with_cache(twse_url, twse_cache, is_today)
    
    roc_date = western_to_roc_date(date_str)
    tpex_url = f"https://www.tpex.org.tw/web/stock/3insti/3insti_summary/3itrdsum_result.php?l=zh-tw&t=D&d={roc_date}&p=1&o=json"
    tpex_cache = os.path.join(cache_dir, f"TPEX_BFI82U_{date_str}.json")
    tpex_data = fetch_data_with_cache(tpex_url, tpex_cache, is_today)
    
    summary_rows = []
    
    if twse_data and twse_data.get("stat") == "OK" and "data" in twse_data:
        for row in twse_data["data"]:
            if len(row) >= 4:
                summary_rows.append({
                    "Market": "上市 (TWSE)",
                    "Category": row[0].strip(),
                    "Buy": row[1],
                    "Sell": row[2],
                    "Net": row[3]
                })
                
    tpex_rows = []
    if tpex_data:
        if "tables" in tpex_data and len(tpex_data["tables"]) > 0:
            tpex_rows = tpex_data["tables"][0].get("data", [])
        elif "aaData" in tpex_data:
            tpex_rows = tpex_data["aaData"]
            
    for row in tpex_rows:
        if len(row) >= 4:
            summary_rows.append({
                "Market": "上櫃 (TPEx)",
                "Category": row[0].strip(),
                "Buy": row[1],
                "Sell": row[2],
                "Net": row[3]
            })
            
    return summary_rows

def load_industry_mapping(cache_dir):
    mapping_cache_path = os.path.join(cache_dir, "industry_mapping.json")
    if os.path.exists(mapping_cache_path):
        with open(mapping_cache_path, "r", encoding="utf-8") as f:
            try:
                return json.load(f)
            except Exception:
                pass
                
    print("Downloading industry mapping file...")
    mapping = {}
    
    industry_map = {
        "01": "水泥工業", "02": "食品工業", "03": "塑膠工業", "04": "紡織纖維",
        "05": "電機機械", "06": "電器電纜", "08": "玻璃陶瓷", "09": "造紙工業",
        "10": "鋼鐵工業", "11": "橡膠工業", "12": "汽車工業", "13": "電子工業",
        "14": "建材營造", "15": "航運業", "16": "觀光餐旅", "17": "金融保險",
        "18": "貿易百貨", "19": "綜合", "20": "其他", "21": "化學工業",
        "22": "生技醫療業", "23": "油電燃氣業", "24": "半導體業",
        "25": "電腦及週邊設備業", "26": "光電業", "27": "通信網路業",
        "28": "電子零組件業", "29": "電子通路業", "30": "資訊服務業",
        "31": "其他電子業", "32": "文化創意業", "33": "農業科技業",
        "35": "綠能環保", "36": "數位雲端", "37": "運動休閒", "38": "居家生活"
    }
    
    headers_req = HEADERS
    
    try:
        res_l = requests.get("https://mopsfin.twse.com.tw/opendata/t187ap03_L.csv", headers=headers_req, timeout=15)
        if res_l.status_code == 200:
            res_l.encoding = 'utf-8-sig'
            df_l = pd.read_csv(io.StringIO(res_l.text))
            for _, row in df_l.iterrows():
                code = str(row["公司代號"]).strip()
                ind_code = str(row["產業別"]).strip()
                if len(ind_code) == 1:
                    ind_code = "0" + ind_code
                ind_name = industry_map.get(ind_code, "其他")
                mapping[code] = ind_name
    except Exception as e:
        print(f"Warning: Failed to load TWSE industry mapping: {e}", file=sys.stderr)
        
    try:
        res_o = requests.get("https://mopsfin.twse.com.tw/opendata/t187ap03_O.csv", headers=headers_req, timeout=15)
        if res_o.status_code == 200:
            res_o.encoding = 'utf-8-sig'
            df_o = pd.read_csv(io.StringIO(res_o.text))
            for _, row in df_o.iterrows():
                code = str(row["公司代號"]).strip()
                ind_code = str(row["產業別"]).strip()
                if len(ind_code) == 1:
                    ind_code = "0" + ind_code
                ind_name = industry_map.get(ind_code, "其他")
                mapping[code] = ind_name
    except Exception as e:
        print(f"Warning: Failed to load TPEx industry mapping: {e}", file=sys.stderr)
        
    if mapping:
        with open(mapping_cache_path, "w", encoding="utf-8") as f:
            json.dump(mapping, f, ensure_ascii=False, indent=2)
            
    return mapping

def clean_old_cache(cache_dir, keep_days=45):
    if not os.path.exists(cache_dir):
        return
    try:
        current_time = time.time()
        limit_seconds = keep_days * 24 * 60 * 60
        cleaned_count = 0
        for filename in os.listdir(cache_dir):
            if filename in ("industry_mapping.json", "NotoSansCJKtc-Regular.otf"):
                continue
            filepath = os.path.join(cache_dir, filename)
            if os.path.isfile(filepath):
                file_mtime = os.path.getmtime(filepath)
                if (current_time - file_mtime) > limit_seconds:
                    os.remove(filepath)
                    cleaned_count += 1
        if cleaned_count > 0:
            print(f"Cleaned up {cleaned_count} old cache files.")
    except Exception:
        pass

def main():
    parser = argparse.ArgumentParser(description="Build TWStockWatch static data.")
    parser.add_argument(
        "--date", type=str, default=None,
        help="Target date in YYYYMMDD format (e.g. 20260630). "
             "If omitted, uses the actual time when the script starts, same as before."
    )
    args = parser.parse_args()

    cache_dir = "data/cache"

    real_taipei_now = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=8)

    if args.date:
        try:
            datetime.datetime.strptime(args.date, "%Y%m%d")
        except ValueError:
            print(f"Invalid --date value '{args.date}', expected YYYYMMDD format.", file=sys.stderr)
            sys.exit(1)

        if args.date == real_taipei_now.strftime("%Y%m%d"):
            # Caller explicitly asked for today - still respect the 15:00
            # cutoff below, since today's data may not exist yet.
            taipei_now = real_taipei_now
        else:
            # A specific past date was requested - treat it as end-of-day
            # (market already closed), so the 15:00 cutoff doesn't apply.
            tz_taipei = datetime.timezone(datetime.timedelta(hours=8))
            taipei_now = datetime.datetime.strptime(args.date, "%Y%m%d").replace(
                hour=23, minute=59, second=0, tzinfo=tz_taipei
            )
        print(f"Running with manually specified date: {args.date}")
    else:
        taipei_now = real_taipei_now

    today_str = taipei_now.strftime("%Y%m%d")
    real_today_str = real_taipei_now.strftime("%Y%m%d")

    # 1. Collect the latest 20 trading days of T86 by asking TWSE/TPEx directly.
    # T86 decides which days are trading days; Yahoo is no longer in this path.
    # Skip today only before 15:00 Taipei, when the session data is not out yet.
    skip_today = (today_str == real_today_str
                  and real_taipei_now.time() < datetime.time(15, 0))
    day_dfs, t86_truncated_at = collect_t86_history(
        today_str, cache_dir, n=20, today_str=real_today_str, skip_today=skip_today
    )  # newest first

    if not day_dfs:
        print("No stock trading data found.", file=sys.stderr)
        sys.exit(1)

    if t86_truncated_at:
        print(f"Note: streak window truncated to {len(day_dfs)} day(s) because "
              f"{t86_truncated_at} could not be fetched; it will self-heal on a "
              f"later run.", file=sys.stderr)

    latest_active_date = day_dfs[0][0]
    print(f"Latest Active Date for Data: {latest_active_date}")
    
    # 3. Calculate Streaks
    df_list = [item[1] for item in day_dfs]
    df_streaks = calculate_streaks(df_list)
    
    # 4. Fetch Daily closing quotes for OHL and Price data
    quotes_map = scrape_daily_stock_quotes(latest_active_date)
    
    # 5. Fetch Daily SBL (Securities Borrowing & Lending) data
    sbl_map = scrape_daily_sbl_data(latest_active_date, cache_dir)
    
    # 6. Load industry mapping
    industry_mapping = load_industry_mapping(cache_dir)

    # 6b. Reference price level across each current streak
    avg_prices = compute_streak_avg_prices(day_dfs, cache_dir)

    # 7. Merge quotes, SBL, and industry mapping into streaks
    final_streaks = []
    for _, row in df_streaks.iterrows():
        sym = row["Symbol"]
        quote = quotes_map.get(sym, {"Open": 0.0, "High": 0.0, "Low": 0.0, "Close": 0.0, "Change": 0.0, "Volume": 0})
        ind = industry_mapping.get(sym, "其他")
        sbl = sbl_map.get(sym, {"SBL_Sold": 0, "SBL_Returned": 0, "SBL_Balance": 0})
        avg = avg_prices.get(sym, {})
        
        f_streak = int(row["Foreign_Streak"])
        t_streak = int(row["Trust_Streak"])
        
        dual_buy_streak = 0
        dual_sell_streak = 0
        
        if f_streak > 0 and t_streak > 0:
            dual_buy_streak = f_streak if f_streak < t_streak else t_streak
            
        elif f_streak < 0 and t_streak < 0:
            dual_sell_streak = f_streak if abs(f_streak) < abs(t_streak) else t_streak
        # ----------------------------------------------------
        
        final_streaks.append({
            "Symbol": sym,
            "Name": row["Name"],
            "Market": row["Market"],
            "Industry": ind,
            "Foreign_Streak": f_streak,
            "Foreign_Latest": int(row["Foreign_Latest"]),
            "Trust_Streak": t_streak,
            "Trust_Latest": int(row["Trust_Latest"]),
            "Dealer_Streak": int(row["Dealer_Streak"]),
            "Dealer_Latest": int(row["Dealer_Latest"]),
            "DealerProp_Streak": int(row["DealerProp_Streak"]),
            "DealerProp_Latest": int(row["DealerProp_Latest"]),
            "DealerHedge_Streak": int(row["DealerHedge_Streak"]),
            "DealerHedge_Latest": int(row["DealerHedge_Latest"]),
            "Total_Streak": int(row["Total_Streak"]),
            "Total_Latest": int(row["Total_Latest"]),
            
            "Dual_Buy_Streak": dual_buy_streak,
            "Dual_Sell_Streak": dual_sell_streak,
            
            "Open": quote["Open"],
            "High": quote["High"],
            "Low": quote["Low"],
            "Close": quote["Close"],
            "Change": quote["Change"],
            "Volume": quote["Volume"],
            "SBL_Sold": int(sbl["SBL_Sold"]),
            "SBL_Returned": int(sbl["SBL_Returned"]),
            "SBL_Balance": int(sbl["SBL_Balance"]),

            # Share-weighted price across the current streak; a reference level,
            # not a cost basis (see compute_streak_avg_prices).
            "Foreign_StreakAvgPrice": avg.get("Foreign"),
            "Trust_StreakAvgPrice": avg.get("Trust")
        })

    # Read existing files to detect changes later
    def read_file_safe(path):
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    return f.read()
            except Exception:
                pass
        return None

    old_streaks = read_file_safe("data/streaks.json")
    old_summary = read_file_safe("data/market_summary.json")
    old_futures = read_file_safe("data/futures_options.json")

    # Write streaks.json
    with open("data/streaks.json", "w", encoding="utf-8") as f:
        json.dump({
            "Date": latest_active_date,
            "Data": final_streaks
        }, f, ensure_ascii=False, indent=2)
    print("Saved data/streaks.json")

    # 6c. Score yesterday's signals and open today's
    try:
        update_scoreboard(latest_active_date, final_streaks, cache_dir)
        print("Saved data/scoreboard.json")
    except Exception as e:
        # The scoreboard is a retrospective extra; never let it fail the build.
        print(f"Warning: scoreboard update failed: {e}", file=sys.stderr)

    # 6b. 將今日焦點 Top 10 注入 index.html（供搜尋引擎與無 JS 環境直接閱讀）
    try:
        from inject_rankings import inject
        inject()
    except Exception as e:
        print(f"[warn] inject_rankings 注入失敗（不影響資料產出）：{e}")

    # 7. Load Market Summary
    summary_data = load_market_summary(latest_active_date, cache_dir, (latest_active_date == today_str))
    with open("data/market_summary.json", "w", encoding="utf-8") as f:
        json.dump({
            "Date": latest_active_date,
            "Data": summary_data
        }, f, ensure_ascii=False, indent=2)
    print("Saved data/market_summary.json")
    
    # 8. Load Futures & Options
    # Walk back from today_str rather than from latest_active_date: TAIFEX decides
    # which days have OI, independently of Yahoo's calendar and of T86 succeeding.
    fresh_oi = collect_futures_oi_history(
        today_str, cache_dir, n=20, today_str=real_taipei_now.strftime("%Y%m%d")
    )  # newest first
    fresh_entries = [flatten_oi_entry(d, oi) for d, oi in fresh_oi]
    futures_history = merge_futures_history(
        load_published_futures_history(), fresh_entries, n=20
    )  # newest first

    # Generate Chart & aligned prices (chart wants oldest to newest)
    chart_path, aligned_prices = generate_trend_chart(list(reversed(futures_history)), cache_dir)
    
    opt_data = fetch_taifex_options_max_oi(latest_active_date, cache_dir)
    is_settlement, settlement_date = check_settlement_week(latest_active_date)
    
    futures_options_data = {
        "Date": latest_active_date,
        "Settlement": {
            "IsSettlementWeek": is_settlement,
            "SettlementDate": settlement_date
        },
        "Options": opt_data,
        "FuturesHistory": futures_history,
        "AlignedPrices": aligned_prices
    }
    
    with open("data/futures_options.json", "w", encoding="utf-8") as f:
        json.dump(futures_options_data, f, ensure_ascii=False, indent=2)
    print("Saved data/futures_options.json")
    
    # 9. Clean Cache
    clean_old_cache(cache_dir, keep_days=45)
    print("Data compilation completed successfully!")


    # Read new files to check for changes
    new_streaks = read_file_safe("data/streaks.json")
    new_summary = read_file_safe("data/market_summary.json")
    new_futures = read_file_safe("data/futures_options.json")

    def json_changed(old_str, new_str):
        if not old_str or not new_str:
            return True
        try:
            return json.loads(old_str) != json.loads(new_str)
        except Exception:
            return True

    data_changed = (
        json_changed(old_streaks, new_streaks) or
        json_changed(old_summary, new_summary) or
        json_changed(old_futures, new_futures)
    )

    last_update_path = "data/last_update.json"
    if data_changed or not os.path.exists(last_update_path):
        utc_now = datetime.datetime.now(datetime.timezone.utc)
        update_data = {
            "last_updated": utc_now.strftime("%Y-%m-%dT%H:%M:%S.%fZ")
        }
        with open(last_update_path, "w", encoding="utf-8") as f:
            json.dump(update_data, f, indent=2)
        print(f"Updated last_update.json: {utc_now.isoformat()}")
    else:
        print("Data is identical. Skipping last_update.json update.")

if __name__ == "__main__":
    main()
