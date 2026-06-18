// Global State Variables
let streaksData = null;
let marketSummary = null;
let futuresOptions = null;
let currentPage = {
    'foreign-buy': 1,
    'foreign-sell': 1,
    'trust-buy': 1,
    'trust-sell': 1
};
let isDockedRight = localStorage.getItem('detail-docked') === 'true';
let activeFuturesType = 'tx';

// DOM Elements
const themeToggleBtn = document.getElementById('theme-toggle');
const stockSearchInput = document.getElementById('stock-search');
const closeSearchBtn = document.getElementById('close-search-btn');
const stockDetailSection = document.getElementById('stock-detail-section');

// Format helpers
function formatNumber(num) {
    if (num === undefined || num === null) return '--';
    return Number(num).toLocaleString('zh-TW');
}

function formatAmount(lots) {
    if (lots === undefined || lots === null) return '--';
    const numLots = Math.round(lots / 1000);
    if (numLots > 0) {
        return `<span class="badge-up">+${numLots.toLocaleString('zh-TW')} 張</span>`;
    } else if (numLots < 0) {
        return `<span class="badge-down">${numLots.toLocaleString('zh-TW')} 張</span>`;
    } else {
        return '0 張';
    }
}

function formatStreakText(streakVal, latestVal) {
    if (streakVal === undefined || streakVal === null) return '--';
    const lots = Math.round(latestVal / 1000);
    let lotsHtml = '';
    if (lots > 0) {
        lotsHtml = `<span class="badge-up">+${lots.toLocaleString('zh-TW')} 張</span>`;
    } else if (lots < 0) {
        lotsHtml = `<span class="badge-down">${lots.toLocaleString('zh-TW')} 張</span>`;
    } else {
        lotsHtml = '0 張';
    }

    if (streakVal > 0) {
        return `<span style="color: var(--color-up); font-weight: 600;">連買 ${streakVal} 天</span> (今日: ${lotsHtml})`;
    } else if (streakVal < 0) {
        return `<span style="color: var(--color-down); font-weight: 600;">連賣 ${Math.abs(streakVal)} 天</span> (今日: ${lotsHtml})`;
    } else {
        return `無連續趨勢 (今日: ${lotsHtml})`;
    }
}

function formatBillion(valStr) {
    if (valStr === undefined || valStr === null) return '--';
    try {
        const val = parseInt(String(valStr).replace(/,/g, '').trim());
        const billion = val / 100000000.0;
        if (billion > 0) {
            return `<span class="badge-up">+${billion.toFixed(2)} 億</span>`;
        } else if (billion < 0) {
            return `<span class="badge-down">${billion.toFixed(2)} 億</span>`;
        } else {
            return '0.00 億';
        }
    } catch (e) {
        return '--';
    }
}

function formatBillionValue(valStr) {
    if (valStr === undefined || valStr === null) return '--';
    try {
        const val = parseInt(String(valStr).replace(/,/g, '').trim());
        const billion = val / 100000000.0;
        return `${billion.toFixed(2)} 億`;
    } catch (e) {
        return '--';
    }
}

// Fetch all dataset
async function initApp() {
    setupTheme();
    setupEventListeners();
    
    try {
        console.log("Loading static dataset...");
        const cacheBuster = `?t=${new Date().getTime()}`;
        
        // 1. Fetch market summary
        const summaryRes = await fetch(`./data/market_summary.json${cacheBuster}`);
        marketSummary = await summaryRes.json();
        renderMarketSummary();
        
        // 2. Fetch futures & options
        const futOptRes = await fetch(`./data/futures_options.json${cacheBuster}`);
        futuresOptions = await futOptRes.json();
        renderFuturesOptions();
        
        // 3. Fetch streaks list
        const streaksRes = await fetch(`./data/streaks.json${cacheBuster}`);
        streaksData = await streaksRes.json();
        renderRankings();
        
    } catch (error) {
        console.error("Error initializing dashboard data:", error);
    }
}

// Setup theme switcher
function setupTheme() {
    const savedTheme = localStorage.getItem('theme');
    const systemPrefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
    
    if (savedTheme === 'dark' || (!savedTheme && systemPrefersDark)) {
        document.documentElement.setAttribute('data-theme', 'dark');
    } else {
        document.documentElement.setAttribute('data-theme', 'light');
    }
}

themeToggleBtn.addEventListener('click', () => {
    const currentTheme = document.documentElement.getAttribute('data-theme');
    const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
    document.documentElement.setAttribute('data-theme', newTheme);
    localStorage.setItem('theme', newTheme);
});

