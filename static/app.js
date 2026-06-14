// State Variables
let socket;
let chart;
let candleSeries;
let lastCandle = null;
let currentSymbol = 'EURUSD';
let currentTimeframe = 'H4';

// Initialize on Load
document.addEventListener('DOMContentLoaded', () => {
    initChart();
    connectSocket();
    fetchAccountStatus();
    fetchChartData();
    fetchTrades();
    fetchStats();
    fetchBotStatus();
    fetchLearningNotes();
    setupEventListeners();
});

// 1. Initialize TradingView Chart
function initChart() {
    const chartContainer = document.getElementById('price-chart');
    
    chart = LightweightCharts.createChart(chartContainer, {
        width: chartContainer.clientWidth,
        height: 380,
        layout: {
            background: { type: LightweightCharts.ColorType.Solid, color: '#131722' },
            textColor: '#d1d4dc',
            fontSize: 11,
            fontFamily: "'Inter', sans-serif"
        },
        grid: {
            vertLines: { color: 'rgba(43, 49, 67, 0.4)' },
            horzLines: { color: 'rgba(43, 49, 67, 0.4)' },
        },
        rightPriceScale: {
            borderColor: 'rgba(43, 49, 67, 0.6)',
            alignLabels: true
        },
        timeScale: {
            borderColor: 'rgba(43, 49, 67, 0.6)',
            timeVisible: true,
            secondsVisible: false,
        },
        crosshair: {
            mode: LightweightCharts.CrosshairMode.Normal,
        }
    });

    candleSeries = chart.addSeries(LightweightCharts.CandlestickSeries, {
        upColor: '#26a69a',
        downColor: '#ef5350',
        borderDownColor: '#ef5350',
        borderUpColor: '#26a69a',
        wickDownColor: '#ef5350',
        wickUpColor: '#26a69a',
    });

    // Resize observer
    window.addEventListener('resize', () => {
        chart.resize(chartContainer.clientWidth, 380);
    });
}

// 2. Setup WebSocket Connection
function connectSocket() {
    socket = io();

    socket.on('connect', () => {
        appendLog('🟢 Connected to server backend websocket.', 'info');
    });

    socket.on('disconnect', () => {
        appendLog('🔴 Disconnected from server backend websocket.', 'error');
    });

    // Real-time Bot Logs
    socket.on('bot_log', (data) => {
        appendLog(data.message, 'info');
    });

    // Real-time Account Updates
    socket.on('account_update', (data) => {
        updateAccountUI(data);
    });

    // Real-time Price Updates (Updates the last bar)
    socket.on('price_update', (data) => {
        if (data.symbol === currentSymbol) {
            updateRealtimePrice(data);
        }
    });

    // Real-time AI Decisions
    socket.on('ai_decision', (data) => {
        updateDecisionUI(data);
    });

    // Real-time Trade Updates (Triggers reload)
    socket.on('trade_update', (data) => {
        fetchTrades();
        fetchStats();
        fetchAccountStatus();
        appendLog(`🔔 Trade Event: Order ${data.ticket_id} is ${data.status}.`, 'info');
    });

    // Real-time Learning Updates
    socket.on('learning_update', (data) => {
        updateLearningUI(data.notes);
    });
}

// 3. API Fetch Functions
async function fetchAccountStatus() {
    try {
        const res = await fetch('/api/mt5/status');
        const data = await res.json();
        updateAccountUI(data);
    } catch (err) {
        console.error('Error fetching account status:', err);
    }
}

async function fetchChartData() {
    try {
        const res = await fetch(`/api/chart/data?symbol=${currentSymbol}&timeframe=${currentTimeframe}`);
        const data = await res.json();
        if (data.length > 0) {
            candleSeries.setData(data);
            lastCandle = { ...data[data.length - 1] };
            chart.timeScale().fitContent();
        } else {
            candleSeries.setData([]);
            lastCandle = null;
        }
    } catch (err) {
        console.error('Error fetching chart data:', err);
    }
}

async function fetchTrades() {
    try {
        const res = await fetch('/api/trades');
        const data = await res.json();
        updateTradeTable(data);
    } catch (err) {
        console.error('Error fetching trades:', err);
    }
}

async function fetchStats() {
    try {
        const res = await fetch('/api/stats');
        const data = await res.json();
        updateStatsUI(data);
    } catch (err) {
        console.error('Error fetching stats:', err);
    }
}

async function fetchBotStatus() {
    try {
        const res = await fetch('/api/bot/status');
        const data = await res.json();
        updateBotStatusUI(data.running);
        
        // Update symbol & timeframe dropdowns to match running state
        document.getElementById('trading-symbol').value = data.symbol;
        document.getElementById('trading-timeframe').value = data.timeframe;
        currentSymbol = data.symbol;
        currentTimeframe = data.timeframe;
        
        document.getElementById('chart-symbol-badge').textContent = currentSymbol;
        document.getElementById('chart-tf-badge').textContent = currentTimeframe;
    } catch (err) {
        console.error('Error fetching bot status:', err);
    }
}

