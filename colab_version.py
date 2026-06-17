#@title 🚀 台股法人籌碼與連買連賣查詢系統 { display-mode: "form" }
#@markdown 請在下方輸入股票代碼（多檔請用空白分隔，例如 `2330 2454`）。
#@markdown **留空直接按執行**，則會顯示「大盤法人買賣超金額」與「外資/投信連買連賣排行榜 Top 10」。

# 1. 安裝相依套件 (Colab 已內建 requests 與 pandas，只需安裝 yfinance、tabulate、wcwidth)
print("正在準備環境，請稍候...")
!pip install -q yfinance tabulate wcwidth

import os
import sys
import json
import time
import datetime
import requests
import pandas as pd

# 強制重新載入 tabulate 以確保能偵測並使用剛安裝好的 wcwidth 套件
if "tabulate" in sys.modules:
    try:
        import importlib
        importlib.reload(sys.modules["tabulate"])
    except Exception:
        pass

from tabulate import tabulate
try:
    import tabulate as tb
    tb.WIDE_CHARS_MODE = True
except Exception:
    pass

def is_in_ipython():
    try:
        from IPython import get_ipython
        if get_ipython() is not None:
            return True
    except Exception:
        pass
    return False

def print_beautiful_table(rows, headers, col_aligns):
    """通用、防破格、支援 CJK 雙字元與 ANSI 色彩代碼的表格渲染器"""
    if is_in_ipython():
        try:
            from IPython.display import display, HTML
            import re
            
            def clean_ansi_to_html(text):
                text_str = str(text)
                # 採用亮色模式高對比之精緻小圓角膠囊標籤 (rose-600 與 emerald-600)
                text_str = text_str.replace('\x1b[91m', '<span style="display: inline-block; padding: 2px 8px; border-radius: 4px; background: rgba(225, 29, 72, 0.06); color: #e11d48; font-weight: 600; border: 1px solid rgba(225, 29, 72, 0.15); font-variant-numeric: tabular-nums;">')
                text_str = text_str.replace('\x1b[92m', '<span style="display: inline-block; padding: 2px 8px; border-radius: 4px; background: rgba(5, 150, 105, 0.06); color: #059669; font-weight: 600; border: 1px solid rgba(5, 150, 105, 0.15); font-variant-numeric: tabular-nums;">')
                text_str = text_str.replace('\x1b[1m', '<strong style="font-weight: 600; color: #0f172a;">')
                text_str = text_str.replace('\x1b[0m', '</span></strong>')
                text_str = re.sub(r'\x1b\[[0-9;]*[mG]', '', text_str)
                return text_str

            # 載入簡約純白卡片設計與 Google Fonts Inter 字型
            html = '<link rel="preconnect" href="https://fonts.googleapis.com">'
            html += '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
            html += '<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&display=swap" rel="stylesheet">'
            html += '<div style="overflow-x:auto; margin: 16px 0; border-radius: 10px; border: 1px solid #e2e8f0; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05), 0 2px 4px -2px rgba(0, 0, 0, 0.05);">'
            html += '<table style="border-collapse: collapse; width: 100%; font-family: \'Inter\', -apple-system, BlinkMacSystemFont, \'Segoe UI\', Roboto, sans-serif; font-size: 13px; background: #ffffff; color: #334155; text-align: left;">'
            
            # Header
            html += '<tr style="background: #f8fafc; border-bottom: 2px solid #e2e8f0;">'
            for h, align in zip(headers, col_aligns):
                align_css = f"text-align: {align}"
                html += f'<th style="padding: 12px 16px; font-weight: 600; font-size: 11px; text-transform: uppercase; letter-spacing: 0.05em; color: #64748b; border: none; {align_css};">{h}</th>'
            html += '</tr>'
            
            # Rows
            for idx, row in enumerate(rows):
                bg_color = "#f8fafc" if idx % 2 == 1 else "#ffffff"
                html += f'<tr style="background: {bg_color}; border-bottom: 1px solid #f1f5f9; transition: background 0.15s;" onmouseover="this.style.background=\'#f1f5f9\'" onmouseout="this.style.background=\'{bg_color}\'">'
                for val, align in zip(row, col_aligns):
                    align_css = f"text-align: {align}"
                    cleaned_val = clean_ansi_to_html(val)
                    html += f'<td style="padding: 12px 16px; border: none; font-variant-numeric: tabular-nums; {align_css};">{cleaned_val}</td>'
                html += '</tr>'
                
            html += '</table></div>'
            display(HTML(html))
            return
        except Exception:
            pass  # Fall back to text printing if HTML display fails
            
    # --- 以下為傳統文字表格輸出備用方案 ---
    import re
    import unicodedata
    
    ansi_escape = re.compile(r'\x1b\[[0-9;]*[mG]')
    
    def get_cjk_width(text):
        clean_text = ansi_escape.sub('', str(text))
        width = 0
        for char in clean_text:
            if unicodedata.east_asian_width(char) in ('W', 'F', 'A'):
                width += 2
            else:
                width += 1
        return width

    def pad_cjk(text, width, align):
        text_str = str(text)
        visual_width = get_cjk_width(text_str)
        padding_needed = max(0, width - visual_width)
        if align == "left":
            return text_str + " " * padding_needed
        elif align == "right":
            return " " * padding_needed + text_str
        else:
            left_pad = padding_needed // 2
            right_pad = padding_needed - left_pad
            return " " * left_pad + text_str + " " * right_pad

    num_cols = len(headers)
    col_widths = [get_cjk_width(h) for h in headers]
    
    for row in rows:
        for i in range(min(num_cols, len(row))):
            col_widths[i] = max(col_widths[i], get_cjk_width(row[i]))
            
    def make_border(left, middle, right, char="-"):
        parts = []
        for w in col_widths:
            parts.append(char * (w + 2))
        return left + middle.join(parts) + right

    top_border = make_border("+", "+", "+", "-")
    header_sep = make_border("+", "+", "+", "=")
    bottom_border = make_border("+", "+", "+", "-")
    
    print(top_border)
    header_parts = [pad_cjk(h, w, align) for h, w, align in zip(headers, col_widths, col_aligns)]
    print("| " + " | ".join(header_parts) + " |")
    print(header_sep)
    
    for row in rows:
        row_parts = [pad_cjk(val, w, align) for val, w, align in zip(row, col_widths, col_aligns)]
        print("| " + " | ".join(row_parts) + " |")
        
    print(bottom_border)