// Event Listeners
function setupEventListeners() {
    // Tab switching
    const tabBtns = document.querySelectorAll('.tab-btn');
    tabBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            tabBtns.forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            
            const tabId = btn.getAttribute('data-tab');
            const contents = document.querySelectorAll('.tab-content');
            contents.forEach(c => c.classList.remove('active'));
            document.getElementById(`tab-${tabId}`).classList.add('active');
        });
    });

    // Futures type tabs switching
    const futuresTabBtns = document.querySelectorAll('.futures-tab-btn');
    futuresTabBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            futuresTabBtns.forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            activeFuturesType = btn.getAttribute('data-futures-type');
            renderFuturesHistoryTable();
        });
    });

    let activeSuggestionIndex = -1;

    function selectStock(match) {
        stockSearchInput.value = `${match.Symbol} ${match.Name}`;
        showStockDetails(match);
        const suggestionsContainer = document.getElementById('search-suggestions');
        if (suggestionsContainer) {
            suggestionsContainer.innerHTML = '';
            suggestionsContainer.classList.add('hidden');
        }
        activeSuggestionIndex = -1;
    }

    // Stock search input suggestions autocomplete
    stockSearchInput.addEventListener('input', () => {
        const query = stockSearchInput.value.trim().toLowerCase();
        const suggestionsContainer = document.getElementById('search-suggestions');
        
        if (!query) {
            if (suggestionsContainer) {
                suggestionsContainer.innerHTML = '';
                suggestionsContainer.classList.add('hidden');
            }
            activeSuggestionIndex = -1;
            return;
        }
        if (streaksData && streaksData.Data) {
            // Match if symbol contains query or name contains query
            const matches = streaksData.Data.filter(item => 
                item.Symbol.toLowerCase().includes(query) || 
                item.Name.toLowerCase().includes(query)
            );
            
            // Prioritize:
            // 1. Symbol starts with query
            // 2. Name starts with query
            // 3. Keep original sorting order (by streak days)
            matches.sort((a, b) => {
                const aSym = a.Symbol.toLowerCase();
                const bSym = b.Symbol.toLowerCase();
                const aName = a.Name.toLowerCase();
                const bName = b.Name.toLowerCase();
                
                const aSymStart = aSym.startsWith(query);
                const bSymStart = bSym.startsWith(query);
                if (aSymStart && !bSymStart) return -1;
                if (!aSymStart && bSymStart) return 1;
                
                const aNameStart = aName.startsWith(query);
                const bNameStart = bName.startsWith(query);
                if (aNameStart && !bNameStart) return -1;
                if (!aNameStart && bNameStart) return 1;
                
                return 0;
            });

            const slicedMatches = matches.slice(0, 10);
            
            if (suggestionsContainer) {
                if (slicedMatches.length > 0) {
                    suggestionsContainer.innerHTML = slicedMatches.map((item, index) => `
                        <div class="suggestion-item" data-symbol="${item.Symbol}">
                            <span class="suggestion-symbol">${item.Symbol}</span>
                            <span class="suggestion-name">${item.Name}</span>
                            <span class="suggestion-market">${item.Market}</span>
                        </div>
                    `).join('');
                    suggestionsContainer.classList.remove('hidden');
                    
                    // Click listener for suggestion items
                    const items = suggestionsContainer.querySelectorAll('.suggestion-item');
                    items.forEach(el => {
                        el.addEventListener('click', () => {
                            const symbol = el.getAttribute('data-symbol');
                            const match = streaksData.Data.find(s => s.Symbol === symbol);
                            if (match) {
                                selectStock(match);
                            }
                        });
                    });
                } else {
                    suggestionsContainer.innerHTML = '';
                    suggestionsContainer.classList.add('hidden');
                }
            }
            activeSuggestionIndex = -1;
        }
    });

    // Close suggestions dropdown when clicking outside
    document.addEventListener('click', (e) => {
        const suggestionsContainer = document.getElementById('search-suggestions');
        if (suggestionsContainer && !e.target.closest('.search-box')) {
            suggestionsContainer.classList.add('hidden');
        }
    });

    // Keyboard navigation in search suggestions
    stockSearchInput.addEventListener('keydown', (e) => {
        const suggestionsContainer = document.getElementById('search-suggestions');
        if (!suggestionsContainer || suggestionsContainer.classList.contains('hidden')) {
            return;
        }
        
        const items = suggestionsContainer.querySelectorAll('.suggestion-item');
        if (items.length === 0) return;
        
        if (e.key === 'ArrowDown') {
            e.preventDefault();
            activeSuggestionIndex = (activeSuggestionIndex + 1) % items.length;
            highlightSuggestion(items);
        } else if (e.key === 'ArrowUp') {
            e.preventDefault();
            activeSuggestionIndex = (activeSuggestionIndex - 1 + items.length) % items.length;
            highlightSuggestion(items);
        } else if (e.key === 'Enter') {
            e.preventDefault();
            if (activeSuggestionIndex >= 0 && activeSuggestionIndex < items.length) {
                const symbol = items[activeSuggestionIndex].getAttribute('data-symbol');
                const match = streaksData.Data.find(s => s.Symbol === symbol);
                if (match) {
                    selectStock(match);
                }
            } else {
                // Try exact match on current input
                const query = stockSearchInput.value.trim().toLowerCase();
                const match = streaksData.Data.find(item => 
                    item.Symbol.toLowerCase() === query || 
                    item.Name.toLowerCase() === query
                );
                if (match) {
                    selectStock(match);
                }
            }
        } else if (e.key === 'Escape') {
            suggestionsContainer.classList.add('hidden');
            stockSearchInput.blur();
        }
    });

    function highlightSuggestion(items) {
        items.forEach((item, index) => {
            if (index === activeSuggestionIndex) {
                item.classList.add('active-suggestion');
                item.scrollIntoView({ block: 'nearest' });
            } else {
                item.classList.remove('active-suggestion');
            }
        });
    }

    closeSearchBtn.addEventListener('click', () => {
        stockSearchInput.value = '';
        hideStockDetails();
        const suggestionsContainer = document.getElementById('search-suggestions');
        if (suggestionsContainer) {
            suggestionsContainer.innerHTML = '';
            suggestionsContainer.classList.add('hidden');
        }
    });

    // Streak days filter range inputs with confirmation button
    const minDaysInput = document.getElementById('streak-min-input');
    const maxDaysInput = document.getElementById('streak-max-input');
    const applyStreakBtn = document.getElementById('apply-streak-btn');
    const pageSizeSelect = document.getElementById('streak-page-size-select');
    
    if (applyStreakBtn && minDaysInput && maxDaysInput) {
        const handleConfirm = () => {
            let minVal = parseInt(minDaysInput.value);
            if (isNaN(minVal) || minVal < 1) {
                minDaysInput.value = 1;
            }
            let maxVal = parseInt(maxDaysInput.value);
            if (!isNaN(maxVal) && maxVal < minVal) {
                maxDaysInput.value = minVal;
            }
            // Reset to page 1 when filter changes
            Object.keys(currentPage).forEach(k => currentPage[k] = 1);
            renderRankings();
        };
        
        applyStreakBtn.addEventListener('click', handleConfirm);
        
        [minDaysInput, maxDaysInput].forEach(inputEl => {
            inputEl.addEventListener('keydown', (e) => {
                if (e.key === 'Enter') {
                    handleConfirm();
                }
            });
            inputEl.addEventListener('blur', () => {
                let minVal = parseInt(minDaysInput.value);
                if (isNaN(minVal) || minVal < 1) {
                    minDaysInput.value = 1;
                }
                let maxVal = parseInt(maxDaysInput.value);
                if (!isNaN(maxVal) && maxVal < minVal) {
                    maxDaysInput.value = minVal;
                }
                // Reset to page 1 when filter changes
                Object.keys(currentPage).forEach(k => currentPage[k] = 1);
                renderRankings();
            });
        });
    }

    if (pageSizeSelect) {
        pageSizeSelect.addEventListener('change', () => {
            // Reset to page 1 when page size changes
            Object.keys(currentPage).forEach(k => currentPage[k] = 1);
            renderRankings();
        });
    }

    // Pagination buttons click events
    const tabIds = ['foreign-buy', 'foreign-sell', 'trust-buy', 'trust-sell'];
    tabIds.forEach(tabId => {
        const container = document.getElementById(`pagination-${tabId}`);
        if (container) {
            const prevBtn = container.querySelector('.prev-btn');
            const nextBtn = container.querySelector('.next-btn');
            
            if (prevBtn) {
                prevBtn.addEventListener('click', () => {
                    if (currentPage[tabId] > 1) {
                        currentPage[tabId]--;
                        renderRankings();
                    }
                });
            }
            
            if (nextBtn) {
                nextBtn.addEventListener('click', () => {
                    currentPage[tabId]++;
                    renderRankings();
                });
            }
        }
    });

    // Modal backdrop click to close
    const modalBackdrop = document.getElementById('modal-backdrop');
    if (modalBackdrop) {
        modalBackdrop.addEventListener('click', () => {
            hideStockDetails();
        });
    }

    // Escape key press to close
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') {
            hideStockDetails();
        }
    });

    // Dock toggle button event listener
    const dockToggleBtn = document.getElementById('dock-toggle-btn');
    if (dockToggleBtn) {
        dockToggleBtn.addEventListener('click', () => {
            isDockedRight = !isDockedRight;
            localStorage.setItem('detail-docked', isDockedRight);
            updateDetailLayout();
        });
    }
}

