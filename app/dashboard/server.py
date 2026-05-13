from fastapi import FastAPI, WebSocket, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
import asyncio
from datetime import datetime
from typing import List
import threading
import uvicorn

from app.database.db_manager import DatabaseManager
from app.nbu.limits import NBULimitManager

app = FastAPI(title="P2P Arbitrage Dashboard", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

db = DatabaseManager()
nbu = NBULimitManager()


# WebSocket менеджер
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except:
                pass


manager = ConnectionManager()

# HTML сторінка з усіма функціями
HTML_PAGE = """
<!DOCTYPE html>
<html lang="uk">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>P2P Arbitrage Dashboard | Bybit + Monobank</title>
    <script src="https://cdn.plot.ly/plotly-3.0.1.min.js" charset="utf-8"></script>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }

        .container {
            max-width: 1600px;
            margin: 0 auto;
        }

        .header {
            background: white;
            border-radius: 15px;
            padding: 20px 30px;
            margin-bottom: 25px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
            display: flex;
            justify-content: space-between;
            align-items: center;
            flex-wrap: wrap;
            gap: 15px;
        }

        .header h1 {
            color: #333;
            font-size: 28px;
        }

        .header h1 span {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
        }

        .status {
            display: flex;
            align-items: center;
            gap: 10px;
        }

        .status-dot {
            width: 10px;
            height: 10px;
            background: #4caf50;
            border-radius: 50%;
            animation: pulse 2s infinite;
        }

        @keyframes pulse {
            0% { opacity: 1; transform: scale(1); }
            50% { opacity: 0.5; transform: scale(1.2); }
            100% { opacity: 1; transform: scale(1); }
        }

        .refresh-btn {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border: none;
            padding: 8px 16px;
            border-radius: 8px;
            cursor: pointer;
            font-size: 14px;
            margin-left: 10px;
        }

        .reset-btn {
            background: #f44336;
            color: white;
            border: none;
            padding: 8px 16px;
            border-radius: 8px;
            cursor: pointer;
            font-size: 14px;
            margin-left: 10px;
        }

        .reset-btn:hover {
            background: #d32f2f;
        }

        .refresh-btn:hover, .reset-btn:hover {
            opacity: 0.9;
        }
        
        .heatmap-controls {
            margin-bottom: 15px;
        }
        
        .heatmap-controls select {
            padding: 5px 10px;
            border-radius: 5px;
            border: 1px solid #ddd;
            background: white;
            cursor: pointer;
            margin-left: 10px;
        }
        
        .legend-gradient {
            display: inline-block;
            width: 200px;
            height: 20px;
            margin: 0 10px;
            background: linear-gradient(90deg, #90be6d, #f9c74f, #f9844a, #f44336);
            border-radius: 10px;
        }
        
        .heatmap-legend {
            display: flex;
            align-items: center;
            justify-content: center;
            margin-top: 15px;
            font-size: 12px;
            color: #666;
        }

        #last-update {
            color: #666;
            font-size: 12px;
            margin-left: 10px;
        }

        .stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }

        .stat-card {
            background: white;
            border-radius: 15px;
            padding: 25px;
            text-align: center;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
            transition: transform 0.3s;
        }

        .stat-card:hover {
            transform: translateY(-5px);
        }

        .stat-title {
            color: #666;
            font-size: 14px;
            text-transform: uppercase;
            letter-spacing: 1px;
            margin-bottom: 10px;
        }

        .stat-value {
            font-size: 32px;
            font-weight: bold;
            color: #333;
            margin-bottom: 5px;
        }

        .stat-unit {
            color: #999;
            font-size: 12px;
        }

        .progress-bar {
            background: #eee;
            border-radius: 10px;
            height: 10px;
            margin-top: 10px;
            overflow: hidden;
        }

        .progress-fill {
            background: linear-gradient(90deg, #4caf50, #ff9800, #f44336);
            height: 100%;
            border-radius: 10px;
            transition: width 0.3s;
        }

        .warning-text {
            color: #f44336;
            font-size: 12px;
            margin-top: 8px;
        }

        .market-info {
            background: white;
            border-radius: 15px;
            padding: 20px;
            margin-bottom: 20px;
            display: flex;
            justify-content: space-around;
            align-items: center;
            flex-wrap: wrap;
            gap: 20px;
        }

        .price-item {
            text-align: center;
        }

        .price-label {
            font-size: 12px;
            color: #666;
            margin-bottom: 5px;
        }

        .price-value {
            font-size: 28px;
            font-weight: bold;
        }

        .price-value.buy {
            color: #4caf50;
        }

        .price-value.sell {
            color: #f44336;
        }

        .spread-value {
            font-size: 24px;
            font-weight: bold;
            color: #ff9800;
        }

        .charts-container {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(500px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }

        .chart-card {
            background: white;
            border-radius: 15px;
            padding: 20px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        }

        .chart-card h3 {
            color: #333;
            margin-bottom: 20px;
            font-size: 18px;
        }

        .opportunities-section {
            background: white;
            border-radius: 15px;
            padding: 20px;
            margin-bottom: 20px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        }

        .opportunities-section h2 {
            color: #333;
            margin-bottom: 20px;
            font-size: 20px;
        }

        .table-container {
            overflow-x: auto;
        }

        table {
            width: 100%;
            border-collapse: collapse;
        }

        th {
            background: #f5f5f5;
            padding: 12px;
            text-align: left;
            font-weight: 600;
            color: #666;
            font-size: 14px;
        }

        td {
            padding: 12px;
            border-bottom: 1px solid #eee;
            color: #333;
        }

        tr:hover {
            background: #f9f9f9;
        }

        .profit-positive {
            color: #4caf50;
            font-weight: bold;
        }

        .loading {
            text-align: center;
            color: #999;
            padding: 40px;
        }

        .btn-success {
            background: #4caf50;
            color: white;
            border: none;
            padding: 6px 12px;
            border-radius: 6px;
            cursor: pointer;
            font-size: 12px;
            margin-right: 5px;
        }

        .btn-danger {
            background: #f44336;
            color: white;
            border: none;
            padding: 6px 12px;
            border-radius: 6px;
            cursor: pointer;
            font-size: 12px;
            margin-right: 5px;
        }

        .btn-warning {
            background: #ff9800;
            color: white;
            border: none;
            padding: 6px 12px;
            border-radius: 6px;
            cursor: pointer;
            font-size: 12px;
        }

        .btn-success:hover, .btn-danger:hover, .btn-warning:hover {
            opacity: 0.8;
        }

        .status-badge {
            display: inline-block;
            padding: 4px 10px;
            border-radius: 12px;
            font-size: 11px;
            font-weight: bold;
        }

        .status-pending {
            background: #ff9800;
            color: white;
        }

        .status-completed {
            background: #4caf50;
            color: white;
        }

        .status-cancelled {
            background: #999;
            color: white;
        }

        .status-waiting {
            background: #2196f3;
            color: white;
        }

        .log-entry {
            font-family: monospace;
            font-size: 12px;
            padding: 8px;
            border-bottom: 1px solid #eee;
        }

        .log-info { color: #2196f3; }
        .log-success { color: #4caf50; }
        .log-warning { color: #ff9800; }
        .log-error { color: #f44336; }

        @media (max-width: 768px) {
            .charts-container {
                grid-template-columns: 1fr;
            }
            .stats-grid {
                grid-template-columns: repeat(2, 1fr);
            }
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🚀 P2P <span>Arbitrage Scanner</span></h1>
            <div class="status">
                <div class="status-dot"></div>
                <span id="status-text">Активний</span>
                <button class="refresh-btn" onclick="refreshData()">🔄 Оновити</button>
                <button class="reset-btn" onclick="resetDatabase()">🗑️ Скинути БД</button>
                <button class="reset-btn" onclick="resetNBU()" style="background: #ff9800;">🏦 Скинути ліміт НБУ</button>
                <span id="last-update"></span>
            </div>
        </div>

        <div class="market-info" id="market-info">
            <div class="price-item">
                <div class="price-label">💰 Найкраща ціна КУПІВЛІ USDT</div>
                <div class="price-value buy" id="best-buy">---</div>
                <div class="price-label">UAH</div>
            </div>
            <div class="price-item">
                <div class="price-label">💵 Найкраща ціна ПРОДАЖУ USDT</div>
                <div class="price-value sell" id="best-sell">---</div>
                <div class="price-label">UAH</div>
            </div>
            <div class="price-item">
                <div class="price-label">📈 Поточний спред</div>
                <div class="spread-value" id="current-spread">---</div>
                <div class="price-label">%</div>
            </div>
        </div>

        <div class="stats-grid">
            <div class="stat-card">
                <div class="stat-title">💰 Загальний прибуток</div>
                <div class="stat-value" id="total-profit">0</div>
                <div class="stat-unit">UAH (за 24 год)</div>
            </div>
            <div class="stat-card">
                <div class="stat-title">📈 Середній ROI</div>
                <div class="stat-value" id="avg-roi">0</div>
                <div class="stat-unit">%</div>
            </div>
            <div class="stat-card">
                <div class="stat-title">🎯 Знайдено угод</div>
                <div class="stat-value" id="total-opps">0</div>
                <div class="stat-unit">за 24 год</div>
            </div>
            <div class="stat-card">
                <div class="stat-title">💎 Найкращий прибуток</div>
                <div class="stat-value" id="max-profit">0</div>
                <div class="stat-unit">UAH</div>
            </div>
            <div class="stat-card">
                <div class="stat-title">🏦 Ліміт НБУ</div>
                <div class="stat-value" id="nbu-used">0</div>
                <div class="stat-unit">грн використано з <span id="nbu-total">120000</span></div>
                <div class="progress-bar">
                    <div class="progress-fill" id="nbu-progress" style="width: 0%;"></div>
                </div>
                <div id="nbu-percent" style="font-size: 12px; margin-top: 5px;">0%</div>
                <div id="nbu-warning" class="warning-text" style="display: none;">⚠️ Ліміт майже вичерпано!</div>
            </div>
        </div>

        <div class="charts-container">
            <div class="chart-card">
                <h3>📊 Історія спредів (останні 50 угод)</h3>
                <div id="spread-chart" style="height: 400px;"></div>
            </div>
            <div class="chart-card">
                <h3>💰 Прибуток за угодами</h3>
                <div id="profit-chart" style="height: 400px;"></div>
            </div>
            <div class="chart-card">
                <h3>📊 Теплова карта прибутку (по годинах та днях)</h3>
                <div class="heatmap-controls">
                    <label>Період: 
                        <select id="heatmap-days" onchange="loadHeatmap()">
                            <option value="7">7 днів</option>
                            <option value="14">14 днів</option>
                            <option value="30" selected>30 днів</option>
                            <option value="60">60 днів</option>
                        </select>
                    </label>
                </div>
                <div id="heatmap-chart" style="height: 400px; margin-top: 10px;"></div>
                <div class="heatmap-legend">
                    <span>💰 Середній прибуток (грн):</span>
                    <div class="legend-gradient"></div>
                    <span>Низький → Високий</span>
                </div>
            </div>
        </div>
        
        

        <div class="opportunities-section">
            <h2>🔔 Останні можливості (очікують підтвердження)</h2>
            <div class="table-container">
                <table id="opportunities-table">
                    <thead>
                        <tr>
                            <th>⏰ Час</th>
                            <th>💵 Купівля</th>
                            <th>💰 Продаж</th>
                            <th>📈 Спред</th>
                            <th>💸 Сума купівлі</th>
                            <th>💵 Сума продажу</th>
                            <th>💚 Прибуток</th>
                            <th>📊 ROI</th>
                            <th>Дія</th>
                        </tr>
                    </thead>
                    <tbody id="opportunities-body">
                        <tr><td colspan="9" class="loading">🔄 Завантаження......</td></tr>
                    </tbody>
                </table>
            </div>
        </div>

        <div class="opportunities-section">
            <h2>✅ Виконані угоди</h2>
            <div class="table-container">
                <table id="completed-deals-table">
                    <thead>
                        <tr><th>ID</th><th>Час</th><th>Сума (UAH)</th><th>USDT</th><th>Прибуток</th><th>Продавець</th><th>Покупець</th><th>Статус</th></table>
                    </thead>
                    <tbody id="completed-deals-body">
                        <tr><td colspan="8" class="loading">Завантаження...</td></tr>
                    </tbody>
                </table>
            </div>
        </div>

        <div class="opportunities-section">
            <h2>📋 Логи подій</h2>
            <div class="table-container">
                <table id="logs-table">
                    <thead>
                        <tr><th>⏰ Час</th><th>📊 Рівень</th><th>📝 Повідомлення</th></tr>
                    </thead>
                    <tbody id="logs-body">
                        <tr><td colspan="3" class="loading">Завантаження...</td></tr>
                    </tbody>
                </table>
            </div>
        </div>
    </div>

    <script>
        let spreadChart = null, profitChart = null, ws = null;
        
        
        function formatNumber(num, d=2) { return num ? num.toLocaleString('uk-UA', {minFractionDigits:d, maxFractionDigits:d}) : '---'; }
        function formatProfit(num) { return num ? (num >= 0 ? `+${formatNumber(num)}` : `-${formatNumber(Math.abs(num))}`) : '---'; }

        async function resetNBU() {
        if (!confirm('🏦 Скинути ліміт НБУ?\\nВсі використані кошти будуть обнулені.')) return;
        
                try {
                    const resp = await fetch('/api/reset-nbu-limit', { method: 'POST' });
                    const data = await resp.json();
                    if (data.success) {
                        alert('✅ Ліміт НБУ скинуто!');
                        loadNBULimit();
                    } else {
                        alert('❌ Помилка: ' + data.error);
                    }
                } catch(e) { console.error(e); }
            }

        async function resetDatabase() {
            if (!confirm('⚠️ ВИ ДІЙСНО ХОЧЕТЕ СКИНУТИ ВСЮ БАЗУ ДАНИХ?\\nЦю дію НЕ МОЖНА скасувати!')) return;
            if (!confirm('ЩЕ РАЗ ПІДТВЕРДІТЬ: ВСІ ДАНІ БУДУТЬ ВИДАЛЕНІ!')) return;

            try {
                const resp = await fetch('/api/reset-database', { method: 'POST' });
                const data = await resp.json();
                if (data.success) {
                    alert('✅ Базу даних скинуто!');
                    location.reload();
                } else {
                    alert('❌ Помилка: ' + data.error);
                }
            } catch(e) { console.error(e); }
        }
        
        let heatmapChart = null;

async function loadHeatmap() {
    const days = document.getElementById('heatmap-days').value;
    try {
        const resp = await fetch(`/api/heatmap?days=${days}`);
        const data = await resp.json();
        
        const colorscale = [
            [0, '#90be6d'],      // зелений - низький прибуток
            [0.33, '#f9c74f'],   // жовтий - середній
            [0.66, '#f9844a'],   // оранжевий - високий
            [1, '#f44336']       // червоний - дуже високий
        ];
        
        const trace = {
            z: data.data,
            x: data.hours,
            y: data.days,
            type: 'heatmap',
            colorscale: colorscale,
            showscale: true,
            text: data.data.map(row => row.map(val => val > 0 ? `${val.toFixed(0)} грн` : '')),
            texttemplate: '%{text}',
            textfont: { size: 10 },
            hovertemplate: '<b>%{y}</b> %{x}:00<br>' +
                          'Середній прибуток: <b>%{z:.0f} грн</b><br>' +
                          '<extra></extra>'
        };
        
        const layout = {
            title: {
                text: `Середній прибуток по годинах (останні ${days} днів)`,
                font: { size: 14 }
            },
            xaxis: {
                title: 'Година дня',
                tickmode: 'linear',
                tick0: 0,
                dtick: 2,
                tickangle: 0
            },
            yaxis: {
                title: 'День тижня',
                autorange: 'reversed'
            },
            height: 350,
            margin: { l: 60, r: 40, t: 50, b: 40 }
        };
        
        if (heatmapChart) {
            Plotly.react('heatmap-chart', [trace], layout);
        } else {
            heatmapChart = Plotly.newPlot('heatmap-chart', [trace], layout);
        }
        
        // Додаємо додаткову інформацію
        updateHeatmapStats(data);
        
    } catch(e) { console.error(e); }
}

function updateHeatmapStats(data) {
    // Знаходимо найкращий час для торгівлі
    let bestProfit = 0;
    let bestDay = '', bestHour = 0;
    
    for (let d = 0; d < data.days.length; d++) {
        for (let h = 0; h < data.hours.length; h++) {
            if (data.data[d][h] > bestProfit) {
                bestProfit = data.data[d][h];
                bestDay = data.days[d];
                bestHour = h;
            }
        }
    }
    
    // Додаємо підказку на сторінку
    let statsDiv = document.getElementById('heatmap-stats');
    if (!statsDiv) {
        statsDiv = document.createElement('div');
        statsDiv.id = 'heatmap-stats';
        statsDiv.style.cssText = 'margin-top: 15px; padding: 10px; background: #f5f5f5; border-radius: 10px; text-align: center;';
        document.querySelector('.heatmap-legend').after(statsDiv);
    }
    
    statsDiv.innerHTML = `
        <strong>📈 Найкращий час для арбітражу:</strong> 
        ${bestDay} ${bestHour}:00 (середній прибуток ${bestProfit.toFixed(0)} грн за угоду)
    `;
}

        async function confirmOpportunity(id, buyAmount, sellAmount, profit, buyMerchant, sellMerchant) {
            if (!confirm(`Підтвердити виконання можливості #${id}?\\nПрибуток: +${profit} UAH\\nВід: ${buyMerchant} → ${sellMerchant}`)) return;

            try {
                const resp = await fetch(`/api/opportunities/${id}/confirm`, { 
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ buy_amount: buyAmount, sell_amount: sellAmount })
                });
                const data = await resp.json();
                if (data.success) {
                    alert('✅ Можливість підтверджено! Ліміт НБУ зарезервовано.');
                    refreshData();
                } else {
                    alert('❌ Помилка: ' + data.error);
                }
            } catch(e) { console.error(e); }
        }

        async function rejectOpportunity(id) {
            if (!confirm(`Відхилити можливість #${id}?`)) return;

            try {
                const resp = await fetch(`/api/opportunities/${id}/reject`, { method: 'POST' });
                const data = await resp.json();
                if (data.success) {
                    alert('❌ Можливість відхилено');
                    refreshData();
                } else {
                    alert('❌ Помилка: ' + data.error);
                }
            } catch(e) { console.error(e); }
        }

        async function loadNBULimit() {
            try {
                const resp = await fetch('/api/nbu/limit');
                const data = await resp.json();
                document.getElementById('nbu-used').textContent = formatNumber(data.used_amount, 0);
                document.getElementById('nbu-total').textContent = formatNumber(data.total_limit, 0);
                const percent = data.usage_percent;
                document.getElementById('nbu-progress').style.width = `${percent}%`;
                document.getElementById('nbu-percent').textContent = `${percent.toFixed(1)}%`;
                if (percent > 85) {
                    document.getElementById('nbu-warning').style.display = 'block';
                } else {
                    document.getElementById('nbu-warning').style.display = 'none';
                }
            } catch(e) { console.error(e); }
        }

        async function loadCompletedDeals() {
            try {
                const resp = await fetch('/api/completed-deals');
                const deals = await resp.json();
                const tbody = document.getElementById('completed-deals-body');
                if (!deals || deals.length === 0) {
                    tbody.innerHTML = '<tr><td colspan="8" class="loading">📭 Немає виконаних угод</td></tr>';
                    return;
                }
                tbody.innerHTML = deals.map(d => {
                    let statusClass = d.status === 'completed' ? 'status-completed' : 'status-cancelled';
                    let statusText = d.status === 'completed' ? 'Виконано' : 'Скасовано';
                    return `<tr>
                        <td>${d.id}</td>
                        <td>${new Date(d.timestamp).toLocaleString('uk-UA')}</td>
                        <td>${formatNumber(d.amount_uah, 0)}</td>
                        <td>${formatNumber(d.amount_usdt, 0)}</td>
                        <td class="profit-positive">${formatProfit(d.profit)}</td>
                        <td>${d.buy_merchant}</td>
                        <td>${d.sell_merchant}</td>
                        <td><span class="status-badge ${statusClass}">${statusText}</span></td>
                    </tr>`;
                }).join('');
            } catch(e) { console.error(e); }
        }

        async function loadLogs() {
    try {
        const resp = await fetch('/api/logs');
        const logs = await resp.json();
        const tbody = document.getElementById('logs-body');
        if (!logs || logs.length === 0) {
            tbody.innerHTML = '<tr><td colspan="3" class="loading">📭 Немає логів</td></tr>';
            return;
        }
        tbody.innerHTML = logs.map(log => {
            let levelClass = `log-${log.level.toLowerCase()}`;
            return `<tr>
                <td>${new Date(log.timestamp).toLocaleString('uk-UA')}</td>
                <td class="${levelClass}">${log.level.toUpperCase()}</td>
                <td>${log.message}</td>
            </tr>`;
        }).join('');
    } catch(e) { console.error(e); }
}

        function updateTable(opps) {
            const tbody = document.getElementById('opportunities-body');
            if (!opps || opps.length === 0) { 
                tbody.innerHTML = '<tr><td colspan="9" class="loading">📭 Немає можливостей, що очікують підтвердження</td></tr>'; 
                return; 
            }
            tbody.innerHTML = opps.map(o => {
                const buyAmount = o.usdt_amount ? o.usdt_amount * o.buy_price : 0;
                const sellAmount = o.usdt_amount ? o.usdt_amount * o.sell_price : 0;
                return `<tr>
                    <td>${new Date(o.timestamp).toLocaleString('uk-UA')}</td>
                    <td>${formatNumber(o.buy_price)} UAH</td>
                    <td>${formatNumber(o.sell_price)} UAH</td>
                    <td>${formatNumber(o.spread,2)}%</td>
                    <td class="profit-positive">${formatNumber(buyAmount, 0)} грн</td>
                    <td class="profit-positive">${formatNumber(sellAmount, 0)} грн</td>
                    <td class="profit-positive">${formatProfit(o.profit)} UAH</td>
                    <td>${formatNumber(o.roi,2)}%</td>
                    <td>
                        <button class="btn-success" onclick="confirmOpportunity(${o.id}, ${buyAmount}, ${sellAmount}, ${o.profit}, '${o.buy_merchant}', '${o.sell_merchant}')">✅ Підтвердити</button>
                        <button class="btn-danger" onclick="rejectOpportunity(${o.id})">❌ Відхилити</button>
                    </td>
                </tr>`;
            }).join('');
        }

        function updateCharts(opps) {
            if (!opps || opps.length === 0) return;
            const rev = [...opps].reverse(), times = rev.map(o => new Date(o.timestamp).toLocaleString('uk-UA')), spreads = rev.map(o => o.spread), profits = rev.map(o => o.profit);
            const spreadTrace = {x: times, y: spreads, type: 'scatter', mode: 'lines+markers', line: {color: '#ff9800', width: 2}};
            if (spreadChart) Plotly.react('spread-chart', [spreadTrace], {title:'', xaxis:{title:'Час'}, yaxis:{title:'Спред (%)'}});
            else spreadChart = Plotly.newPlot('spread-chart', [spreadTrace], {title:'', xaxis:{title:'Час'}, yaxis:{title:'Спред (%)'}});
            const profitTrace = {x: times, y: profits, type: 'bar', marker: {color: profits.map(p => p >= 0 ? '#4caf50' : '#f44336')}};
            if (profitChart) Plotly.react('profit-chart', [profitTrace], {title:'', xaxis:{title:'Час'}, yaxis:{title:'Прибуток (UAH)'}});
            else profitChart = Plotly.newPlot('profit-chart', [profitTrace], {title:'', xaxis:{title:'Час'}, yaxis:{title:'Прибуток (UAH)'}});
        }

        function updateStats(opps) {
            if (!opps || opps.length === 0) return;
            const total = opps.reduce((s,o) => s + o.profit, 0), avg = total / opps.length, max = Math.max(...opps.map(o => o.profit));
            document.getElementById('total-profit').textContent = formatNumber(total);
            document.getElementById('avg-roi').textContent = formatNumber(avg, 2);
            document.getElementById('total-opps').textContent = opps.length;
            document.getElementById('max-profit').textContent = formatNumber(max);
        }

        function updateMarket(opps) {
            if (!opps || opps.length === 0) return;
            const latest = opps[0];
            if (latest) {
                document.getElementById('best-buy').textContent = formatNumber(latest.buy_price);
                document.getElementById('best-sell').textContent = formatNumber(latest.sell_price);
                document.getElementById('current-spread').textContent = formatNumber(latest.spread, 2);
            }
        }

        async function fetchData() {
            try {
                const resp = await fetch('/api/opportunities/pending');
                const data = await resp.json();
                updateTable(data);
                updateCharts(data);
                updateStats(data);
                updateMarket(data);
                document.getElementById('last-update').textContent = `Оновлено: ${new Date().toLocaleTimeString('uk-UA')}`;
            } catch(e) { console.error(e); }
        }

        function refreshData() { fetchData(); loadNBULimit(); loadCompletedDeals(); loadLogs(); loadHeatmap();}

        function connectWebSocket() {
            const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
            ws = new WebSocket(`${protocol}//${location.host}/ws`);
            ws.onopen = () => { console.log('WebSocket connected'); document.getElementById('status-text').textContent = 'Live режим'; };
            ws.onmessage = (e) => { const data = JSON.parse(e.data); if(data.type === 'update') { updateTable(data.opportunities); updateCharts(data.opportunities); updateStats(data.opportunities); updateMarket(data.opportunities); loadNBULimit(); loadCompletedDeals(); loadLogs(); loadHeatmap();} };
            ws.onclose = () => { console.log('WebSocket disconnected'); setTimeout(connectWebSocket, 5000); };
        }

        fetchData();
        loadNBULimit();
        loadCompletedDeals();
        loadLogs();
        loadHeatmap();  
        
        connectWebSocket();
        setInterval(() => { if(!ws || ws.readyState !== WebSocket.OPEN) { fetchData(); loadNBULimit(); loadCompletedDeals(); loadLogs(); } }, 30000);
    </script>
</body>
</html>
"""


@app.get("/", response_class=HTMLResponse)
async def get_dashboard():
    return HTMLResponse(content=HTML_PAGE)


@app.get("/api/opportunities/pending")
async def get_pending_opportunities():
    """Отримати можливості, що очікують підтвердження (status='pending')"""
    from app.database.models import Opportunity
    from sqlalchemy import create_engine, desc
    from sqlalchemy.orm import sessionmaker
    from config.settings import settings

    engine = create_engine(settings.DATABASE_URL)
    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        opportunities = session.query(Opportunity).filter(
            Opportunity.alert_sent == False
        ).order_by(desc(Opportunity.timestamp)).limit(100).all()
        return [
            {
                "id": o.id,
                "timestamp": o.timestamp.isoformat(),
                "spread": o.spread_percent,
                "profit": o.net_profit,
                "roi": o.roi_percent,
                "buy_price": o.buy_price,
                "sell_price": o.sell_price,
                "usdt_amount": o.usdt_amount,
                "buy_merchant": getattr(o, 'buy_merchant', 'Unknown'),
                "sell_merchant": getattr(o, 'sell_merchant', 'Unknown')
            }
            for o in opportunities
        ]
    finally:
        session.close()


@app.post("/api/opportunities/{opp_id}/confirm")
async def confirm_opportunity(opp_id: int):
    """Підтвердити можливість - створити транзакцію та зарезервувати ліміт НБУ"""
    from app.database.models import Opportunity
    from app.nbu.limits import Transaction, NBULimit
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from config.settings import settings
    from datetime import datetime

    engine = create_engine(settings.DATABASE_URL)
    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        opp = session.query(Opportunity).filter(Opportunity.id == opp_id).first()
        if not opp:
            return {"success": False, "error": "Opportunity not found"}

        if opp.alert_sent:
            return {"success": False, "error": "Opportunity already processed"}

        # Резервуємо ліміт НБУ
        current_month = datetime.now().strftime('%Y-%m')
        limit = session.query(NBULimit).filter(NBULimit.month == current_month).first()
        if not limit:
            limit = NBULimit(total_limit=120000, used_amount=0, month=current_month)
            session.add(limit)

        amount_uah = opp.usdt_amount * opp.buy_price
        if limit.used_amount + amount_uah > limit.total_limit:

            return {"success": False,
                    "error": f"NBU limit exceeded! Need {amount_uah:,.0f}, available {limit.total_limit - limit.used_amount:,.0f}"}

        # Створюємо транзакцію
        transaction = Transaction(
            amount_uah=amount_uah,
            amount_usdt=opp.usdt_amount,
            buy_merchant=getattr(opp, 'buy_merchant', 'Unknown'),
            sell_merchant=getattr(opp, 'sell_merchant', 'Unknown'),
            buy_price=opp.buy_price,
            sell_price=opp.sell_price,
            profit=opp.net_profit,
            status='pending'
        )
        session.add(transaction)

        # Оновлюємо ліміт
        limit.used_amount += amount_uah
        limit.updated_at = datetime.now()

        # Позначаємо можливість як опрацьовану
        opp.alert_sent = True

        session.commit()

        # Додаємо лог
        add_log(session, "SUCCESS",
                f"Opportunity #{opp_id} confirmed! Transaction #{transaction.id} created. Reserved {amount_uah:,.0f} UAH from NBU limit")

        return {"success": True, "transaction_id": transaction.id}
    except Exception as e:
        session.rollback()
        return {"success": False, "error": str(e)}
    finally:
        session.close()


@app.get("/api/best-hours")
async def get_best_hours(days: int = 30):
    """Отримати найкращі години для торгівлі"""
    data = db.get_heatmap_data(days=days)

    # Знаходимо топ-5 годин
    best_hours = []
    for d in range(7):
        for h in range(24):
            if data['data'][d][h] > 0:
                best_hours.append({
                    'day': data['days'][d],
                    'hour': h,
                    'profit': data['data'][d][h],
                    'count': data['counts'][d][h]
                })

    best_hours.sort(key=lambda x: x['profit'], reverse=True)
    return best_hours[:10]

@app.post("/api/opportunities/{opp_id}/reject")
async def reject_opportunity(opp_id: int):
    """Відхилити можливість"""
    from app.database.models import Opportunity
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from config.settings import settings

    engine = create_engine(settings.DATABASE_URL)
    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        opp = session.query(Opportunity).filter(Opportunity.id == opp_id).first()
        if not opp:
            return {"success": False, "error": "Opportunity not found"}

        opp.alert_sent = True  # Позначаємо як опрацьовану (відхилену)
        session.commit()

        add_log(session, "WARNING", f"Opportunity #{opp_id} rejected")

        return {"success": True}
    except Exception as e:
        session.rollback()
        return {"success": False, "error": str(e)}
    finally:
        session.close()


@app.get("/api/completed-deals")
async def get_completed_deals():
    """Отримати виконані угоди (транзакції)"""
    from app.nbu.limits import Transaction
    from sqlalchemy import create_engine, desc
    from sqlalchemy.orm import sessionmaker
    from config.settings import settings

    engine = create_engine(settings.DATABASE_URL)
    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        transactions = session.query(Transaction).order_by(desc(Transaction.timestamp)).limit(100).all()
        return [
            {
                "id": t.id,
                "timestamp": t.timestamp.isoformat(),
                "amount_uah": t.amount_uah,
                "amount_usdt": t.amount_usdt,
                "profit": t.profit,
                "buy_merchant": t.buy_merchant,
                "sell_merchant": t.sell_merchant,
                "status": t.status
            }
            for t in transactions
        ]
    finally:
        session.close()


@app.get("/api/logs")
async def get_logs(limit: int = 200):
    """Отримати логи з БД"""
    from app.database.models import Log
    from sqlalchemy import create_engine, desc
    from sqlalchemy.orm import sessionmaker
    from config.settings import settings

    engine = create_engine(settings.DATABASE_URL)
    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        logs = session.query(Log).order_by(desc(Log.timestamp)).limit(limit).all()
        return [
            {
                "timestamp": log.timestamp.isoformat(),
                "level": log.level,
                "message": log.message
            }
            for log in logs
        ]
    except Exception as e:
        print(f"Error getting logs: {e}")
        return []
    finally:
        session.close()


@app.post("/api/reset-nbu-limit")
async def reset_nbu_limit():
    """Скинути ліміт НБУ (обнулити використання)"""
    from app.nbu.limits import NBULimit
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from config.settings import settings
    from datetime import datetime

    try:
        engine = create_engine(settings.DATABASE_URL)
        Session = sessionmaker(bind=engine)
        session = Session()
        try:
            current_month = datetime.now().strftime('%Y-%m')
            limit = session.query(NBULimit).filter(NBULimit.month == current_month).first()

            if limit:
                limit.used_amount = 0
                limit.updated_at = datetime.now()
            else:
                limit = NBULimit(
                    total_limit=settings.NBU_MONTHLY_LIMIT,
                    used_amount=0,
                    month=current_month
                )
                session.add(limit)

            session.commit()

            # Додаємо лог
            from app.database.db_manager import DatabaseManager
            db = DatabaseManager()
            db.add_log("INFO", "NBU limit reset by user")

            return {"success": True}
        finally:
            session.close()
    except Exception as e:
        return {"success": False, "error": str(e)}

@app.post("/api/reset-database")
async def reset_database():
    """Скинути базу даних (очистити всі таблиці)"""
    from sqlalchemy import create_engine, text
    from app.database.models import Base as ModelsBase
    from app.nbu.limits import Base as NBUBase
    from config.settings import settings

    try:
        engine = create_engine(settings.DATABASE_URL)

        # Очищаємо ВСІ таблиці через SQL (швидший спосіб)
        with engine.connect() as conn:
            # Отримуємо список всіх таблиць
            if 'sqlite' in settings.DATABASE_URL:
                # Для SQLite
                conn.execute(text("DELETE FROM opportunities"))
                conn.execute(text("DELETE FROM p2p_quotes"))
                conn.execute(text("DELETE FROM logs"))
                conn.execute(text("DELETE FROM nbu_limits"))
                conn.execute(text("DELETE FROM transactions"))
                # Скидаємо автоінкремент
                conn.execute(text("DELETE FROM sqlite_sequence"))
            else:
                # Для PostgreSQL
                conn.execute(text(
                    "TRUNCATE TABLE opportunities, p2p_quotes, logs, nbu_limits, transactions RESTART IDENTITY CASCADE"))
            conn.commit()

        # Створюємо новий ліміт НБУ на поточний місяць
        from app.nbu.limits import NBULimit
        from datetime import datetime
        from sqlalchemy.orm import sessionmaker

        Session = sessionmaker(bind=engine)
        session = Session()
        try:
            current_month = datetime.now().strftime('%Y-%m')
            new_limit = NBULimit(
                total_limit=settings.NBU_MONTHLY_LIMIT,
                used_amount=0,
                month=current_month
            )
            session.add(new_limit)
            session.commit()
        finally:
            session.close()

        # Додаємо лог про скидання
        from app.database.db_manager import DatabaseManager
        db = DatabaseManager()
        db.add_log("INFO", "Database reset by user - all limits cleared")

        return {"success": True}
    except Exception as e:
        return {"success": False, "error": str(e)}


@app.get("/api/nbu/limit")
async def get_nbu_limit():
    """API для отримання ліміту НБУ"""
    return {
        "total_limit": 120000,
        "used_amount": nbu.get_used_amount(),
        "remaining": nbu.get_remaining_limit(),
        "usage_percent": nbu.get_usage_percent()
    }


def add_log(session, level: str, message: str):
    """Додати запис логу"""
    from app.database.models import Log
    log = Log(level=level, message=message)
    session.add(log)
    session.commit()

@app.get("/api/heatmap")
async def get_heatmap(days: int = 30):
    """API для отримання даних теплової карти"""
    return db.get_heatmap_data(days=days)

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket для реального часу"""
    await manager.connect(websocket)
    try:
        while True:
            from app.database.models import Opportunity
            from sqlalchemy import create_engine, desc
            from sqlalchemy.orm import sessionmaker
            from config.settings import settings

            engine = create_engine(settings.DATABASE_URL)
            Session = sessionmaker(bind=engine)
            session = Session()
            try:
                opportunities = session.query(Opportunity).filter(
                    Opportunity.alert_sent == False
                ).order_by(desc(Opportunity.timestamp)).limit(100).all()
                data = [
                    {
                        "id": o.id,
                        "timestamp": o.timestamp.isoformat(),
                        "spread": o.spread_percent,
                        "profit": o.net_profit,
                        "roi": o.roi_percent,
                        "buy_price": o.buy_price,
                        "sell_price": o.sell_price,
                        "usdt_amount": o.usdt_amount,
                        "buy_merchant": getattr(o, 'buy_merchant', 'Unknown'),
                        "sell_merchant": getattr(o, 'sell_merchant', 'Unknown')
                    }
                    for o in opportunities
                ]
                await manager.broadcast({
                    "type": "update",
                    "opportunities": data,
                    "timestamp": datetime.now().isoformat()
                })
            finally:
                session.close()
            await asyncio.sleep(5)
    except Exception as e:
        print(f"WebSocket error: {e}")
    finally:
        manager.disconnect(websocket)


def start_dashboard(host="0.0.0.0", port=5002):
    """Запуск дашборду в окремому потоці"""

    def run():
        uvicorn.run(app, host=host, port=port, log_level="warning")

    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    print(f"\n📊 Dashboard запущено на http://{host}:{port}")
    return thread