# 定義 Colab 表單變數
stock_codes = "" #@param {type:"string"}
#@markdown **使用 Google Drive 快取以加速執行（推薦，可避免重複下載）**
use_gdrive_cache = True #@param {type:"boolean"}
#@markdown **連買/連賣天數區間篩選（僅在大盤模式下生效）**
min_streak_days = 3 #@param {type:"integer"}
max_streak_days = 5 #@param {type:"integer"}
#@markdown **呈現數量上限 (可設定為 0 表示不限制數量，或輸入 50, 100 等)**
display_limit = 50 #@param {type:"integer"}

BOLD = "\033[1m"
RESET = "\033[0m"
RED = "\033[91m"     # 漲/買超 (台股紅)
GREEN = "\033[92m"   # 跌/賣超 (台股綠)

def western_to_roc_date(date_str):
    year = int(date_str[:4])
    month = date_str[4:6]
    day = date_str[6:]
    roc_year = year - 1911
    return f"{roc_year}/{month}/{day}"

def fetch_data_with_cache(url, cache_path, is_today=False, delay=0.8):
    # Colab 環境中若不需要本機快取，我們還是保留它，以免多次點擊時速度太慢
    if os.path.exists(cache_path):
        import re
        is_recent_no_data = False
        date_match = re.search(r'\d{8}', os.path.basename(cache_path))
        if date_match:
            try:
                file_date = datetime.datetime.strptime(date_match.group(0), "%Y%m%d").date()
                if (datetime.date.today() - file_date).days <= 3:
                    is_recent_no_data = True
            except Exception:
                pass
                
        with open(cache_path, "r", encoding="utf-8") as f:
            try:
                data = json.load(f)
                if data.get("stat") == "NO_DATA" and (is_today or is_recent_no_data):
                    pass
                else:
                    return data
            except Exception:
                pass
                
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36"
    }
    
    url_name = url.split("?")[0].split("/")[-1]
    time.sleep(delay)
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            data = response.json()
            os.makedirs(os.path.dirname(cache_path), exist_ok=True)
            
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
    except Exception as e:
        pass
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
        
    idx_total = -1
    if "三大法人買賣超股數" in fields:
        idx_total = fields.index("三大法人買賣超股數")
    else:
        idx_total = 18
        
    rows = []
    for r in data:
        def clean(val):
            if val is None:
                return 0
            val_str = str(val).replace(",", "").strip()
            try:
                return int(val_str)
            except ValueError:
                return 0
                
        def get_val_safe(row, idx):
            if idx >= 0 and idx < len(row):
                return clean(row[idx])
            return 0
            
        symbol = str(r[idx_symbol]).strip() if idx_symbol < len(r) else ""
        name = str(r[idx_name]).strip() if idx_name < len(r) else ""
        
        foreign = get_val_safe(r, idx_foreign)
        trust = get_val_safe(r, idx_trust)
        dealer = get_val_safe(r, idx_dealer)
        total = get_val_safe(r, idx_total)
        
        rows.append({
            "Symbol": symbol,
            "Name": name,
            "Foreign": foreign,
            "Trust": trust,
            "Dealer": dealer,
            "Total": total
        })
    return pd.DataFrame(rows)

def parse_tpex_t86(api_response):
    # 支援新版 TPEx API JSON 格式 (tables) 與舊版格式 (aaData)
    data = []
    if "tables" in api_response and len(api_response["tables"]) > 0:
        data = api_response["tables"][0].get("data", [])
    elif "aaData" in api_response:
        data = api_response["aaData"]
        
    rows = []
    for r in data:
        # 新版格式有 24 或 25 個欄位
        if len(r) >= 24:
            symbol = str(r[0]).strip()
            name = str(r[1]).strip()
            
            def clean(val):
                if val is None:
                    return 0
                val_str = str(val).replace(",", "").strip()
                try:
                    return int(val_str)
                except ValueError:
                    return 0
                    
            foreign = clean(r[10]) # 外資及陸資合計買賣超
            trust = clean(r[13])   # 投信買賣超
            dealer = clean(r[22])  # 自營商合計買賣超
            total = clean(r[23])   # 三大法人買賣超合計
            
            rows.append({
                "Symbol": symbol,
                "Name": name,
                "Foreign": foreign,
                "Trust": trust,
                "Dealer": dealer,
                "Total": total
            })
        elif len(r) >= 19:
            # 舊版格式相容
            symbol = str(r[0]).strip()
            name = str(r[1]).strip()
            
            def clean(val):
                if val is None:
                    return 0
                val_str = str(val).replace(",", "").strip()
                try:
                    return int(val_str)
                except ValueError:
                    return 0
                    
            foreign = clean(r[4])
            trust = clean(r[10])
            dealer = clean(r[17])
            total = clean(r[18])
            
            rows.append({
                "Symbol": symbol,
                "Name": name,
                "Foreign": foreign,
                "Trust": trust,
                "Dealer": dealer,
                "Total": total
            })
    return pd.DataFrame(rows)

def load_t86_both_markets(date_str, cache_dir, is_today=False):
    twse_url = f"https://www.twse.com.tw/rwd/zh/fund/T86?response=json&date={date_str}&selectType=ALLBUT0999"
    twse_cache = os.path.join(cache_dir, f"T86_{date_str}.json")
    twse_data = fetch_data_with_cache(twse_url, twse_cache, is_today)
    
    # 若證交所明確回傳沒有資料 (代表當日休市/未開盤)，則直接跳過櫃買中心查詢，節省一半請求時間
    if twse_data and twse_data.get("stat") == "NO_DATA":
        if not is_today:
            # 同步將 TPEx 快取寫入 NO_DATA，避免下次重試
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
    
    has_twse = twse_data and twse_data.get("stat") == "OK" and "data" in twse_data and len(twse_data["data"]) > 0
    
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