// Render TWSE / TPEx summary tables side-by-side
function renderMarketSummary() {
    const twseBody = document.querySelector('#market-summary-twse-table tbody');
    const tpexBody = document.querySelector('#market-summary-tpex-table tbody');
    const dateLabel = document.getElementById('market-summary-date');
    
    if (!marketSummary || !marketSummary.Data) {
        if (twseBody) twseBody.innerHTML = '<tr><td colspan="4" class="text-center">查無上市大盤統計資料</td></tr>';
        if (tpexBody) tpexBody.innerHTML = '<tr><td colspan="4" class="text-center">查無上櫃大盤統計資料</td></tr>';
        return;
    }
    
    // Set date
    const d = marketSummary.Date;
    dateLabel.textContent = `更新日期: ${d.slice(0,4)}/${d.slice(4,6)}/${d.slice(6)}`;
    
    // Helper to shorten institutional categories to prevent table wrapping
    function shortenCategoryName(name) {
        if (!name) return '';
        return name
            .replace('外資及陸資(不含外資自營商)', '外資 (不含自營)')
            .replace('外資及陸資(不含自營商)', '外資 (不含自營)')
            .replace('外資及陸資合計', '外資合計')
            .replace('自營商(自行買賣)', '自營 (自行買賣)')
            .replace('自營商(避險)', '自營 (避險)')
            .replace('自營商合計', '自營合計')
            .replace('三大法人合計*', '三大法人合計')
            .replace('外資自營商', '外資自營');
    }

    let twseHtml = '';
    let tpexHtml = '';
    
    marketSummary.Data.forEach(row => {
        const shortenedName = shortenCategoryName(row.Category);
        const rowHtml = `
            <tr>
                <td><strong>${shortenedName}</strong></td>
                <td class="text-right">${formatBillionValue(row.Buy)}</td>
                <td class="text-right">${formatBillionValue(row.Sell)}</td>
                <td class="text-right">${formatBillion(row.Net)}</td>
            </tr>
        `;
        if (row.Market.includes("上市")) {
            twseHtml += rowHtml;
        } else if (row.Market.includes("上櫃")) {
            tpexHtml += rowHtml;
        }
    });
    
    if (twseBody) twseBody.innerHTML = twseHtml || '<tr><td colspan="4" class="text-center">無上市資料</td></tr>';
    if (tpexBody) tpexBody.innerHTML = tpexHtml || '<tr><td colspan="4" class="text-center">無上櫃資料</td></tr>';
}

