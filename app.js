// Global State Variables
let streaksData = null;
let marketSummary = null;
let futuresOptions = null;
let currentPage = {
    'foreign-buy': 1,
    'foreign-sell': 1,
    'trust-buy': 1,
    'trust-sell': 1,
    'dual-buy': 1,
    'dual-sell': 1
};
let isDockedRight = localStorage.getItem('detail-docked') === 'true';
let activeFuturesType = 'tx';
let watchlist = [];
let currentDetailStock = null;

// DOM Elements
const themeToggleBtn = document.getElementById('theme-toggle');
const stockSearchInput = document.getElementById('stock-search');
const closeSearchBtn = document.getElementById('close-search-btn');
const stockDetailSection = document.getElementById('stock-detail-section');

// Format helpers

// Shared "positive/negative value -> colored badge" formatter. Replaces the
// 4 near-identical if/else-if/else blocks that used to be duplicated across
// formatAmount(), formatStreakText(), formatBillion() and the inline
// formatOI() inside renderFuturesHistoryTable().
// sign: pass true to prefix positive values with "+" (most callers want this).
function badgeSpan(value, formattedText, { sign = true, zeroText = null } = {}) {
    if (value > 0) {
        return `<span class="badge-up">${sign ? '+' : ''}${formattedText}</span>`;
    } else if (value < 0) {
        return `<span class="badge-down">${formattedText}</span>`;
    } else {
        return zeroText !== null ? zeroText : formattedText;
    }
}

function formatNumber(num) {
    if (num === undefined || num === null) return '--';
    return Number(num).toLocaleString('zh-TW');
}

function formatAmount(lots) {
    if (lots === undefined || lots === null) return '--';
    const numLots = Math.round(lots / 1000);
    return badgeSpan(numLots, `${numLots.toLocaleString('zh-TW')} 張`, { zeroText: '0 張' });
}

function formatStreakText(streakVal, latestVal) {
    if (streakVal === undefined || streakVal === null) return '--';
    const lots = Math.round(latestVal / 1000);
    const lotsHtml = badgeSpan(lots, `${lots.toLocaleString('zh-TW')} 張`, { zeroText: '0 張' });

    if (streakVal > 0) {
        return `<span class="text-up">連買 ${streakVal} 天</span> (今日: ${lotsHtml})`;
    } else if (streakVal < 0) {
        return `<span class="text-down">連賣 ${Math.abs(streakVal)} 天</span> (今日: ${lotsHtml})`;
    } else {
        return `無連續趨勢 (今日: ${lotsHtml})`;
    }
}