def find_latest_trading_days(n=20, cache_dir=".cache"):
    trading_days = []
    
    # 嘗試從 Yahoo Finance 下載大盤指數歷史，以取得準確的交易日列表 (避開週末與國定假日)
    # 這能在一秒內得知哪些日期才是真正的交易日，避免盲目發送 HTTP 請求給證交所 API
    try:
        import yfinance as yf
        print("正在透過 Yahoo Finance 取得最近交易日列表...")
        ticker = yf.Ticker("^TWII")
        # 抓取大約 n * 2 天的歷史資料，確保能有足夠的交易日
        hist = ticker.history(period=f"{n * 2}d")
        if not hist.empty:
            # 取得所有的交易日，格式為 YYYYMMDD
            all_trading_dates = hist.index.strftime("%Y%m%d").tolist()
            # 我們需要由新到舊 (倒序) 的日期
            all_trading_dates = sorted(list(set(all_trading_dates)), reverse=True)
            
            today_str = datetime.date.today().strftime("%Y%m%d")
            
            for date_str in all_trading_dates:
                if len(trading_days) >= n:
                    break
                is_today = (date_str == today_str)
                # 若是今天，且時間尚未到下午 3:00，代表今天法人資料還沒出來，跳過
                if is_today and datetime.datetime.now().time() < datetime.time(15, 0):
                    continue
                    
                df = load_t86_both_markets(date_str, cache_dir, is_today)
                if df is not None:
                    trading_days.append((date_str, df))
            
            if len(trading_days) >= n:
                return trading_days
    except Exception as e:
        print(f"無法透過 Yahoo Finance 取得交易日列表 ({e})，改用傳統西元曆回推。")
        
    # === 備用方案：若 Yahoo Finance 連線失敗，採用傳統西元曆逐日回推 ===
    trading_days = []
    current_date = datetime.date.today()
    
    if current_date.weekday() == 5:
        current_date -= datetime.timedelta(days=1)
    elif current_date.weekday() == 6:
        current_date -= datetime.timedelta(days=2)
        
    checked_days = 0
    max_days_to_check = n * 3
    today_str = datetime.date.today().strftime("%Y%m%d")
    
    while len(trading_days) < n and checked_days < max_days_to_check:
        if current_date.weekday() in (5, 6):
            current_date -= datetime.timedelta(days=1)
            checked_days += 1
            continue

        date_str = current_date.strftime("%Y%m%d")
        is_today = (date_str == today_str)
        
        if is_today and datetime.datetime.now().time() < datetime.time(15, 0):
            current_date -= datetime.timedelta(days=1)
            checked_days += 1
            continue
            
        df = load_t86_both_markets(date_str, cache_dir, is_today)
        if df is not None:
            trading_days.append((date_str, df))
            
        current_date -= datetime.timedelta(days=1)
        checked_days += 1
        
    return trading_days

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
    for sym in all_symbols:
        data = symbol_data[sym]
        foreign_streak = get_streak_days(data["Foreign"])
        trust_streak = get_streak_days(data["Trust"])
        dealer_streak = get_streak_days(data["Dealer"])
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
            "Total_Streak": total_streak,
            "Total_Latest": data["Total"][0]
        })
        
    return pd.DataFrame(streak_results)

def fetch_taifex_futures_oi(date_str, cache_dir):
    """從期交所網頁抓取台指期貨三大法人多空未平倉部位並進行本地快取"""
    cache_path = os.path.join(cache_dir, f"futures_oi_{date_str}.json")
    if os.path.exists(cache_path):
        with open(cache_path, "r", encoding="utf-8") as f:
            try:
                return json.load(f)
            except Exception:
                pass
                
    formatted_date = f"{date_str[:4]}/{date_str[4:6]}/{date_str[6:]}"
    url = "https://www.taifex.com.tw/cht/3/futContractsDate"
    payload = {"queryDate": formatted_date}
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36"
    }
    
    print(f"正在從期交所獲取期貨三大法人部位資料... ({formatted_date})")
    time.sleep(0.8) # 友善延遲
    
    try:
        from bs4 import BeautifulSoup
        res = requests.post(url, data=payload, headers=headers, timeout=10)
        if res.status_code == 200:
            soup = BeautifulSoup(res.text, "html.parser")
            rows = soup.find_all("tr")
            for i, r in enumerate(rows):
                cells = [td.get_text().strip() for td in r.find_all(["td", "th"])]
                if len(cells) > 1 and "臺股期貨" in cells[1]:
                    def clean_int(val):
                        return int(val.replace(",", "").strip())
                    
                    # 自營商
                    dealers_long = clean_int(cells[9])
                    dealers_short = clean_int(cells[11])
                    dealers_net = clean_int(cells[13])
                    
                    # 投信
                    cells_trust = [td.get_text().strip() for td in rows[i+1].find_all(["td", "th"])]
                    trust_long = clean_int(cells_trust[7])
                    trust_short = clean_int(cells_trust[9])
                    trust_net = clean_int(cells_trust[11])
                    
                    # 外資及陸資
                    cells_foreign = [td.get_text().strip() for td in rows[i+2].find_all(["td", "th"])]
                    foreign_long = clean_int(cells_foreign[7])
                    foreign_short = clean_int(cells_foreign[9])
                    foreign_net = clean_int(cells_foreign[11])
                    
                    result = {
                        "Date": date_str,
                        "Dealers": {"Long": dealers_long, "Short": dealers_short, "Net": dealers_net},
                        "Trust": {"Long": trust_long, "Short": trust_short, "Net": trust_net},
                        "Foreign": {"Long": foreign_long, "Short": foreign_short, "Net": foreign_net}
                    }
                    
                    os.makedirs(cache_dir, exist_ok=True)
                    with open(cache_path, "w", encoding="utf-8") as f:
                        json.dump(result, f, ensure_ascii=False, indent=2)
                    return result
    except Exception:
        pass
    return None