// Render Futures History Table dynamically based on type (tx, mtx, tmf)
function renderFuturesHistoryTable() {
    const tableBody = document.querySelector('#futures-oi-table tbody');
    if (!tableBody) return;
    if (!futuresOptions || !futuresOptions.FuturesHistory) {
        tableBody.innerHTML = '<tr><td colspan="5" class="text-center">無期貨歷史資料</td></tr>';
        return;
    }
    
    let html = '';
    const history = (futuresOptions.FuturesHistory || []).slice(0, 5);
    history.forEach(row => {
        const d = row.Date;
        const formattedDate = `${d.slice(0,4)}/${d.slice(4,6)}/${d.slice(6)}`;
        
        let foreignNet = null, trustNet = null, dealerNet = null, totalNet = null;
        if (activeFuturesType === 'mtx') {
            foreignNet = row.MTX_Foreign_Net;
            trustNet = row.MTX_Trust_Net;
            dealerNet = row.MTX_Dealer_Net;
            totalNet = row.MTX_Total_Net;
        } else if (activeFuturesType === 'tmf') {
            foreignNet = row.TMF_Foreign_Net;
            trustNet = row.TMF_Trust_Net;
            dealerNet = row.TMF_Dealer_Net;
            totalNet = row.TMF_Total_Net;
        } else {
            foreignNet = row.Foreign_Net;
            trustNet = row.Trust_Net;
            dealerNet = row.Dealer_Net;
            totalNet = row.Total_Net;
        }
        
        function formatOI(val) {
            if (val === undefined || val === null) return '--';
            if (val > 0) return `<span class="badge-up">+${val.toLocaleString()}</span>`;
            if (val < 0) return `<span class="badge-down">${val.toLocaleString()}</span>`;
            return '0';
        }
        
        html += `
            <tr>
                <td>${formattedDate}</td>
                <td class="text-right">${formatOI(foreignNet)}</td>
                <td class="text-right">${formatOI(trustNet)}</td>
                <td class="text-right">${formatOI(dealerNet)}</td>
                <td class="text-right">${formatOI(totalNet)}</td>
            </tr>
        `;
    });
    tableBody.innerHTML = html || '<tr><td colspan="5" class="text-center">無期貨歷史資料</td></tr>';
}

