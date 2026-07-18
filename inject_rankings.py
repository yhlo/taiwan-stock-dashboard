# -*- coding: utf-8 -*-
"""
把每日法人連買 Top 10 排行「烤」成靜態 HTML，寫入 index.html 的
<!-- STATIC_RANKINGS:START --> ... <!-- STATIC_RANKINGS:END --> 區塊。

目的：讓搜尋引擎爬蟲與未執行 JavaScript 的環境，也能直接讀到當日的
核心籌碼內容（原本排行榜是前端 JS 讀 JSON 後才渲染，爬蟲看不到）。

用法：
    python inject_rankings.py                # 讀 data/streaks.json 注入 index.html
可被 build_static_data.py 於每日爬蟲後 import 呼叫：
    from inject_rankings import inject
    inject()
"""
import html
import json
import os

START_MARKER = "<!-- STATIC_RANKINGS:START -->"
END_MARKER = "<!-- STATIC_RANKINGS:END -->"


def _fmt_lots(latest_shares):
    """買賣超股數 → 張（1 張 = 1000 股），帶正負號與千分位。"""
    lots = round((latest_shares or 0) / 1000)
    sign = "+" if lots > 0 else ""
    color = "var(--color-up)" if lots > 0 else ("var(--color-down)" if lots < 0 else "var(--text-secondary)")
    return f'<span style="color: {color}; font-weight: 600;">{sign}{lots:,} 張</span>'


def _fmt_date(date_str):
    """20260714 → 2026/07/14"""
    if date_str and len(date_str) == 8:
        return f"{date_str[0:4]}/{date_str[4:6]}/{date_str[6:8]}"
    return date_str or ""


def _rows(items, streak_key, latest_getter):
    if not items:
        return '<tr><td colspan="4" class="text-center" style="color: var(--text-secondary);">今日無符合條件的個股</td></tr>'
    out = []
    for r in items:
        sym = html.escape(str(r.get("Symbol", "")))
        name = html.escape(str(r.get("Name", "")))
        days = r.get(streak_key, 0)
        latest = latest_getter(r)
        out.append(
            f'<tr><td><strong>{sym}</strong></td><td>{name}</td>'
            f'<td class="text-right">{days} 天</td>'
            f'<td class="text-right">{_fmt_lots(latest)}</td></tr>'
        )
    return "\n".join(out)


def _table(title, rows_html):
    return (
        '<div class="table-container">'
        f'<h3 class="table-subtitle">{title}</h3>'
        '<table><thead><tr>'
        '<th>代號</th><th>名稱</th>'
        '<th class="text-right">連續天數</th>'
        '<th class="text-right">最新買賣超</th>'
        '</tr></thead><tbody>'
        f'{rows_html}'
        '</tbody></table></div>'
    )


def build_html(streaks):
    data = streaks.get("Data", [])
    date_disp = _fmt_date(streaks.get("Date", ""))

    foreign = sorted(
        [r for r in data if r.get("Foreign_Streak", 0) >= 1],
        key=lambda r: (-r.get("Foreign_Streak", 0), -r.get("Foreign_Latest", 0)),
    )[:10]

    trust = sorted(
        [r for r in data if r.get("Trust_Streak", 0) >= 1],
        key=lambda r: (-r.get("Trust_Streak", 0), -r.get("Trust_Latest", 0)),
    )[:10]

    dual = sorted(
        [r for r in data if r.get("Dual_Buy_Streak", 0) >= 1],
        key=lambda r: (-r.get("Dual_Buy_Streak", 0),
                       -(r.get("Foreign_Latest", 0) + r.get("Trust_Latest", 0))),
    )[:10]

    intro = (
        f'<p style="margin-bottom: 14px; color: var(--text-secondary); font-size: 13px;">'
        f'📅 資料日期：<strong>{date_disp}</strong>（每個交易日盤後自動更新）'
        f'　以下為外資、投信連續買超天數與外資投信「雙買」共識股的當日前十名，'
        f'完整排行與篩選請見下方<a href="#streaks-ranking">🏆 三大法人連買連賣天數排行榜</a>。</p>'
    )

    grid = (
        '<div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 16px;">'
        + _table("🌊 外資連買 Top 10", _rows(foreign, "Foreign_Streak", lambda r: r.get("Foreign_Latest", 0)))
        + _table("🚀 投信連買 Top 10", _rows(trust, "Trust_Streak", lambda r: r.get("Trust_Latest", 0)))
        + _table("🔥 雙買共識 Top 10", _rows(dual, "Dual_Buy_Streak",
                 lambda r: r.get("Foreign_Latest", 0) + r.get("Trust_Latest", 0)))
        + '</div>'
    )
    return intro + grid


def inject(streaks_path="data/streaks.json", index_path="index.html"):
    if not os.path.exists(streaks_path):
        print(f"[inject_rankings] 找不到 {streaks_path}，略過注入。")
        return False
    with open(streaks_path, encoding="utf-8") as f:
        streaks = json.load(f)
    with open(index_path, encoding="utf-8") as f:
        page = f.read()

    if START_MARKER not in page or END_MARKER not in page:
        print("[inject_rankings] index.html 找不到 STATIC_RANKINGS 標記，略過注入。")
        return False

    before, rest = page.split(START_MARKER, 1)
    _, after = rest.split(END_MARKER, 1)
    new_page = before + START_MARKER + "\n" + build_html(streaks) + "\n            " + END_MARKER + after

    if new_page != page:
        with open(index_path, "w", encoding="utf-8", newline="\n") as f:
            f.write(new_page)
        print("[inject_rankings] 已將今日焦點 Top 10 注入 index.html")
    else:
        print("[inject_rankings] 內容無變化，未寫入。")
    return True


if __name__ == "__main__":
    inject()