def fetch_taifex_options_max_oi(date_str, cache_dir):
    """從期交所網頁抓取台指選擇權每日交易行情，找出最大未平倉量履約價並進行本地快取"""
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
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36"
    }
    
    print(f"正在從期交所獲取選擇權未平倉資料... ({formatted_date})")
    time.sleep(0.8) # 友善延遲
    
    try:
        from bs4 import BeautifulSoup
        from collections import defaultdict
        res = requests.post(url, data=payload, headers=headers, timeout=10)
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
                
                os.makedirs(cache_dir, exist_ok=True)
                with open(cache_path, "w", encoding="utf-8") as f:
                    json.dump(result, f, ensure_ascii=False, indent=2)
                return result
    except Exception:
        pass
    return None

def check_settlement_week(date_str):
    """判定是否為當月台指期/選擇權結算週 (第三個星期三)"""
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
    """下載大盤指數收盤價，並與外資期貨淨未平倉口數繪製雙 y 軸疊圖 (Colab 版直接顯示)"""
    import yfinance as yf
    import matplotlib.pyplot as plt
    import matplotlib
    
    # 支援繁體中文的字型設定
    # 在 Linux/Colab 上自動下載思源黑體 (Noto Sans CJK TC) 以解決中文亂碼/豆腐字問題
    font_name = 'Microsoft JhengHei'
    import sys
    if sys.platform.startswith('linux'):
        font_path = os.path.join(cache_dir, "NotoSansCJKtc-Regular.otf")
        if not os.path.exists(font_path):
            import urllib.request
            print("正在下載思源黑體 (Noto Sans CJK TC) 以解決 Colab 中文顯示問題 (僅首次下載)...")
            try:
                os.makedirs(cache_dir, exist_ok=True)
                urllib.request.urlretrieve("https://github.com/googlefonts/noto-cjk/raw/main/Sans/OTF/TraditionalChinese/NotoSansCJKtc-Regular.otf", font_path)
            except Exception as e:
                print(f"中文字型下載失敗 ({e})，圖表中文可能無法正常顯示。")
                
        if os.path.exists(font_path):
            try:
                import matplotlib.font_manager as fm
                fm.fontManager.addfont(font_path)
                prop = fm.FontProperties(fname=font_path)
                font_name = prop.get_name()
            except Exception:
                pass
                
    matplotlib.rcParams['font.sans-serif'] = [font_name, 'Microsoft JhengHei', 'DFKai-SB', 'SimHei', 'sans-serif']
    matplotlib.rcParams['axes.unicode_minus'] = False # 解決負號顯示為方塊的問題
    
    dates = [item[0] for item in futures_history]
    foreign_nets = [item[1]["Foreign"]["Net"] for item in futures_history]
    
    if not dates:
        return
        
    start_date_str = f"{dates[0][:4]}-{dates[0][4:6]}-{dates[0][6:]}"
    end_date = datetime.datetime.strptime(dates[-1], "%Y%m%d") + datetime.timedelta(days=2)
    end_date_str = end_date.strftime("%Y-%m-%d")
    
    try:
        print("正在從 Yahoo Finance 下載大盤指數歷史價格...")
        ticker = yf.Ticker("^TWII")
        hist = ticker.history(start=start_date_str, end=end_date_str)
        if hist.empty:
            print("無法取得大盤指數價格，疊圖失敗。")
            return
            
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
            print("日期對齊失敗，疊圖失敗。")
            return
            
        fig, ax1 = plt.subplots(figsize=(10, 5))
        
        # 1. 繪製大盤指數 (左 y 軸)
        color = 'tab:blue'
        ax1.set_xlabel('交易日', fontweight='bold')
        ax1.set_ylabel('大盤收盤指數', color=color, fontweight='bold')
        ax1.plot(aligned_dates, aligned_prices, color=color, marker='o', linewidth=2, label='大盤指數')
        ax1.tick_params(axis='y', labelcolor=color)
        ax1.grid(True, linestyle='--', alpha=0.5)
        
        # 2. 建立右 y 軸繪製外資淨 OI (右 y 軸)
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
        plt.show()
        return None, aligned_prices
    except Exception as e:
        print(f"生成疊圖時發生錯誤: {e}")
    return None, []