// Render Futures & Options
function renderFuturesOptions() {
    const chartImg = document.getElementById('futures-trend-chart');
    const fallbackTxt = document.getElementById('chart-fallback');
    
    if (!futuresOptions) {
        const tableBody = document.querySelector('#futures-oi-table tbody');
        if (tableBody) tableBody.innerHTML = '<tr><td colspan="5" class="text-center">查無期貨未平倉資料</td></tr>';
        return;
    }
    
    // Set Chart Image src
    chartImg.src = `./data/futures_trend.png?t=${new Date().getTime()}`; // Prevent browser cache
    chartImg.onerror = () => {
        chartImg.classList.add('hidden');
        fallbackTxt.classList.remove('hidden');
    };
    
    // Render Futures History table
    renderFuturesHistoryTable();
    
    // Options
    const opt = futuresOptions.Options;
    if (opt) {
        document.getElementById('options-max-call-strike').textContent = `${formatNumber(opt.MaxCallStrike)} 點`;
        document.getElementById('options-max-call-oi').textContent = `未平倉量: ${formatNumber(opt.MaxCallOI)} 口`;
        document.getElementById('options-max-put-strike').textContent = `${formatNumber(opt.MaxPutStrike)} 點`;
        document.getElementById('options-max-put-oi').textContent = `未平倉量: ${formatNumber(opt.MaxPutOI)} 口`;
    }
    
    // Settlement week banner
    const settle = futuresOptions.Settlement;
    const banner = document.getElementById('settlement-alert-banner');
    const alertIcon = document.getElementById('settlement-alert-icon');
    const alertText = document.getElementById('settlement-alert-text');
    
    if (settle && settle.IsSettlementWeek) {
        banner.className = "settlement-banner alert";
        alertIcon.textContent = "⚠️";
        alertText.textContent = `本週為台指期權結算週！(結算日：${settle.SettlementDate})，主力可能藉期貨壓低或拉高結算。`;
    } else {
        banner.className = "settlement-banner neutral";
        alertIcon.textContent = "ℹ️";
        alertText.textContent = "本週非期權結算週，大盤走勢回歸常態技術籌碼面。";
    }
    
    // Generate dynamic Smart Sentiment Analysis text
    generateSentimentAnalysis();
}