async function fetchLearningNotes() {
    try {
        const res = await fetch('/api/learning/notes');
        const data = await res.json();
        updateLearningUI(data.notes, data.timestamp);
    } catch (err) {
        console.error('Error fetching learning notes:', err);
    }
}

// 4. DOM Update Helpers
function updateAccountUI(data) {
    if (data.connected) {
        document.getElementById('acc-login').textContent = data.login;
        document.getElementById('acc-balance').textContent = `$${data.balance.toFixed(2)}`;
        document.getElementById('acc-equity').textContent = `$${data.equity.toFixed(2)}`;
        document.getElementById('acc-margin').textContent = `$${data.margin_free.toFixed(2)}`;
        document.getElementById('acc-server').textContent = data.server;
    } else {
        document.getElementById('acc-login').textContent = 'Offline';
        document.getElementById('acc-balance').textContent = '$0.00';
        document.getElementById('acc-equity').textContent = '$0.00';
        document.getElementById('acc-margin').textContent = '$0.00';
        document.getElementById('acc-server').textContent = 'Disconnected';
    }
}

function updateRealtimePrice(data) {
    if (lastCandle) {
        const price = parseFloat(data.bid);
        lastCandle.close = price;
        if (price > lastCandle.high) lastCandle.high = price;
        if (price < lastCandle.low) lastCandle.low = price;
        candleSeries.update(lastCandle);
    }
}

function updateDecisionUI(data) {
    const box = document.getElementById('ai-decision-box');
    const conf = document.getElementById('ai-confidence');
    const reasoning = document.getElementById('ai-reasoning-text');
    const time = document.getElementById('ai-update-time');

    box.className = 'decision-box ' + data.recommendation.toLowerCase();
    box.textContent = data.recommendation;
    conf.textContent = `${data.confidence}%`;
    reasoning.textContent = data.reasoning;
    time.textContent = `Last update: ${data.time}`;
}

function updateLearningUI(notes, timestamp) {
    const display = document.getElementById('learning-notes-display');
    const time = document.getElementById('learning-time');
    
    time.textContent = timestamp || new Date().toLocaleTimeString();

    if (!notes || notes.trim() === 'ยังไม่มีประวัติการเรียนรู้' || notes.startsWith('ยังไม่มี')) {
        display.innerHTML = `ยังไม่มีข้อมูลการเรียนรู้ เนื่องจากจำนวนออเดอร์สะสมที่ปิดแล้วยังมีไม่เพียงพอ (ต้องการอย่างน้อย 5 ออเดอร์ขึ้นไป)`;
        return;
    }

    // Format bullet points into list elements
    const lines = notes.split('\n');
    let html = '<ul>';
    lines.forEach(line => {
        const clean = line.replace(/^[-\*\d\.\s]+/, '').trim();
        if (clean) {
            html += `<li>${clean}</li>`;
        }
    });
    html += '</ul>';
    display.innerHTML = html;
}

function updateTradeTable(trades) {
    const tbody = document.getElementById('trade-history-rows');
    tbody.innerHTML = '';

    if (trades.length === 0) {
        tbody.innerHTML = `<tr><td colspan="11" class="text-center">ไม่พบประวัติการเทรดในฐานข้อมูล</td></tr>`;
        return;
    }

    trades.forEach(t => {
        const pnl = t.pnl_usd !== null ? t.pnl_usd : 0.0;
        const pnlClass = pnl > 0 ? 'text-green font-bold' : (pnl < 0 ? 'text-danger font-bold' : '');
        const pnlText = t.pnl_usd !== null ? `$${pnl.toFixed(2)}` : '-';
        
        let outcomeBadge = '-';
        if (t.outcome === 'WIN') outcomeBadge = '<span class="badge badge-win">WIN</span>';
        else if (t.outcome === 'LOSS') outcomeBadge = '<span class="badge badge-loss">LOSS</span>';
        else if (t.outcome === 'BE') outcomeBadge = '<span class="badge">BE</span>';

        const statusBadge = t.status === 'OPEN' ? '<span class="badge badge-open">OPEN</span>' : '<span class="badge badge-closed">CLOSED</span>';

        const row = document.createElement('tr');
        row.innerHTML = `
            <td>${t.ticket_id || '-'}</td>
            <td>${t.timestamp}</td>
            <td>${t.symbol}</td>
            <td><span class="badge ${t.action === 'BUY' ? 'badge-buy' : 'badge-sell'}">${t.action}</span></td>
            <td>${t.entry_price.toFixed(5)}</td>
            <td>${t.sl ? t.sl.toFixed(5) : '-'}</td>
            <td>${t.tp ? t.tp.toFixed(5) : '-'}</td>
            <td>${t.exit_price ? t.exit_price.toFixed(5) : '-'}</td>
            <td class="${pnlClass}">${pnlText}</td>
            <td>${outcomeBadge}</td>
            <td>${statusBadge}</td>
        `;
        tbody.appendChild(row);
    });
}