def analyze_market_sentiment(futures_history, aligned_prices, opt_data, is_settlement, settlement_date):
    """根據期貨、選擇權與大盤指數走勢，進行大盤籌碼綜合智慧分析 (Colab 專屬 Emoji 美化版)"""
    print(f"\n{BOLD}================================================================================{RESET}")
    print(f"{BOLD}       📊 大盤籌碼面綜合智慧分析 (Smart Market Sentiment Analysis) 📊{RESET}")
    print(f"{BOLD}================================================================================{RESET}")
    
    # Step 1：看外資期貨淨 OI
    latest_oi = futures_history[-1][1]["Foreign"]["Net"]
    prev_oi = futures_history[-2][1]["Foreign"]["Net"] if len(futures_history) > 1 else latest_oi
    oi_diff = latest_oi - prev_oi
    
    print(f"{BOLD}【Step 1：外資期貨淨未平倉 (OI) 動態】{RESET}")
    if latest_oi < 0:
        oi_type = "淨空單"
        if oi_diff < 0:
            step1_msg = f"{RED}空單增加（更負） ➔ 外資偏空，壓力大。{RESET}"
            oi_change_desc = f"淨空單增加 {abs(oi_diff):,} 口"
            oi_trend = "increase"
        else:
            step1_msg = f"{GREEN}空單減少（負值縮小） ➔ 外資回補，行情有機會反彈。{RESET}"
            oi_change_desc = f"淨空單減少 {abs(oi_diff):,} 口"
            oi_trend = "decrease"
    else:
        oi_type = "淨多單"
        if oi_diff > 0:
            step1_msg = f"{RED}多單增加 ➔ 外資偏多，行情支撐強。{RESET}"
            oi_change_desc = f"淨多單增加 {abs(oi_diff):,} 口"
            oi_trend = "increase"
        else:
            step1_msg = f"{GREEN}多單減少 ➔ 外資退場，多方力道減弱。{RESET}"
            oi_change_desc = f"淨多單減少 {abs(oi_diff):,} 口"
            oi_trend = "decrease"
            
    print(f"  ● 最新一日外資{oi_type}：{latest_oi:,} 口 (前一日：{prev_oi:,} 口，{oi_change_desc})")
    print(f"  ➔ 研判結果：{step1_msg}")
    
    # Step 2：對照大盤指數走勢
    print(f"\n{BOLD}【Step 2：期權籌碼與大盤走勢對照】{RESET}")
    step2_msg = ""
    summary_sentiment = ""
    
    if aligned_prices and len(aligned_prices) >= 2:
        latest_price = aligned_prices[-1]
        prev_price = aligned_prices[-2]
        price_diff = latest_price - prev_price
        price_trend = "up" if price_diff > 0 else "down"
        
        price_change_desc = f"上漲 +{price_diff:,.2f} 點" if price_diff > 0 else f"下跌 {price_diff:,.2f} 點"
        print(f"  ● 最新大盤收盤價：{latest_price:,.2f} 點 (前一日：{prev_price:,.2f} 點，{price_change_desc})")
        print(f"  ● 外資期貨淨 OI 動向：{oi_type}{'增加' if oi_trend == 'increase' else '減少'}")
        
        if oi_trend == "increase" and price_trend == "down":
            step2_msg = f"{RED}OI 增加 + 指數下跌 ➔ 空方力量強，趨勢偏空。{RESET}"
            summary_sentiment = "大盤目前呈現「外資期貨空單增加且指數下跌」的空頭格局。空方力量強勁，趨勢偏空，短期建議保守看待。"
        elif oi_trend == "decrease" and price_trend == "up":
            step2_msg = f"{GREEN}OI 減少 + 指數上漲 ➔ 外資回補，行情偏多。{RESET}"
            summary_sentiment = "大盤目前呈現「外資期貨空單減少且指數上漲」的偏多格局。外資空單回補，行情有反彈或持續上攻的機會。"
        elif oi_trend == "increase" and price_trend == "up":
            step2_msg = f"{RED}OI 增加 + 指數上漲 ➔ 可能是避險，需觀察是否反轉。{RESET}"
            summary_sentiment = "大盤目前呈現「外資期貨空單增加但指數上漲」的避險格局。外資在指數走高時增持空單避險，需提防行情可能隨時出現反轉。"
        elif oi_trend == "decrease" and price_trend == "down":
            step2_msg = f"{GREEN}OI 減少 + 指數下跌 ➔ 外資退場，行情可能整理。{RESET}"
            summary_sentiment = "大盤目前呈現「外資期貨空單減少但指數下跌」的整理格局。外資多空部位同步退場，市場觀望氣氛較濃，行情可能陷入區間震盪整理。"
            
        print(f"  ➔ 研判結果：{step2_msg}")
    else:
        print("  ● 無法取得大盤指數價格（Yahoo Finance 價格下載失敗或日期未對齊）")
        summary_sentiment = "因無法對照歷史指數收盤價，僅能以期貨與選擇權未平倉量進行評估。"
        
    # Step 3：檢查選擇權 OI 支撐壓力
    print(f"\n{BOLD}【Step 3：選擇權 OI 支撐壓力】{RESET}")
    if opt_data:
        max_call = opt_data["MaxCallStrike"]
        max_call_oi = opt_data["MaxCallOI"]
        max_put = opt_data["MaxPutStrike"]
        max_put_oi = opt_data["MaxPutOI"]
        
        print(f"  ● 最大 Call OI 履約價：{BOLD}{max_call:,}{RESET} 點 (未平倉 {max_call_oi:,} 口) ➔ 壓力區，指數不易突破。")
        print(f"  ● 最大 Put  OI 履約價：{BOLD}{max_put:,}{RESET} 點 (未平倉 {max_put_oi:,} 口) ➔ 支撐區，指數不易跌破。")
        
        # 結算週提醒
        if is_settlement:
            print(f"  ● {RED}結算週特別注意：外資可能利用期貨空單壓低結算價。{RESET}")
    else:
        print("  ● 無法取得今日選擇權最大未平倉數據。")
        
    # 最後輸出總結
    print(f"\n{BOLD}================================================================================{RESET}")
    print(f"{BOLD}【💡 籌碼面智慧總結 (Final Summary)】{RESET}")
    
    summary_text = summary_sentiment
    if opt_data:
        summary_text += f" 目前選擇權近月合約支撐位於 {opt_data['MaxPutStrike']:,} 點，壓力位於 {opt_data['MaxCallStrike']:,} 點。"
    if is_settlement:
        summary_text += f" 由於本週為結算週 (結算日：{settlement_date})，"
        if latest_oi < -20000:
            summary_text += f" 且外資持有較多空單部位 ({latest_oi:,} 口)，主力利用期貨空單壓低結算價的風險較高，操作上建議避開過度槓桿，防範結算前後行情劇烈波動。"
        else:
            summary_text += " 主力可能在換倉或進行拉高/壓低結算，請特別注意盤勢波動風險。"
            
    print(f"  {summary_text}")
    print(f"{BOLD}================================================================================{RESET}")