// Smart Market Sentiment Analysis Logic in JavaScript
function generateSentimentAnalysis() {
    const contentBox = document.getElementById('market-analysis-text');
    if (!futuresOptions || !futuresOptions.FuturesHistory || futuresOptions.FuturesHistory.length < 2) {
        contentBox.textContent = "歷史資料不足，無法進行籌碼面綜合智慧分析。";
        return;
    }
    
    const history = futuresOptions.FuturesHistory;
    const latest = history[0]; // Newest is at index 0 (or last, let's check order. In JSON we reversed it, so newest is at the end? Or we wrote reversed?
    // Let's verify: In JSON output: FuturesHistory is written as reversed(futures_history).
    // Reversed futures_history means newest first! Let's double check.
    // In build_static_data.py: for d, oi in reversed(futures_history) -> newest is indeed at the end in futures_history, so reversed makes newest first!
    // Yes! latest = history[0] is correct.
    const prev = history[1];
    
    const latestOI = latest.Foreign_Net;
    const prevOI = prev.Foreign_Net;
    const oiDiff = latestOI - prevOI;
    const oiType = latestOI < 0 ? "淨空單" : "淨多單";
    
    let step1 = "";
    let oiTrend = "";
    if (latestOI < 0) {
        if (oiDiff < 0) {
            step1 = `<span style="color: var(--color-up); font-weight: bold;">空單增加（更負） => 外資偏空，壓力大。</span>`;
            oiTrend = "increase";
        } else {
            step1 = `<span style="color: var(--color-down); font-weight: bold;">空單減少（負值縮小） => 外資回補，行情有機會反彈。</span>`;
            oiTrend = "decrease";
        }
    } else {
        if (oiDiff > 0) {
            step1 = `<span style="color: var(--color-up); font-weight: bold;">多單增加 => 外資偏多，行情支撐強。</span>`;
            oiTrend = "increase";
        } else {
            step1 = `<span style="color: var(--color-down); font-weight: bold;">多單減少 => 外資退場，多方力道減弱。</span>`;
            oiTrend = "decrease";
        }
    }
    
    // Step 2
    let step2 = "";
    let summarySentiment = "";
    const prices = futuresOptions.AlignedPrices || [];
    if (prices.length >= 2) {
        const latestPrice = prices[prices.length - 1];
        const prevPrice = prices[prices.length - 2];
        const priceDiff = latestPrice - prevPrice;
        const priceTrend = priceDiff > 0 ? "up" : "down";
        
        if (oiTrend === "increase" && priceTrend === "down") {
            step2 = `<span style="color: var(--color-up); font-weight: bold;">OI 增加 + 指數下跌 => 空方力量強，趨勢偏空。</span>`;
            summarySentiment = "大盤目前呈現「外資期貨空單增加且指數下跌」的空頭格局。空方力量強勁，趨勢偏空，短期建議保守看待。";
        } else if (oiTrend === "decrease" && priceTrend === "up") {
            step2 = `<span style="color: var(--color-down); font-weight: bold;">OI 減少 + 指數上漲 => 外資回補，行情偏多。</span>`;
            summarySentiment = "大盤目前呈現「外資期貨空單減少且指數上漲」的偏多格局。外資空單回補，行情有反彈或持續上攻的機會。";
        } else if (oiTrend === "increase" && priceTrend === "up") {
            step2 = `<span style="color: var(--color-up); font-weight: bold;">OI 增加 + 指數上漲 => 可能是避險，需觀察是否反轉。</span>`;
            summarySentiment = "大盤目前呈現「外資期貨空單增加但指數上漲」的避險格局。外資在指數走高時增持空單避險，需提防行情可能隨時出現反轉。";
        } else if (oiTrend === "decrease" && priceTrend === "down") {
            step2 = `<span style="color: var(--color-down); font-weight: bold;">OI 減少 + 指數下跌 => 外資退場，行情可能整理。</span>`;
            summarySentiment = "大盤目前呈現「外資期貨空單減少但指數下跌」的整理格局。外資多空部位同步退場，市場觀望氣氛較濃，行情可能陷入區間震盪整理。";
        }
    } else {
        step2 = "無大盤指數漲跌對照。";
        summarySentiment = "僅能以期貨與選擇權未平倉部位評估。";
    }
    
    // Step 3
    const opt = futuresOptions.Options;
    let step3 = "";
    let finalSummary = summarySentiment;
    
    if (opt) {
        step3 = `目前選擇權近月合約支撐位於 <strong>${opt.MaxPutStrike.toLocaleString()}</strong> 點，壓力位於 <strong>${opt.MaxCallStrike.toLocaleString()}</strong> 點。`;
        finalSummary += ` 目前選擇權近月合約支撐位於 ${opt.MaxPutStrike.toLocaleString()} 點，壓力位於 ${opt.MaxCallStrike.toLocaleString()} 點。`;
    }
    
    const settle = futuresOptions.Settlement;
    if (settle && settle.IsSettlementWeek) {
        if (latestOI < -20000) {
            finalSummary += ` 由於本週為結算週 (結算日：${settle.SettlementDate})，且外資持有較多空單部位 (${latestOI.toLocaleString()} 口)，主力利用期貨空單壓低結算價的風險較高，操作上建議防範結算前後行情劇烈波動。`;
        } else {
            finalSummary += ` 由於本週為結算週 (結算日：${settle.SettlementDate})，主力可能在進行換倉或拉高壓低結算，操作上請特別注意風險。`;
        }
    }
    
    let html = `
        <div style="margin-bottom: 8px;"><strong>【Step 1：外資期貨淨未平倉動態】</strong></div>
        <div style="padding-left: 12px; margin-bottom: 12px; border-left: 2px solid var(--border-color);">
            最新一日外資${oiType}：<strong>${latestOI.toLocaleString()} 口</strong> (前一日：${prevOI.toLocaleString()} 口，淨空單變動 ${oiDiff.toLocaleString()} 口)<br>
            研判結果：${step1}
        </div>
        <div style="margin-bottom: 8px;"><strong>【Step 2：期權籌碼與大盤走勢對照】</strong></div>
        <div style="padding-left: 12px; margin-bottom: 12px; border-left: 2px solid var(--border-color);">
            研判結果：${step2}
        </div>
        <div style="margin-bottom: 8px;"><strong>【Step 3：選擇權 OI 支撐壓力】</strong></div>
        <div style="padding-left: 12px; margin-bottom: 16px; border-left: 2px solid var(--border-color);">
            ${step3}
        </div>
        <div style="border-top: 1px dashed var(--border-color); padding-top: 12px; font-weight: 500;">
            📝 <strong>智慧總結 (Final Summary)：</strong><br>
            <span style="color: var(--text-secondary); line-height: 1.5; display: inline-block; margin-top: 4px;">${finalSummary}</span>
        </div>
    `;
    
    contentBox.innerHTML = html;
}