function updateStatsUI(data) {
    document.getElementById('stat-total-trades').textContent = data.total_trades;
    document.getElementById('stat-win-rate').textContent = `${data.win_rate}%`;
    
    const pnlEl = document.getElementById('stat-net-pnl');
    pnlEl.textContent = `$${data.total_pnl_usd.toFixed(2)}`;
    
    const iconEl = document.getElementById('stat-pnl-icon');
    if (data.total_pnl_usd > 0) {
        pnlEl.className = 'value text-green';
        iconEl.className = 'stat-icon text-green';
    } else if (data.total_pnl_usd < 0) {
        pnlEl.className = 'value text-danger';
        iconEl.className = 'stat-icon text-danger';
    } else {
        pnlEl.className = 'value';
        iconEl.className = 'stat-icon';
    }

    document.getElementById('stat-avg-rr').textContent = data.avg_rr.toFixed(2);
}

function updateBotStatusUI(running) {
    const pill = document.getElementById('bot-status-pill');
    const text = pill.querySelector('.status-text');
    const btnStart = document.getElementById('btn-start');
    const btnStop = document.getElementById('btn-stop');

    if (running) {
        pill.className = 'status-pill running';
        text.textContent = 'Running';
        btnStart.disabled = true;
        btnStop.disabled = false;
    } else {
        pill.className = 'status-pill stopped';
        text.textContent = 'Stopped';
        btnStart.disabled = false;
        btnStop.disabled = true;
    }
}

// 5. Setup Event Listeners
function setupEventListeners() {
    // Start Bot Button
    document.getElementById('btn-start').addEventListener('click', async () => {
        const symbol = document.getElementById('trading-symbol').value;
        const timeframe = document.getElementById('trading-timeframe').value;

        try {
            const res = await fetch('/api/bot/start', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ symbol, timeframe })
            });
            const data = await res.json();
            if (data.success) {
                appendLog(data.message, 'info');
                updateBotStatusUI(true);
            }
        } catch (err) {
            console.error('Error starting bot:', err);
        }
    });

    // Stop Bot Button
    document.getElementById('btn-stop').addEventListener('click', async () => {
        try {
            const res = await fetch('/api/bot/stop', { method: 'POST' });
            const data = await res.json();
            if (data.success) {
                appendLog(data.message, 'info');
                updateBotStatusUI(false);
            }
        } catch (err) {
            console.error('Error stopping bot:', err);
        }
    });

    // Analyze Now Button
    document.getElementById('btn-analyze').addEventListener('click', async () => {
        try {
            const res = await fetch('/api/bot/analyze-now', { method: 'POST' });
            const data = await res.json();
            appendLog(data.message, 'info');
        } catch (err) {
            console.error('Error manually analyzing:', err);
        }
    });

    // Connect MT5 Form Submit
    document.getElementById('login-form').addEventListener('submit', async (e) => {
        e.preventDefault();
        const server = document.getElementById('mt5-server').value;
        const login = document.getElementById('mt5-login').value;
        const password = document.getElementById('mt5-password').value;

        const btnSubmit = document.getElementById('btn-login-submit');
        btnSubmit.disabled = true;
        btnSubmit.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Connecting...';

        try {
            const res = await fetch('/api/mt5/login', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ server, login, password })
            });
            const data = await res.json();
            
            appendLog(data.message, data.success ? 'info' : 'error');
            
            if (data.success) {
                updateAccountUI(data.account);
            }
        } catch (err) {
            console.error('Error logging in:', err);
            appendLog('❌ Error connecting to MT5 endpoint.', 'error');
        } finally {
            btnSubmit.disabled = false;
            btnSubmit.innerHTML = '<i class="fa-solid fa-link"></i> Connect Terminal';
        }
    });

    // Manual Force Learning
    document.getElementById('btn-learn-generate').addEventListener('click', async () => {
        try {
            const res = await fetch('/api/learning/generate', { method: 'POST' });
            const data = await res.json();
            appendLog(data.message, data.success ? 'info' : 'warning');
        } catch (err) {
            console.error('Error forcing learning:', err);
        }
    });

    // Handle Symbol Change
    document.getElementById('trading-symbol').addEventListener('change', (e) => {
        currentSymbol = e.target.value;
        document.getElementById('chart-symbol-badge').textContent = currentSymbol;
        fetchChartData();
    });

    // Handle Timeframe Change
    document.getElementById('trading-timeframe').addEventListener('change', (e) => {
        currentTimeframe = e.target.value;
        document.getElementById('chart-tf-badge').textContent = currentTimeframe;
        fetchChartData();
    });

    // Clear Logs Button
    document.getElementById('btn-clear-logs').addEventListener('click', () => {
        document.getElementById('log-console').innerHTML = '';
    });
}

// 6. Log Console Helper
function appendLog(message, type = 'info') {
    const console = document.getElementById('log-console');
    const row = document.createElement('div');
    row.className = `log-row ${type}`;
    row.textContent = message;
    console.appendChild(row);
    console.scrollTop = console.scrollHeight;
}