def load_industry_mapping(cache_dir="colab_cache"):
    """從公開資料下載並建立上市櫃公司「股票代號 -> 產業名稱」的對照表，並快取在本地"""
    mapping_cache_path = os.path.join(cache_dir, "industry_mapping.json")
    if os.path.exists(mapping_cache_path):
        with open(mapping_cache_path, "r", encoding="utf-8") as f:
            try:
                return json.load(f)
            except Exception:
                pass
                
    print("正在下載公司產業別對照資料（此動作僅在首次執行或快取失效時進行）...")
    mapping = {}
    
    # 證交所產業代碼與中文名稱對照字典
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
    
    import io
    headers_req = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36"
    }
    # 1. 載入上市公司基本資料
    try:
        res_l = requests.get("https://mopsfin.twse.com.tw/opendata/t187ap03_L.csv", headers=headers_req, timeout=10)
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
        print(f"警告：無法讀取上市基本資料：{e}", file=sys.stderr)
        
    # 2. 載入上櫃公司基本資料
    try:
        res_o = requests.get("https://mopsfin.twse.com.tw/opendata/t187ap03_O.csv", headers=headers_req, timeout=10)
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
        print(f"警告：無法讀取上櫃基本資料：{e}", file=sys.stderr)
        
    if mapping:
        os.makedirs(cache_dir, exist_ok=True)
        with open(mapping_cache_path, "w", encoding="utf-8") as f:
            json.dump(mapping, f, ensure_ascii=False, indent=2)
            
    return mapping

def show_market_summary(date_str, cache_dir, is_today=False):
    print(f"\n{BOLD}🏛️  大盤三大法人進出統計 ({date_str[:4]}/{date_str[4:6]}/{date_str[6:]}) 🏛️{RESET}")
    
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
                
    if not summary_rows:
        print("無法取得大盤三大法人進出統計數據。")
        return
        
    formatted_table = []
    for r in summary_rows:
        def to_billion(val_str):
            try:
                val = int(str(val_str).replace(",", "").strip())
                return val / 100_000_000.0
            except ValueError:
                return 0.0
                
        net_b = to_billion(r["Net"])
        buy_b = to_billion(r["Buy"])
        sell_b = to_billion(r["Sell"])
        
        if net_b > 0:
            net_str = f"{RED}+{net_b:,.2f} 億{RESET}"
        elif net_b < 0:
            net_str = f"{GREEN}{net_b:,.2f} 億{RESET}"
        else:
            net_str = "0.00 億"
            
        formatted_table.append([
            r["Market"],
            r["Category"],
            f"{buy_b:,.2f} 億",
            f"{sell_b:,.2f} 億",
            net_str
        ])
        
    headers = ["市場", "法人機構", "買進金額", "賣出金額", "買賣超金額"]
    col_aligns = ["left", "left", "right", "right", "right"]
    print_beautiful_table(formatted_table, headers, col_aligns)

def show_streak_rankings(df_streaks, industry_mapping, min_streak_days=1, max_streak_days=None, display_limit=None):
    """顯示外資與投信的連買/連賣天數排行榜 (含產業別，依條件篩選)"""
    min_days = max(1, int(min_streak_days) if min_streak_days is not None else 1)
    max_days = int(max_streak_days) if (max_streak_days is not None and int(max_streak_days) > 0) else None
    
    # 篩選出大於等於 min_days (連買) 或小於等於 -min_days (連賣) 且符合最大值限制的資料
    if max_days is not None:
        foreign_buy = df_streaks[(df_streaks["Foreign_Streak"] >= min_days) & (df_streaks["Foreign_Streak"] <= max_days)]
        foreign_sell = df_streaks[(df_streaks["Foreign_Streak"] <= -min_days) & (df_streaks["Foreign_Streak"] >= -max_days)]
        trust_buy = df_streaks[(df_streaks["Trust_Streak"] >= min_days) & (df_streaks["Trust_Streak"] <= max_days)]
        trust_sell = df_streaks[(df_streaks["Trust_Streak"] <= -min_days) & (df_streaks["Trust_Streak"] >= -max_days)]
    else:
        foreign_buy = df_streaks[df_streaks["Foreign_Streak"] >= min_days]
        foreign_sell = df_streaks[df_streaks["Foreign_Streak"] <= -min_days]
        trust_buy = df_streaks[df_streaks["Trust_Streak"] >= min_days]
        trust_sell = df_streaks[df_streaks["Trust_Streak"] <= -min_days]

    # 排序
    foreign_buy = foreign_buy.sort_values(by=["Foreign_Streak", "Foreign_Latest"], ascending=[False, False])
    foreign_sell = foreign_sell.sort_values(by=["Foreign_Streak", "Foreign_Latest"], ascending=[True, True])
    trust_buy = trust_buy.sort_values(by=["Trust_Streak", "Trust_Latest"], ascending=[False, False])
    trust_sell = trust_sell.sort_values(by=["Trust_Streak", "Trust_Latest"], ascending=[True, True])
    
    # 限制呈現數量：如果有設定特定天數，可顯示多一點 (例如 top 50)，如果是 1，維持 top 20 以免太長
    # 限制呈現數量
    if display_limit is not None:
        limit = int(display_limit)
    else:
        limit = 50 if (min_days > 1 or max_days is not None) else 20
    
    if limit > 0:
        foreign_buy = foreign_buy.head(limit)
        foreign_sell = foreign_sell.head(limit)
        trust_buy = trust_buy.head(limit)
        trust_sell = trust_sell.head(limit)
    
    def format_streak_rows(df, streak_col, latest_col):
        rows = []
        for _, row in df.iterrows():
            streak = abs(row[streak_col])
            latest_lots = int(row[latest_col] / 1000)
            
            if latest_lots > 0:
                latest_str = f"{RED}+{latest_lots:,} 張{RESET}"
            elif latest_lots < 0:
                latest_str = f"{GREEN}{latest_lots:,} 張{RESET}"
            else:
                latest_str = "0 張"
                
            streak_str = f"{RED}連買 {streak} 天{RESET}" if row[streak_col] > 0 else f"{GREEN}連賣 {streak} 天{RESET}"
            
            # 取得產業別
            ind_name = industry_mapping.get(row["Symbol"], "其他")
            
            rows.append([
                row["Symbol"],
                row["Name"],
                ind_name,
                row["Market"],
                streak_str,
                latest_str
            ])
        return rows

    headers = ["股票代號", "股票名稱", "產業別", "市場", "連續天數", "最新一日買賣超"]
    col_aligns = ["left", "left", "left", "left", "right", "right"]
    
    if max_days is not None:
        suffix = f" ({min_days}-{max_days}天, Top {limit})"
    else:
        suffix = f" (最少 {min_days}天, Top {limit})" if min_days > 1 else f" (Top {limit})"
    
    print(f"\n{BOLD}🔥 外資連買排行榜{suffix} 🔥{RESET}")
    if not foreign_buy.empty:
        print_beautiful_table(format_streak_rows(foreign_buy, "Foreign_Streak", "Foreign_Latest"), headers, col_aligns)
    else:
        print("今日無符合之個股。")
        
    print(f"\n{BOLD}💀 外資連賣排行榜{suffix} 💀{RESET}")
    if not foreign_sell.empty:
        print_beautiful_table(format_streak_rows(foreign_sell, "Foreign_Streak", "Foreign_Latest"), headers, col_aligns)
    else:
        print("今日無符合之個股。")
        
    print(f"\n{BOLD}🔥 投信連買排行榜{suffix} 🔥{RESET}")
    if not trust_buy.empty:
        print_beautiful_table(format_streak_rows(trust_buy, "Trust_Streak", "Trust_Latest"), headers, col_aligns)
    else:
        print("今日無符合之個股。")
        
    print(f"\n{BOLD}💀 投信連賣排行榜{suffix} 💀{RESET}")
    if not trust_sell.empty:
        print_beautiful_table(format_streak_rows(trust_sell, "Trust_Streak", "Trust_Latest"), headers, col_aligns)
    else:
        print("今日無符合之個股。")