// Render Rankings tables (filtered by range & with pagination)
function renderRankings() {
    if (!streaksData || !streaksData.Data) return;
    
    const minDaysInput = document.getElementById('streak-min-input');
    const maxDaysInput = document.getElementById('streak-max-input');
    const pageSizeSelect = document.getElementById('streak-page-size-select');
    
    const minDays = minDaysInput ? Math.max(1, parseInt(minDaysInput.value) || 1) : 1;
    const maxDays = (maxDaysInput && maxDaysInput.value.trim() !== '') ? parseInt(maxDaysInput.value) : NaN;
    
    let rowsPerPage = 50;
    if (pageSizeSelect) {
        const selVal = pageSizeSelect.value;
        if (selVal === 'all') {
            rowsPerPage = Infinity;
        } else {
            rowsPerPage = parseInt(selVal) || 50;
        }
    }
    
    const data = streaksData.Data;
    
    // 1. Foreign Buy
    const fBuyAll = data.filter(r => r.Foreign_Streak >= minDays && (isNaN(maxDays) || r.Foreign_Streak <= maxDays))
                        .sort((a, b) => b.Foreign_Streak - a.Foreign_Streak || b.Foreign_Latest - a.Foreign_Latest);
                        
    // 2. Foreign Sell
    const fSellAll = data.filter(r => r.Foreign_Streak <= -minDays && (isNaN(maxDays) || r.Foreign_Streak >= -maxDays))
                         .sort((a, b) => a.Foreign_Streak - b.Foreign_Streak || a.Foreign_Latest - b.Foreign_Latest);
                         
    // 3. Trust Buy
    const tBuyAll = data.filter(r => r.Trust_Streak >= minDays && (isNaN(maxDays) || r.Trust_Streak <= maxDays))
                        .sort((a, b) => b.Trust_Streak - a.Trust_Streak || b.Trust_Latest - a.Trust_Latest);
                        
    // 4. Trust Sell
    const tSellAll = data.filter(r => r.Trust_Streak <= -minDays && (isNaN(maxDays) || r.Trust_Streak >= -maxDays))
                         .sort((a, b) => a.Trust_Streak - b.Trust_Streak || a.Trust_Latest - b.Trust_Latest);
                         
    // Render each table with pagination
    renderTableWithPagination('foreign-buy', 'table-foreign-buy', fBuyAll, 'Foreign_Streak', 'Foreign_Latest', rowsPerPage);
    renderTableWithPagination('foreign-sell', 'table-foreign-sell', fSellAll, 'Foreign_Streak', 'Foreign_Latest', rowsPerPage);
    renderTableWithPagination('trust-buy', 'table-trust-buy', tBuyAll, 'Trust_Streak', 'Trust_Latest', rowsPerPage);
    renderTableWithPagination('trust-sell', 'table-trust-sell', tSellAll, 'Trust_Streak', 'Trust_Latest', rowsPerPage);
    
    // Update tab headers to display total matching count dynamically
    updateTabCounts(fBuyAll.length, fSellAll.length, tBuyAll.length, tSellAll.length);
}

function renderTableWithPagination(tabId, tableId, sortedList, streakCol, latestCol, rowsPerPage) {
    const totalItems = sortedList.length;
    let totalPages = 1;
    if (rowsPerPage !== Infinity && totalItems > 0) {
        totalPages = Math.ceil(totalItems / rowsPerPage);
    }
    
    // Ensure currentPage is within valid bounds
    if (!currentPage[tabId]) currentPage[tabId] = 1;
    if (currentPage[tabId] > totalPages) {
        currentPage[tabId] = totalPages;
    }
    if (currentPage[tabId] < 1) {
        currentPage[tabId] = 1;
    }
    
    const currPageNum = currentPage[tabId];
    
    // Slice data
    let paginatedList = sortedList;
    if (rowsPerPage !== Infinity) {
        const start = (currPageNum - 1) * rowsPerPage;
        const end = start + rowsPerPage;
        paginatedList = sortedList.slice(start, end);
    }
    
    // Populate Table
    populateRankingTable(tableId, paginatedList, streakCol, latestCol);
    
    // Update Pagination UI
    const paginationContainer = document.getElementById(`pagination-${tabId}`);
    if (paginationContainer) {
        if (totalItems === 0 || rowsPerPage === Infinity || totalPages <= 1) {
            paginationContainer.classList.add('hidden');
        } else {
            paginationContainer.classList.remove('hidden');
            
            const prevBtn = paginationContainer.querySelector('.prev-btn');
            const nextBtn = paginationContainer.querySelector('.next-btn');
            const pageInfo = paginationContainer.querySelector('.page-info');
            
            if (pageInfo) {
                pageInfo.textContent = `第 ${currPageNum} / ${totalPages} 頁 (共 ${totalItems} 筆)`;
            }
            
            if (prevBtn) {
                prevBtn.disabled = (currPageNum === 1);
            }
            
            if (nextBtn) {
                nextBtn.disabled = (currPageNum === totalPages);
            }
        }
    }
}

function updateTabCounts(fBuyCount, fSellCount, tBuyCount, tSellCount) {
    const fBuyBtn = document.querySelector('.tab-btn[data-tab="foreign-buy"]');
    const fSellBtn = document.querySelector('.tab-btn[data-tab="foreign-sell"]');
    const tBuyBtn = document.querySelector('.tab-btn[data-tab="trust-buy"]');
    const tSellBtn = document.querySelector('.tab-btn[data-tab="trust-sell"]');
    
    if (fBuyBtn) fBuyBtn.textContent = `外資連買 (${fBuyCount})`;
    if (fSellBtn) fSellBtn.textContent = `外資連賣 (${fSellCount})`;
    if (tBuyBtn) tBuyBtn.textContent = `投信連買 (${tBuyCount})`;
    if (tSellBtn) tSellBtn.textContent = `投信連賣 (${tSellCount})`;
}

