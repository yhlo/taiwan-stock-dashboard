// Renders data/scoreboard.json: what each chip signal picked, and how it did.
//
// The point of a scoreboard is that it is kept honestly, so this deliberately
// shows sample size next to every average and never hides a losing session.

const SMALL_SAMPLE_SESSIONS = 20;

function fmtDate(s) {
    if (!s || s.length !== 8) return s || '—';
    return `${s.slice(4, 6)}/${s.slice(6)}`;
}

function fmtPct(v, digits = 2) {
    if (v === null || v === undefined) return '—';
    return `${v >= 0 ? '+' : ''}${v.toFixed(digits)}%`;
}

function pctClass(v) {
    if (v === null || v === undefined) return '';
    return v >= 0 ? 'text-up' : 'text-down';
}

function renderSummary(summary) {
    const host = document.getElementById('scoreboard-summary');
    const keys = Object.keys(summary || {});
    if (!keys.length) {
        host.innerHTML = '<p class="text-center text-secondary">尚未累積足夠的結算紀錄，明日起陸續更新。</p>';
        return 0;
    }

    let minSessions = Infinity;
    host.innerHTML = keys.map(k => {
        const s = summary[k];
        minSessions = Math.min(minSessions, s.Sessions);
        return `
            <div class="score-card">
                <div class="score-card-title">${s.Label}</div>
                <div class="score-card-main ${pctClass(s.AvgReturn)}">${fmtPct(s.AvgReturn)}</div>
                <div class="score-card-sub">每日平均報酬 · 共 ${s.Sessions} 個交易日</div>
                <div class="score-card-grid">
                    <div>
                        <span class="score-k">為正場次</span>
                        <span class="score-v">${s.PositiveSessionRate}%</span>
                    </div>
                    <div>
                        <span class="score-k">最佳</span>
                        <span class="score-v text-up">${fmtPct(s.BestReturn)}</span>
                    </div>
                    <div>
                        <span class="score-k">最差</span>
                        <span class="score-v text-down">${fmtPct(s.WorstReturn)}</span>
                    </div>
                </div>
            </div>`;
    }).join('');
    return minSessions;
}

function renderCaveat(minSessions) {
    const host = document.getElementById('scoreboard-caveat');
    if (!minSessions || minSessions === Infinity) { host.innerHTML = ''; return; }

    // A handful of sessions cannot separate signal from luck. Say so plainly and
    // in proportion, rather than letting a tidy percentage imply more than it can.
    if (minSessions < SMALL_SAMPLE_SESSIONS) {
        host.innerHTML = `
            <div class="brief-alert score-caveat">
                ⚠️ <strong>樣本僅 ${minSessions} 個交易日，尚不足以判斷訊號優劣。</strong>
                短期結果極易受個別行情左右（例如單日大跌會同時拖累所有訊號），
                請當作紀錄觀察，不要當成勝率保證。統計會隨每日累積而更有參考性。
            </div>`;
    } else {
        host.innerHTML = `
            <div class="brief-alert score-caveat">
                📊 已累積 ${minSessions} 個交易日的紀錄。過去表現不代表未來結果，且未計入交易成本與滑價。
            </div>`;
    }
}

function renderEntries(entries) {
    const tbody = document.querySelector('#scoreboard-table tbody');
    if (!entries || !entries.length) {
        tbody.innerHTML = '<tr><td colspan="6" class="text-center">尚無紀錄</td></tr>';
        return;
    }

    tbody.innerHTML = entries.map(e => {
        const pending = !e.EvalDate;
        const stocks = (e.Stocks || []).map(s => {
            const ret = s.Return;
            const retHtml = (ret === undefined || ret === null)
                ? ''
                : `<span class="chip-ret ${pctClass(ret)}">${fmtPct(ret, 1)}</span>`;
            return `<span class="stock-chip" title="${s.Name}">${s.Name}${retHtml}</span>`;
        }).join('');

        const scoredNote = (!pending && e.Scored && e.Scored < (e.Stocks || []).length)
            ? `<span class="score-partial" title="部分個股無可取得的歷史股價，未計入平均">計入 ${e.Scored}/${e.Stocks.length}</span>`
            : '';

        return `
            <tr>
                <td><strong>${fmtDate(e.SignalDate)}</strong></td>
                <td>${e.Label}</td>
                <td class="text-right">${pending
                    ? `<span class="score-pending" title="訊號於 ${fmtDate(e.SignalDate)} 收盤後產生，需等次一交易日收盤才能結算，以免用當天自己的收盤價回頭評分。">待次一交易日結算</span>`
                    : fmtDate(e.EvalDate)}</td>
                <td class="text-right ${pctClass(e.AvgReturn)}">
                    ${pending ? '—' : `<strong>${fmtPct(e.AvgReturn)}</strong>`}
                </td>
                <td class="text-right">${pending ? '—' : `${e.WinRate}% ${scoredNote}`}</td>
                <td><div class="stock-chips">${stocks}</div></td>
            </tr>`;
    }).join('');
}

async function initScoreboard() {
    try {
        const res = await fetch(`./data/scoreboard.json?t=${Date.now()}`);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const board = await res.json();

        const badge = document.getElementById('scoreboard-date');
        if (badge) {
            badge.textContent = board.UpdatedFor
                ? `更新至 ${fmtDate(board.UpdatedFor)}`
                : '—';
        }

        const minSessions = renderSummary(board.Summary || {});
        renderCaveat(minSessions);
        renderEntries(board.Entries || []);

        const note = document.getElementById('scoreboard-note');
        if (note && board.Note) note.textContent = board.Note;
    } catch (e) {
        console.error('Scoreboard load failed:', e);
        document.querySelector('#scoreboard-table tbody').innerHTML =
            '<tr><td colspan="6" class="text-center">計分板資料載入失敗</td></tr>';
        document.getElementById('scoreboard-summary').innerHTML =
            '<p class="text-center text-secondary">資料載入失敗，請稍後再試。</p>';
    }
}

document.addEventListener('DOMContentLoaded', initScoreboard);