def show_individual_stock(symbol, df_streaks, industry_mapping):
    import yfinance as yf
    
    print(f"\n{BOLD}=================================================={RESET}")
    print(f"{BOLD}🔍 個股數據查詢: {symbol} 🔍{RESET}")
    print(f"{BOLD}=================================================={RESET}")
    
    # 先查詢法人明細中的市場別，以精準查詢 yfinance，避免無效查詢產生錯誤 Log
    market_suffix = None
    if not df_streaks.empty:
        match = df_streaks[df_streaks["Symbol"] == symbol]
        if not match.empty:
            market = match.iloc[0]["Market"]
            if "上市" in market:
                market_suffix = "TW"
            elif "上櫃" in market:
                market_suffix = "TWO"

    # 1. 取得個股股價 (使用 yfinance)
    hist = None
    full_symbol = None
    
    if market_suffix == "TW":
        try:
            ticker = yf.Ticker(f"{symbol}.TW")
            temp_hist = ticker.history(period="5d")
            if not temp_hist.empty:
                hist = temp_hist
                full_symbol = f"{symbol}.TW"
        except Exception:
            pass
    elif market_suffix == "TWO":
        try:
            ticker = yf.Ticker(f"{symbol}.TWO")
            temp_hist = ticker.history(period="5d")
            if not temp_hist.empty:
                hist = temp_hist
                full_symbol = f"{symbol}.TWO"
        except Exception:
            pass
    else:
        # 若在法人明細中找不到，則關閉 yfinance 內建 logger 錯誤顯示並依序嘗試
        try:
            import logging
            logging.getLogger('yfinance').setLevel(logging.CRITICAL)
        except Exception:
            pass
            
        try:
            ticker = yf.Ticker(f"{symbol}.TW")
            temp_hist = ticker.history(period="5d")
            if not temp_hist.empty:
                hist = temp_hist
                full_symbol = f"{symbol}.TW"
        except Exception:
            pass
            
        if hist is None:
            try:
                ticker = yf.Ticker(f"{symbol}.TWO")
                temp_hist = ticker.history(period="5d")
                if not temp_hist.empty:
                    hist = temp_hist
                    full_symbol = f"{symbol}.TWO"
            except Exception:
                pass
            
    if hist is not None and not hist.empty:
        latest = hist.iloc[-1]
        prev = hist.iloc[-2] if len(hist) > 1 else None
        
        close_p = latest["Close"]
        open_p = latest["Open"]
        high_p = latest["High"]
        low_p = latest["Low"]
        vol = int(latest["Volume"] / 1000)
        
        if prev is not None:
            prev_close = prev["Close"]
            change = close_p - prev_close
            change_pct = (change / prev_close) * 100
        else:
            change = 0
            change_pct = 0.0
            
        if change > 0:
            change_str = f"{RED}+{change:.2f} 元 (+{change_pct:.2f}%){RESET}"
        elif change < 0:
            change_str = f"{GREEN}{change:.2f} 元 ({change_pct:.2f}%){RESET}"
        else:
            change_str = "0.00 元 (0.00%)"
            
        print(f"市場識別: {full_symbol}")
        print(f"今日收盤: {close_p:.2f} 元 | 漲跌幅: {change_str}")
        print(f"開盤: {open_p:.2f} 元 | 最高: {high_p:.2f} 元 | 最低: {low_p:.2f} 元")
        print(f"今日成交: {vol:,} 張")
    else:
        print("無法從 Yahoo Finance 取得即時股價資料。")
        
    print(f"\n{BOLD}💼 法人籌碼動向與連買連賣天數 💼{RESET}")
    match = df_streaks[df_streaks["Symbol"] == symbol]
    
    if not match.empty:
        row = match.iloc[0]
        ind_name = industry_mapping.get(symbol, "其他")
        print(f"股票名稱: {row['Name']} ({row['Market']} | {ind_name})")
        
        def format_streak(streak_val, latest_val):
            lots = int(latest_val / 1000)
            if lots > 0:
                lots_str = f"{RED}+{lots:,} 張{RESET}"
            elif lots < 0:
                lots_str = f"{GREEN}{lots:,} 張{RESET}"
            else:
                lots_str = "0 張"
                
            if streak_val > 0:
                return f"{RED}連買 {streak_val} 天{RESET} (今日: {lots_str})"
            elif streak_val < 0:
                return f"{GREEN}連賣 {abs(streak_val)} 天{RESET} (今日: {lots_str})"
            else:
                return f"無連續趨勢 (今日: {lots_str})"
                
        print(f"1. 外資買賣超：{format_streak(row['Foreign_Streak'], row['Foreign_Latest'])}")
        print(f"2. 投信買賣超：{format_streak(row['Trust_Streak'], row['Trust_Latest'])}")
        print(f"3. 自營商買賣超：{format_streak(row['Dealer_Streak'], row['Dealer_Latest'])}")
        print(f"4. 三大法人合計：{format_streak(row['Total_Streak'], row['Total_Latest'])}")
    else:
        print("未在法人買賣明細中找到此股票。可能該股今日無法人進出，或代碼輸入錯誤。")
    print("-" * 50)