function formatBillion(valStr) {
    if (valStr === undefined || valStr === null) return '--';
    try {
        const val = parseInt(String(valStr).replace(/,/g, '').trim());
        const billion = val / 100000000.0;
        return badgeSpan(billion, `${billion.toFixed(2)} 億`, { zeroText: '0.00 億' });
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
    setupScrollButtons();
    loadWatchlist();
    renderWatchlist();
    
    try {
        console.log("Loading static dataset...");

        // Fetch the build's own timestamp first. We use it as a *stable*
        // version string for every other request below, instead of the old
        // `?t=${Date.now()}` approach. Date.now() changes on every single
        // page load, which defeats the browser's HTTP cache entirely and
        // forces a full re-download of every JSON file (and the chart PNG)
        // on every visit, even when the data hasn't changed since the last
        // 17:00 build. Using the build timestamp means repeat visits within
        // the same day hit the cache, and a fresh fetch only happens once
        // the data actually changes.
        const lastUpdateRes = await fetch(`./data/last_update.json?t=${new Date().getTime()}`);
        const lastUpdateInfo = await lastUpdateRes.json();
        const dataVersion = lastUpdateInfo.last_updated
            ? `?v=${encodeURIComponent(lastUpdateInfo.last_updated)}`
            : `?t=${new Date().getTime()}`; // fallback if last_update.json is ever missing the field
        displayLastUpdated(lastUpdateInfo);

        // 1. Fetch market summary
        const summaryRes = await fetch(`./data/market_summary.json${dataVersion}`);
        marketSummary = await summaryRes.json();
        renderMarketSummary();
        
        // 2. Fetch futures & options
        const futOptRes = await fetch(`./data/futures_options.json${dataVersion}`);
        futuresOptions = await futOptRes.json();
        renderFuturesOptions(dataVersion);
        
        // 3. Fetch streaks list
        const streaksRes = await fetch(`./data/streaks.json${dataVersion}`);
        streaksData = await streaksRes.json();
        renderRankings();
        renderWatchlist();

        // 4. Pre-open brief. Independent of the above: it is generated by a
        // separate workflow and may legitimately be absent or a day behind, so
        // a failure here must not take the rest of the dashboard down with it.
        renderMorningBrief(dataVersion);

    } catch (error) {
        console.error("Error initializing dashboard data:", error);
    }
}

function displayLastUpdated(lastUpdateInfo) {
    const el = document.getElementById('last-updated');
    if (el && lastUpdateInfo && lastUpdateInfo.last_updated) {
        // Parse ISO string and format as "YYYY-MM-DD HH:MM:SS (UTC+8)"
        const d = new Date(lastUpdateInfo.last_updated);

        // Format directly to Asia/Taipei timezone
        const formatter = new Intl.DateTimeFormat('zh-TW', {
            timeZone: 'Asia/Taipei',
            year: 'numeric',
            month: '2-digit',
            day: '2-digit',
            hour: '2-digit',
            minute: '2-digit',
            second: '2-digit',
            hour12: false
        });

        const parts = formatter.formatToParts(d);
        const partObj = {};
        parts.forEach(p => partObj[p.type] = p.value);

        const formatted = `${partObj.year}-${partObj.month}-${partObj.day} ${partObj.hour}:${partObj.minute}:${partObj.second} (UTC+8)`;
        el.textContent = formatted;
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
    const tabIds = ['foreign-buy', 'foreign-sell', 'trust-buy', 'trust-sell', 'dual-buy', 'dual-sell'];
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

    // Favorite star toggle button event listener
    const favoriteToggleBtn = document.getElementById('favorite-toggle-btn');
    if (favoriteToggleBtn) {
        favoriteToggleBtn.addEventListener('click', () => {
            if (currentDetailStock) {
                toggleWatchlist(currentDetailStock.Symbol);
            }
        });
    }
}

// Watchlist state and functions
function loadWatchlist() {
    try {
        watchlist = JSON.parse(localStorage.getItem('watchlist')) || [];
    } catch (e) {
        watchlist = [];
    }
}

// Global scope check so that it can be deleted in child buttons safely
function saveWatchlist() {
    localStorage.setItem('watchlist', JSON.stringify(watchlist));
}

function toggleWatchlist(symbol) {
    const idx = watchlist.indexOf(symbol);
    const favoriteToggleBtn = document.getElementById('favorite-toggle-btn');
    
    if (idx > -1) {
        watchlist.splice(idx, 1);
        if (favoriteToggleBtn) {
            favoriteToggleBtn.classList.remove('active');
            favoriteToggleBtn.innerHTML = '☆ 關注';
        }
    } else {
        watchlist.push(symbol);
        if (favoriteToggleBtn) {
            favoriteToggleBtn.classList.add('active');
            favoriteToggleBtn.innerHTML = '⭐ 已關注';
        }
    }
    saveWatchlist();
    renderWatchlist();
}

function renderWatchlist() {
    const watchlistContainer = document.getElementById('watchlist-container');
    if (!watchlistContainer) return;
    
    if (watchlist.length === 0) {
        watchlistContainer.innerHTML = `
            <div class="watchlist-placeholder">
                <span>💡 您目前尚未加入任何關注股票。請在右上方搜尋框查詢個股後，點選「☆ 關注」按鈕加入。</span>
            </div>
        `;
        return;
    }
    
    let html = '';
    watchlist.forEach(symbol => {
        let stock = null;
        if (streaksData && streaksData.Data) {
            stock = streaksData.Data.find(s => s.Symbol === symbol);
        }
        
        if (stock) {
            const changePercent = ((stock.Change / (stock.Close - stock.Change)) * 100).toFixed(2);
            const changeColor = stock.Change > 0 ? 'var(--color-up)' : (stock.Change < 0 ? 'var(--color-down)' : 'var(--text-secondary)');
            const changeSign = stock.Change > 0 ? '+' : '';
            
            html += `
                <div class="watchlist-chip" onclick="window.searchStockDirectly('${stock.Symbol}')">
                    <span class="watchlist-chip-title">${stock.Symbol} ${stock.Name}</span>
                    <span class="watchlist-chip-price">${stock.Close.toFixed(2)} 元</span>
                    <span class="watchlist-chip-change" style="color: ${changeColor}">
                        ${changeSign}${stock.Change.toFixed(2)} (${changeSign}${changePercent}%)
                    </span>
                    <button class="watchlist-chip-remove" data-symbol="${stock.Symbol}" title="移出關注名單">&times;</button>
                </div>
            `;
        } else {
            html += `
                <div class="watchlist-chip" onclick="window.searchStockDirectly('${symbol}')">
                    <span class="watchlist-chip-title">${symbol}</span>
                    <button class="watchlist-chip-remove" data-symbol="${symbol}" title="移出關注名單">&times;</button>
                </div>
            `;
        }
    });
    
    watchlistContainer.innerHTML = html;
    
    // Bind click listener for removal buttons (prevent propagation to chip click)
    const removeBtns = watchlistContainer.querySelectorAll('.watchlist-chip-remove');
    removeBtns.forEach(btn => {
        btn.addEventListener('click', (e) => {
            e.stopPropagation();
            const symbol = btn.getAttribute('data-symbol');
            toggleWatchlist(symbol);
        });
    });
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

    const orderMap = {
        '外資 (不含自營)': 1,
        '外資自營': 2,
        '投信': 3,
        '自營 (自行買賣)': 4,
        '自營 (避險)': 5,
        '合計': 6,
        '三大法人合計': 6
    };

    const twseRows = [];
    const tpexRows = [];

    marketSummary.Data.forEach(row => {
        const shortenedName = shortenCategoryName(row.Category);
        if (orderMap.hasOwnProperty(shortenedName)) {
            const mappedRow = {
                Category: shortenedName,
                Buy: row.Buy,
                Sell: row.Sell,
                Net: row.Net
            };
            if (row.Market.includes("上市")) {
                twseRows.push(mappedRow);
            } else if (row.Market.includes("上櫃")) {
                tpexRows.push(mappedRow);
            }
        }
    });

    const sortByOrder = (a, b) => orderMap[a.Category] - orderMap[b.Category];
    twseRows.sort(sortByOrder);
    tpexRows.sort(sortByOrder);

    const buildTableHtml = (rows) => {
        return rows.map(row => `
            <tr>
                <td><strong>${row.Category}</strong></td>
                <td class="text-right">${formatBillionValue(row.Buy)}</td>
                <td class="text-right">${formatBillionValue(row.Sell)}</td>
                <td class="text-right">${formatBillion(row.Net)}</td>
            </tr>
        `).join('');
    };

    const twseHtml = buildTableHtml(twseRows);
    const tpexHtml = buildTableHtml(tpexRows);
    
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
    
    const isMobile = window.innerWidth <= 576;
    let html = '';
    const history = (futuresOptions.FuturesHistory || []).slice(0, 5);
    history.forEach(row => {
        const d = row.Date;
        const formattedDate = isMobile ? `${d.slice(4,6)}/${d.slice(6)}` : `${d.slice(0,4)}/${d.slice(4,6)}/${d.slice(6)}`;
        
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
            return badgeSpan(val, val.toLocaleString(), { zeroText: '0' });
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
function renderFuturesOptions(dataVersion) {
    const chartImg = document.getElementById('futures-trend-chart');
    const fallbackTxt = document.getElementById('chart-fallback');
    
    if (!futuresOptions) {
        const tableBody = document.querySelector('#futures-oi-table tbody');
        if (tableBody) tableBody.innerHTML = '<tr><td colspan="5" class="text-center">查無期貨未平倉資料</td></tr>';
        return;
    }
    
    // Set Chart Image src, versioned by the data build timestamp so it's
    // cached across repeat visits on the same day instead of re-downloaded
    // on every page load.
    chartImg.src = `./data/futures_trend.png${dataVersion || ''}`;
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
    
    // build_static_data.py writes FuturesHistory in reverse chronological
    // order (newest first), so index 0 is always the latest trading day.
    const history = futuresOptions.FuturesHistory;
    const latest = history[0];
    const prev = history[1];
    
    const latestOI = latest.Foreign_Net;
    const prevOI = prev.Foreign_Net;
    const oiDiff = latestOI - prevOI;
    const oiType = latestOI < 0 ? "淨空單" : "淨多單";
    
    let step1 = "";
    let oiTrend = "";
    if (latestOI < 0) {
        if (oiDiff < 0) {
            step1 = `<span class="text-up">空單增加（更負） => 外資偏空，壓力大。</span>`;
            oiTrend = "increase";
        } else {
            step1 = `<span class="text-down">空單減少（負值縮小） => 外資回補，行情有機會反彈。</span>`;
            oiTrend = "decrease";
        }
    } else {
        if (oiDiff > 0) {
            step1 = `<span class="text-up">多單增加 => 外資偏多，行情支撐強。</span>`;
            oiTrend = "increase";
        } else {
            step1 = `<span class="text-down">多單減少 => 外資退場，多方力道減弱。</span>`;
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
            step2 = `<span class="text-up">OI 增加 + 指數下跌 => 空方力量強，趨勢偏空。</span>`;
            summarySentiment = "大盤目前呈現「外資期貨空單增加且指數下跌」的空頭格局。空方力量強勁，趨勢偏空，短期建議保守看待。";
        } else if (oiTrend === "decrease" && priceTrend === "up") {
            step2 = `<span class="text-down">OI 減少 + 指數上漲 => 外資回補，行情偏多。</span>`;
            summarySentiment = "大盤目前呈現「外資期貨空單減少且指數上漲」的偏多格局。外資空單回補，行情有反彈或持續上攻的機會。";
        } else if (oiTrend === "increase" && priceTrend === "up") {
            step2 = `<span class="text-up">OI 增加 + 指數上漲 => 可能是避險，需觀察是否反轉。</span>`;
            summarySentiment = "大盤目前呈現「外資期貨空單增加但指數上漲」的避險格局。外資在指數走高時增持空單避險，需提防行情可能隨時出現反轉。";
        } else if (oiTrend === "decrease" && priceTrend === "down") {
            step2 = `<span class="text-down">OI 減少 + 指數下跌 => 外資退場，行情可能整理。</span>`;
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
    // 5. Dual Buy                     
    const dBuyAll = data.filter(r => r.Dual_Buy_Streak >= minDays && (isNaN(maxDays) || r.Dual_Buy_Streak <= maxDays))
                        .sort((a, b) => b.Dual_Buy_Streak - a.Dual_Buy_Streak || (b.Foreign_Latest + b.Trust_Latest) - (a.Foreign_Latest + a.Trust_Latest));

    // 6. Dual Sell
    const dSellAll = data.filter(r => r.Dual_Sell_Streak <= -minDays && (isNaN(maxDays) || r.Dual_Sell_Streak >= -maxDays))
                         .sort((a, b) => a.Dual_Sell_Streak - b.Dual_Sell_Streak || (a.Foreign_Latest + a.Trust_Latest) - (b.Foreign_Latest + b.Trust_Latest));
    
    // Render each table with pagination
    renderTableWithPagination('foreign-buy', 'table-foreign-buy', fBuyAll, 'Foreign_Streak', 'Foreign_Latest', rowsPerPage);
    renderTableWithPagination('foreign-sell', 'table-foreign-sell', fSellAll, 'Foreign_Streak', 'Foreign_Latest', rowsPerPage);
    renderTableWithPagination('trust-buy', 'table-trust-buy', tBuyAll, 'Trust_Streak', 'Trust_Latest', rowsPerPage);
    renderTableWithPagination('trust-sell', 'table-trust-sell', tSellAll, 'Trust_Streak', 'Trust_Latest', rowsPerPage);
    renderTableWithPagination('dual-buy', 'table-dual-buy', dBuyAll, 'Dual_Buy_Streak', 'Foreign_Latest', rowsPerPage);
    renderTableWithPagination('dual-sell', 'table-dual-sell', dSellAll, 'Dual_Sell_Streak', 'Foreign_Latest', rowsPerPage);
    
    // Update tab headers to display total matching count dynamically
    updateTabCounts(fBuyAll.length, fSellAll.length, tBuyAll.length, tSellAll.length, dBuyAll.length, dSellAll.length);
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

// ---------- Pre-open morning brief ----------

function briefPctClass(v) {
    if (v === null || v === undefined) return '';
    return v >= 0 ? 'text-up' : 'text-down';
}

function briefPct(v, digits = 2) {
    if (v === null || v === undefined) return '—';
    return `${v >= 0 ? '+' : ''}${v.toFixed(digits)}%`;
}

function briefStatTile(label, value, sub, cls) {
    return `<div class="brief-tile">
                <div class="brief-tile-label">${label}</div>
                <div class="brief-tile-value ${cls || ''}">${value}</div>
                ${sub ? `<div class="brief-tile-sub">${sub}</div>` : ''}
            </div>`;
}

async function renderMorningBrief(dataVersion) {
    const section = document.getElementById('morning-brief-section');
    const body = document.getElementById('morning-brief-body');
    if (!section || !body) return;

    let brief;
    try {
        const res = await fetch(`./data/morning_brief.json${dataVersion || ''}`);
        if (!res.ok) return;           // not generated yet: leave the card hidden
        brief = await res.json();
    } catch (e) {
        console.warn('Morning brief unavailable:', e);
        return;
    }
    if (!brief || !brief.Date) return;

    const dateLabel = `${brief.Date.slice(0, 4)}/${brief.Date.slice(4, 6)}/${brief.Date.slice(6)}`;
    const badge = document.getElementById('morning-brief-date');
    if (badge) badge.textContent = `${dateLabel} 盤前`;

    const groups = [];

    // Overnight US markets
    if (brief.UsMarkets && brief.UsMarkets.length) {
        const tiles = brief.UsMarkets.map(m => briefStatTile(
            m.Name,
            briefPct(m.ChangePct),
            m.Close.toLocaleString(),
            briefPctClass(m.ChangePct)
        )).join('');
        groups.push(`<div class="brief-group">
                        <h3 class="brief-group-title">🌎 美股隔夜收盤</h3>
                        <div class="brief-tiles">${tiles}</div>
                     </div>`);
    }

    // ADR + night session: the two things that hint at the open
    const gapTiles = [];
    if (brief.Adr) {
        const a = brief.Adr;
        gapTiles.push(briefStatTile(
            '台積電 ADR',
            briefPct(a.ChangePct),
            `${a.Close} USD`,
            briefPctClass(a.ChangePct)
        ));
        gapTiles.push(briefStatTile(
            'ADR 溢價率',
            briefPct(a.PremiumPct),
            `換算 ${a.ImpliedTwd} / 台股 ${a.TwClose}`,
            briefPctClass(a.PremiumPct)
        ));
    }
    if (brief.NightSession && brief.NightSession.GapPct !== undefined) {
        const n = brief.NightSession;
        gapTiles.push(briefStatTile(
            '台指期夜盤',
            briefPct(n.GapPct),
            `收 ${n.Close.toLocaleString()}（${n.GapPoints > 0 ? '+' : ''}${n.GapPoints} 點）`,
            briefPctClass(n.GapPct)
        ));
    } else {
        // Absent by design when TAIFEX cannot be read cleanly; say so rather
        // than leave a silent hole the reader might mistake for "flat".
        gapTiles.push(briefStatTile('台指期夜盤', '—', '盤中無法判讀，暫不顯示', ''));
    }
    if (gapTiles.length) {
        groups.push(`<div class="brief-group">
                        <h3 class="brief-group-title">🔮 開盤參考</h3>
                        <div class="brief-tiles">${gapTiles.join('')}</div>
                     </div>`);
    }

    // Yesterday's chips
    const c = brief.Chips || {};
    const chipTiles = [];
    if (c.ForeignFuturesNet) {
        const f = c.ForeignFuturesNet;
        const chg = f.Change;
        chipTiles.push(briefStatTile(
            '外資期貨淨未平倉',
            `${f.Net.toLocaleString()} 口`,
            chg !== undefined ? `較前日 ${chg > 0 ? '+' : ''}${chg.toLocaleString()} 口` : '',
            f.Net >= 0 ? 'text-up' : 'text-down'
        ));
    }
    if (c.OptionLevels) {
        const o = c.OptionLevels;
        chipTiles.push(briefStatTile('選擇權上檔壓力', o.Resistance.toLocaleString(),
            `Max Call OI ${o.ResistanceOI.toLocaleString()}`, 'text-down'));
        chipTiles.push(briefStatTile('選擇權下檔支撐', o.Support.toLocaleString(),
            `Max Put OI ${o.SupportOI.toLocaleString()}`, 'text-up'));
    }
    if (chipTiles.length) {
        groups.push(`<div class="brief-group">
                        <h3 class="brief-group-title">🎯 昨日籌碼（${c.ChipDate || ''}）</h3>
                        <div class="brief-tiles">${chipTiles.join('')}</div>
                     </div>`);
    }

    const listGroups = [];
    const mkList = (title, arr, fmt) => {
        if (!arr || !arr.length) return '';
        return `<div class="brief-list">
                    <h4 class="brief-list-title">${title}</h4>
                    <ol>${arr.map(fmt).join('')}</ol>
                </div>`;
    };
    listGroups.push(mkList('外資連買天數 Top 5', c.ForeignBuyStreak,
        s => `<li><span class="brief-li-name" onclick="searchStockDirectly('${s.Symbol}')">${s.Symbol} ${s.Name}</span><span class="text-up">${s.Streak} 天</span></li>`));
    listGroups.push(mkList('投信連買天數 Top 5', c.TrustBuyStreak,
        s => `<li><span class="brief-li-name" onclick="searchStockDirectly('${s.Symbol}')">${s.Symbol} ${s.Name}</span><span class="text-up">${s.Streak} 天</span></li>`));
    listGroups.push(mkList('投信昨日新進場', c.TrustFreshBuys,
        s => `<li><span class="brief-li-name" onclick="searchStockDirectly('${s.Symbol}')">${s.Symbol} ${s.Name}</span><span class="text-secondary">${Math.round((s.Shares || 0) / 1000).toLocaleString()} 張</span></li>`));
    const listsHtml = listGroups.filter(Boolean).join('');
    if (listsHtml) {
        groups.push(`<div class="brief-group"><div class="brief-lists">${listsHtml}</div></div>`);
    }

    // Settlement notice only when it is actually relevant
    if (brief.Settlement && brief.Settlement.IsSettlementWeek) {
        const s = brief.Settlement;
        groups.push(`<div class="brief-alert">
                        ${s.IsSettlementDay ? '⚠️ <strong>今日為結算日</strong>' : '📅 本週為結算週'}
                        ${s.SettlementDate ? `，結算日 ${s.SettlementDate}` : ''}
                     </div>`);
    }

    body.innerHTML = groups.join('');
    section.classList.remove('hidden');
}

// Share-weighted price over the current streak, shown next to the last close so
// a reader can see whether price sits above or below where the flow accumulated.
// Deliberately not labelled a cost basis: T86 reports net shares (see
// compute_streak_avg_prices in build_static_data.py).
function renderStreakAvgPrice(row, which) {
    const avg = which === 'Trust' ? row.Trust_StreakAvgPrice : row.Foreign_StreakAvgPrice;
    if (!avg) return '<span class="avg-price-empty" title="連續未達 2 日，或該股無可用歷史股價">—</span>';

    const close = row.Close;
    if (!close) return `<span class="avg-price-value">${avg.toFixed(2)}</span>`;

    const diffPct = (close / avg - 1) * 100;
    const cls = diffPct >= 0 ? 'text-up' : 'text-down';
    const sign = diffPct >= 0 ? '+' : '';
    return `<div class="avg-price-cell">
                <span class="avg-price-value">${avg.toFixed(2)}</span>
                <span class="avg-price-diff ${cls}">現價 ${sign}${diffPct.toFixed(1)}%</span>
            </div>`;
}

function populateRankingTable(tableId, list, streakCol, latestCol) {
    const tbody = document.querySelector(`#${tableId} tbody`);
    if (list.length === 0) {
        tbody.innerHTML = '<tr><td colspan="7" class="text-center">今日無符合之個股</td></tr>';
        return;
    }
    
    let html = '';
    list.forEach(row => {
        let streakLabel = '';
        let amountLabel = '';

     
        if (tableId === 'table-dual-buy') {
            streakLabel = `<div style="line-height:1.4;"><span class="text-up">外資連買 ${row.Foreign_Streak}天</span><br><span class="text-up">投信連買 ${row.Trust_Streak}天</span></div>`;
            amountLabel = `<div style="font-size:13px; line-height:1.4;">外: ${formatAmount(row.Foreign_Latest)}<br>投: ${formatAmount(row.Trust_Latest)}</div>`;
        } else if (tableId === 'table-dual-sell') {
            streakLabel = `<div style="line-height:1.4;"><span class="text-down">外資連賣 ${Math.abs(row.Foreign_Streak)}天</span><br><span class="text-down">投信連賣 ${Math.abs(row.Trust_Streak)}天</span></div>`;
            amountLabel = `<div style="font-size:13px; line-height:1.4;">外: ${formatAmount(row.Foreign_Latest)}<br>投: ${formatAmount(row.Trust_Latest)}</div>`;
        } else {

            const streak = Math.abs(row[streakCol]);
            streakLabel = row[streakCol] > 0 ? 
                `<span class="text-up">連買 ${streak} 天</span>` :
                `<span class="text-down">連賣 ${streak} 天</span>`;
            amountLabel = formatAmount(row[latestCol]);
        }
            
        const avgWhich = (tableId === 'table-trust-buy' || tableId === 'table-trust-sell')
            ? 'Trust' : 'Foreign';

        html += `
            <tr style="cursor: pointer;" onclick="searchStockDirectly('${row.Symbol}')">
                <td><strong>${row.Symbol}</strong></td>
                <td>${row.Name}</td>
                <td>${row.Industry}</td>
                <td>${row.Market}</td>
                <td class="text-right">${streakLabel}</td>
                <td class="text-right">${amountLabel}</td>
                <td class="text-right">${renderStreakAvgPrice(row, avgWhich)}</td>
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
        if (dockToggleBtn) dockToggleBtn.textContent = '⬅️ 置中彈窗';
        
        // Hide backdrop overlay in docked mode so the user can interact with the main page
        if (backdrop) backdrop.classList.remove('active');
    } else {
        stockDetailSection.classList.remove('docked-right');
        if (dockToggleBtn) dockToggleBtn.textContent = '➡️ 側邊面板';
        
        // Show backdrop in centered floating modal mode
        if (stockDetailSection.classList.contains('active')) {
            if (backdrop) backdrop.classList.add('active');
        }
    }
}

// Show stock detail section
function showStockDetails(stock) {
    currentDetailStock = stock;
    
    // Update favorite button state
    const favoriteToggleBtn = document.getElementById('favorite-toggle-btn');
    if (favoriteToggleBtn) {
        if (watchlist.includes(stock.Symbol)) {
            favoriteToggleBtn.classList.add('active');
            favoriteToggleBtn.innerHTML = '⭐ 已關注';
        } else {
            favoriteToggleBtn.classList.remove('active');
            favoriteToggleBtn.innerHTML = '☆ 關注';
        }
    }

    // Update Yahoo Stock link
    const yahooLink = document.getElementById('yahoo-stock-link');
    if (yahooLink) {
        const suffix = stock.Market.includes('上櫃') || stock.Market.includes('TPEx') ? 'TWO' : 'TW';
        yahooLink.href = `https://tw.stock.yahoo.com/quote/${stock.Symbol}.${suffix}`;
    }

    // Update Intraday Live warning banner
    const liveIndicator = document.getElementById('stock-live-indicator');
    if (liveIndicator) {
        try {
            // Get current time in Taipei timezone (UTC+8)
            const taipeiDate = new Date(new Date().toLocaleString("en-US", {timeZone: "Asia/Taipei"}));
            const day = taipeiDate.getDay(); // 0: Sunday, 1-5: Mon-Fri, 6: Sat
            const hours = taipeiDate.getHours();
            const minutes = taipeiDate.getMinutes();
            const timeValue = hours * 60 + minutes;
            
            // Monday to Friday (1-5) and 09:00 (540 mins) to 13:30 (810 mins)
            const isTradingHours = (day >= 1 && day <= 5) && (timeValue >= 540 && timeValue <= 810);
            
            if (isTradingHours) {
                liveIndicator.classList.remove('hidden');
            } else {
                liveIndicator.classList.add('hidden');
            }
        } catch (e) {
            console.error("Error calculating Taipei trading hours:", e);
            liveIndicator.classList.add('hidden');
        }
    }

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
    document.getElementById('stock-streak-dealer-prop').innerHTML = formatStreakText(stock.DealerProp_Streak, stock.DealerProp_Latest);
    document.getElementById('stock-streak-dealer-hedge').innerHTML = formatStreakText(stock.DealerHedge_Streak, stock.DealerHedge_Latest);
    document.getElementById('stock-streak-dealer').innerHTML = formatStreakText(stock.Dealer_Streak, stock.Dealer_Latest);
    document.getElementById('stock-streak-total').innerHTML = formatStreakText(stock.Total_Streak, stock.Total_Latest);

    // SBL details
    const sblSoldEl = document.getElementById('stock-sbl-sold');
    const sblReturnedEl = document.getElementById('stock-sbl-returned');
    const sblBalanceEl = document.getElementById('stock-sbl-balance');
    const sblSummaryEl = document.getElementById('stock-sbl-summary');
    
    if (sblSoldEl && sblReturnedEl && sblBalanceEl && sblSummaryEl) {
        const sblSoldLots = Math.round((stock.SBL_Sold || 0) / 1000);
        const sblReturnedLots = Math.round((stock.SBL_Returned || 0) / 1000);
        const sblBalanceLots = Math.round((stock.SBL_Balance || 0) / 1000);
        
        sblSoldEl.textContent = `${formatNumber(sblSoldLots)} 張`;
        sblReturnedEl.textContent = `${formatNumber(sblReturnedLots)} 張`;
        sblBalanceEl.textContent = `${formatNumber(sblBalanceLots)} 張`;
        
        const sblNet = sblSoldLots - sblReturnedLots;
        
        if (sblBalanceLots === 0 && sblSoldLots === 0 && sblReturnedLots === 0) {
            sblSummaryEl.className = "sbl-summary-banner";
            sblSummaryEl.textContent = "此股無借券放空餘額，或不適用借券賣出。";
        } else if (sblNet > 0) {
            sblSummaryEl.className = "sbl-summary-banner bearish";
            sblSummaryEl.innerHTML = `📉 今日 SBL 淨增加 <strong>${formatNumber(sblNet)} 張</strong> (外資/法人偏空放空力道增強)`;
        } else if (sblNet < 0) {
            sblSummaryEl.className = "sbl-summary-banner bullish";
            sblSummaryEl.innerHTML = `📈 今日 SBL 淨減少 <strong>${formatNumber(Math.abs(sblNet))} 張</strong> (空單回補 / 法人放空力道減弱)`;
        } else {
            sblSummaryEl.className = "sbl-summary-banner";
            sblSummaryEl.textContent = "今日 SBL 無增減淨變動 (放空與回補力道持平)。";
        }
    }

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

function setupScrollButtons() {
    const toTopBtn = document.getElementById('scroll-to-top');
    const toBottomBtn = document.getElementById('scroll-to-bottom');
    
    if (!toTopBtn || !toBottomBtn) return;
    
    // Toggle visibility based on scroll position
    window.addEventListener('scroll', () => {
        const scrollY = window.scrollY;
        const totalHeight = document.documentElement.scrollHeight;
        const viewportHeight = window.innerHeight;
        
        // Show scroll-to-top if we scrolled down a bit (more than 300px)
        if (scrollY > 300) {
            toTopBtn.classList.add('visible');
        } else {
            toTopBtn.classList.remove('visible');
        }
        
        // Show scroll-to-bottom if we are not near the bottom (more than 300px away)
        if (scrollY < totalHeight - viewportHeight - 300) {
            toBottomBtn.classList.add('visible');
        } else {
            toBottomBtn.classList.remove('visible');
        }
    });
    
    // Scroll click handlers
    toTopBtn.addEventListener('click', () => {
        window.scrollTo({ top: 0, behavior: 'smooth' });
    });
    
    toBottomBtn.addEventListener('click', () => {
        window.scrollTo({ top: document.documentElement.scrollHeight, behavior: 'smooth' });
    });
    
    // Keyboard shortcuts (T: Top, B: Bottom)
    window.addEventListener('keydown', (e) => {
        // Ignore if user is typing in input fields
        const activeEl = document.activeElement;
        if (activeEl && (activeEl.tagName === 'INPUT' || activeEl.tagName === 'TEXTAREA' || activeEl.isContentEditable)) {
            return;
        }
        
        const key = e.key.toLowerCase();
        if (key === 't') {
            e.preventDefault();
            window.scrollTo({ top: 0, behavior: 'smooth' });
        } else if (key === 'b') {
            e.preventDefault();
            window.scrollTo({ top: document.documentElement.scrollHeight, behavior: 'smooth' });
        }
    });
}

function updateTabCounts(fBuyCount, fSellCount, tBuyCount, tSellCount, dBuyCount, dSellCount) {
    const fBuyBtn = document.querySelector('.tab-btn[data-tab="foreign-buy"]');
    const fSellBtn = document.querySelector('.tab-btn[data-tab="foreign-sell"]');
    const tBuyBtn = document.querySelector('.tab-btn[data-tab="trust-buy"]');
    const tSellBtn = document.querySelector('.tab-btn[data-tab="trust-sell"]');
    const dBuyBtn = document.querySelector('.tab-btn[data-tab="dual-buy"]');
    const dSellBtn = document.querySelector('.tab-btn[data-tab="dual-sell"]');
    
    if (fBuyBtn) fBuyBtn.textContent = `外資連買 (${fBuyCount})`;
    if (fSellBtn) fSellBtn.textContent = `外資連賣 (${fSellCount})`;
    if (tBuyBtn) tBuyBtn.textContent = `投信連買 (${tBuyCount})`;
    if (tSellBtn) tSellBtn.textContent = `投信連賣 (${tSellCount})`;
    if (dBuyBtn) dBuyBtn.textContent = `🔥雙買 (${dBuyCount})`;
    if (dSellBtn) dSellBtn.textContent = `❄️雙賣 (${dSellCount})`;
}

// OI Info Accordion Toggle
function toggleOiInfo() {
    const btn = document.getElementById('oi-info-toggle-btn');
    const body = document.getElementById('oi-info-body');
    const isOpen = btn.getAttribute('aria-expanded') === 'true';
    btn.setAttribute('aria-expanded', !isOpen);
    body.classList.toggle('open', !isOpen);
}

// Bootstrap
window.addEventListener('DOMContentLoaded', initApp);