function populateRankingTable(tableId, list, streakCol, latestCol) {
    const tbody = document.querySelector(`#${tableId} tbody`);
    if (list.length === 0) {
        tbody.innerHTML = '<tr><td colspan="6" class="text-center">今日無符合之個股</td></tr>';
        return;
    }
    
    let html = '';
    list.forEach(row => {
        const streak = Math.abs(row[streakCol]);
        const streakLabel = row[streakCol] > 0 ? 
            `<span style="color: var(--color-up); font-weight: 600;">連買 ${streak} 天</span>` :
            `<span style="color: var(--color-down); font-weight: 600;">連賣 ${streak} 天</span>`;
            
        html += `
            <tr style="cursor: pointer;" onclick="searchStockDirectly('${row.Symbol}')">
                <td><strong>${row.Symbol}</strong></td>
                <td>${row.Name}</td>
                <td>${row.Industry}</td>
                <td>${row.Market}</td>
                <td class="text-right">${streakLabel}</td>
                <td class="text-right">${formatAmount(row[latestCol])}</td>
            </tr>
        `;
    });
    tbody.innerHTML = html;
}

// Link click helper to directly search for a stock and open details modal
window.searchStockDirectly = function(symbol) {
    if (streaksData && streaksData.Data) {
        const match = streaksData.Data.find(s => s.Symbol === symbol);
        if (match) {
            stockSearchInput.value = `${match.Symbol} ${match.Name}`;
            showStockDetails(match);
            const suggestionsContainer = document.getElementById('search-suggestions');
            if (suggestionsContainer) {
                suggestionsContainer.innerHTML = '';
                suggestionsContainer.classList.add('hidden');
            }
        }
    }
};

// Update CSS classes and layout based on docking state
function updateDetailLayout() {
    const dockToggleBtn = document.getElementById('dock-toggle-btn');
    const backdrop = document.getElementById('modal-backdrop');
    
    if (isDockedRight) {
        stockDetailSection.classList.add('docked-right');
        if (dockToggleBtn) dockToggleBtn.textContent = '⬅️ 浮動視窗';
        
        // Hide backdrop overlay in docked mode so the user can interact with the main page
        if (backdrop) backdrop.classList.remove('active');
    } else {
        stockDetailSection.classList.remove('docked-right');
        if (dockToggleBtn) dockToggleBtn.textContent = '➡️ 停靠右側';
        
        // Show backdrop in centered floating modal mode
        if (stockDetailSection.classList.contains('active')) {
            if (backdrop) backdrop.classList.add('active');
        }
    }
}

// Show stock detail section
function showStockDetails(stock) {
    document.getElementById('stock-detail-title').textContent = `🔍 個股數據查詢: ${stock.Symbol} ${stock.Name}`;
    document.getElementById('stock-detail-market').textContent = stock.Market;
    document.getElementById('stock-detail-industry').textContent = stock.Industry;
    
    // Price details
    const close = stock.Close;
    const change = stock.Change;
    document.getElementById('stock-detail-close').textContent = close > 0 ? `${close.toFixed(2)} 元` : '-- 元';
    
    const changeEl = document.getElementById('stock-detail-change');
    if (change > 0) {
        changeEl.className = "stock-price-change badge-up";
        changeEl.textContent = `+${change.toFixed(2)} 元 (+${((change/(close-change))*100).toFixed(2)}%)`;
    } else if (change < 0) {
        changeEl.className = "stock-price-change badge-down";
        changeEl.textContent = `${change.toFixed(2)} 元 (${((change/(close-change))*100).toFixed(2)}%)`;
    } else {
        changeEl.className = "stock-price-change";
        changeEl.textContent = '0.00 元 (0.00%)';
    }
    
    // OHL details
    document.getElementById('stock-detail-open').textContent = stock.Open > 0 ? `${stock.Open.toFixed(2)} 元` : '--';
    document.getElementById('stock-detail-high').textContent = stock.High > 0 ? `${stock.High.toFixed(2)} 元` : '--';
    document.getElementById('stock-detail-low').textContent = stock.Low > 0 ? `${stock.Low.toFixed(2)} 元` : '--';
    document.getElementById('stock-detail-volume').textContent = stock.Volume > 0 ? `${formatNumber(stock.Volume)} 張` : '0 張';
    
    // Streaks
    document.getElementById('stock-streak-foreign').innerHTML = formatStreakText(stock.Foreign_Streak, stock.Foreign_Latest);
    document.getElementById('stock-streak-trust').innerHTML = formatStreakText(stock.Trust_Streak, stock.Trust_Latest);
    document.getElementById('stock-streak-dealer').innerHTML = formatStreakText(stock.Dealer_Streak, stock.Dealer_Latest);
    document.getElementById('stock-streak-total').innerHTML = formatStreakText(stock.Total_Streak, stock.Total_Latest);

    // Open the modal by adding active class
    stockDetailSection.classList.add('active');
    
    // Apply styling based on current docking preference
    updateDetailLayout();
}

function hideStockDetails() {
    stockDetailSection.classList.remove('active');
    
    const backdrop = document.getElementById('modal-backdrop');
    if (backdrop) backdrop.classList.remove('active');
}

// Bootstrap
window.addEventListener('DOMContentLoaded', initApp);