def clean_old_cache(cache_dir, keep_days=40):
    """清理超過 keep_days 天的歷史快取檔案，將快取總容量永久控制在安全範圍內"""
    if not os.path.exists(cache_dir):
        return
        
    try:
        current_time = time.time()
        limit_seconds = keep_days * 24 * 60 * 60
        cleaned_count = 0
        for filename in os.listdir(cache_dir):
            if filename == "industry_mapping.json":
                continue
            filepath = os.path.join(cache_dir, filename)
            if os.path.isfile(filepath):
                file_mtime = os.path.getmtime(filepath)
                if (current_time - file_mtime) > limit_seconds:
                    os.remove(filepath)
                    cleaned_count += 1
        if cleaned_count > 0:
            print(f"快取自動清理：已自動清除 {cleaned_count} 個超過 {keep_days} 天的舊快取檔案。")
    except Exception:
        pass

def main():
    print(f"{BOLD}=================================================={RESET}")
    print(f"{BOLD}       🚀 台灣股市法人籌碼與連買連賣查詢 🚀       {RESET}")
    print(f"=================================================={RESET}")
    
    global use_gdrive_cache
    if 'use_gdrive_cache' in globals() and use_gdrive_cache:
        try:
            from google.colab import drive
            print("正在掛載 Google Drive 以讀取/儲存快取資料...")
            drive.mount('/content/drive', force_remount=False)
            cache_dir = "/content/drive/MyDrive/stock_scraper_cache"
            print(f"快取路徑已設定為 Google Drive: {cache_dir}")
        except Exception as e:
            print(f"無法掛載 Google Drive ({e})，將使用本地暫存快取。")
            cache_dir = "colab_cache"
    else:
        cache_dir = "colab_cache"

    
    trading_days = find_latest_trading_days(n=20, cache_dir=cache_dir)
    if not trading_days:
        print("無法取得歷史交易資料，請確認網路連線。", file=sys.stderr)
        return
        
    latest_date, _ = trading_days[0]
    print(f"定位最新交易日: {latest_date[:4]}/{latest_date[4:6]}/{latest_date[6:]}")
    
    df_list = [day[1] for day in trading_days]
    df_streaks = calculate_streaks(df_list)
    
    # 載入公司產業別對照資料
    industry_mapping = load_industry_mapping(cache_dir)
    
    # 處理 Colab 的表單輸入
    symbols = [s.strip() for s in stock_codes.split() if s.strip()]
    
    if len(symbols) > 0:
        for symbol in symbols:
            show_individual_stock(symbol, df_streaks, industry_mapping)
    else:
        is_today = (latest_date == datetime.date.today().strftime("%Y%m%d"))
        show_market_summary(latest_date, cache_dir, is_today)
        
        # --- 新增期權籌碼分析 ---
        # 1. 抓取最近 10 天期貨資料並顯示趨勢表
        print(f"\n{BOLD}=== 三大法人期貨未平倉量 (OI) 歷史趨勢 (近 10 天) ==={RESET}")
        futures_history = []
        for date_str, _ in reversed(trading_days[:10]):  # 由舊到新 (用於繪圖與時間順序)
            oi_data = fetch_taifex_futures_oi(date_str, cache_dir)
            if oi_data:
                futures_history.append((date_str, oi_data))
                
        aligned_prices = []
        if futures_history:
            # 準備表格內容 (由新到舊呈現於終端機)
            futures_rows = []
            for date_str, oi in reversed(futures_history):
                f_net = oi["Foreign"]["Net"]
                t_net = oi["Trust"]["Net"]
                d_net = oi["Dealers"]["Net"]
                tot_net = f_net + t_net + d_net
                
                def fmt_oi(val):
                    if val > 0:
                        return f"{RED}+{val:,} 口{RESET}"
                    elif val < 0:
                        return f"{GREEN}{val:,} 口{RESET}"
                    else:
                        return "0 口"
                
                futures_rows.append([
                    f"{date_str[:4]}/{date_str[4:6]}/{date_str[6:]}",
                    fmt_oi(f_net),
                    fmt_oi(t_net),
                    fmt_oi(d_net),
                    fmt_oi(tot_net)
                ])
                
            headers_f = ["交易日期", "外資期貨淨OI", "投信期貨淨OI", "自營商期貨淨OI", "三大法人合計淨OI"]
            aligns_f = ["left", "right", "right", "right", "right"]
            print_beautiful_table(futures_rows, headers_f, aligns_f)
            
            # 生成走勢疊圖 (Colab 直接 plt.show()) 並取得對齊的大盤價格
            _, aligned_prices = generate_trend_chart(futures_history, cache_dir)
        else:
            print("無法取得期貨未平倉量歷史資料。")
            
        # 2. 獲取選擇權資料
        opt_data = fetch_taifex_options_max_oi(latest_date, cache_dir)
        
        # 3. 結算週判定
        is_settlement, settlement_date = check_settlement_week(latest_date)
        
        # 4. 進行大盤籌碼綜合分析與總結
        if futures_history:
            analyze_market_sentiment(futures_history, aligned_prices, opt_data, is_settlement, settlement_date)
        # --- 期權籌碼分析結束 ---
        
        show_streak_rankings(df_streaks, industry_mapping, min_streak_days, max_streak_days, display_limit)

    # 在程式結束前自動清理舊快取，避免快取檔案無限期累積佔用 Google Drive 空間
    clean_old_cache(cache_dir, keep_days=40)

if __name__ == "__main__":
    main()
