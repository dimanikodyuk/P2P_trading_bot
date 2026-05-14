from fastapi import FastAPI, WebSocket, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
import asyncio
from datetime import datetime
from typing import List
import threading
import uvicorn
import os

from app.database.db_manager import DatabaseManager
from app.nbu.limits import NBULimitManager
from config.settings import settings

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

        /* Таби */
        .tabs {
            display: flex;
            gap: 10px;
            margin-bottom: 25px;
            flex-wrap: wrap;
        }

        .tab-btn {
            background: rgba(255,255,255,0.2);
            color: white;
            border: none;
            padding: 12px 24px;
            border-radius: 10px;
            cursor: pointer;
            font-size: 16px;
            font-weight: 600;
            transition: all 0.3s;
        }

        .tab-btn.active {
            background: white;
            color: #667eea;
        }

        .tab-btn:hover {
            background: rgba(255,255,255,0.3);
        }

        .tab-content {
            display: none;
        }

        .tab-content.active {
            display: block;
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

        .opportunities-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 20px;
            flex-wrap: wrap;
            gap: 10px;
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

        .btn-save {
            background: #4caf50;
            color: white;
            border: none;
            padding: 10px 20px;
            border-radius: 8px;
            cursor: pointer;
            font-size: 14px;
            margin-top: 20px;
        }

        .btn-save:hover {
            opacity: 0.9;
        }

        .settings-form {
            background: white;
            border-radius: 15px;
            padding: 25px;
        }

        .settings-group {
            margin-bottom: 25px;
            border-bottom: 1px solid #eee;
            padding-bottom: 20px;
        }

        .settings-group h3 {
            color: #333;
            margin-bottom: 15px;
            font-size: 18px;
        }

        .setting-row {
            display: flex;
            flex-wrap: wrap;
            margin-bottom: 15px;
            align-items: flex-start;
            gap: 10px;
        }

        .setting-label {
            width: 250px;
            font-weight: 600;
            color: #333;
        }

        .setting-label small {
            display: block;
            font-weight: normal;
            font-size: 11px;
            color: #999;
            margin-top: 3px;
        }

        .setting-input {
            flex: 1;
            min-width: 200px;
        }

        .setting-input input, .setting-input select {
            width: 100%;
            padding: 8px 12px;
            border: 1px solid #ddd;
            border-radius: 6px;
            font-size: 14px;
        }

        .setting-input .current-value {
            font-size: 12px;
            color: #666;
            margin-top: 5px;
        }

        .checkbox-input {
            display: flex;
            align-items: center;
            gap: 10px;
        }

        .checkbox-input input {
            width: 20px;
            height: 20px;
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

        .controls {
            display: flex;
            justify-content: flex-end;
            margin-bottom: 15px;
            gap: 10px;
        }

        .controls select {
            padding: 5px 10px;
            border-radius: 5px;
            border: 1px solid #ddd;
            background: white;
            cursor: pointer;
        }

        @media (max-width: 768px) {
            .charts-container {
                grid-template-columns: 1fr;
            }
            .stats-grid {
                grid-template-columns: repeat(2, 1fr);
            }
            .opportunities-header {
                flex-direction: column;
                align-items: flex-start;
            }
            .setting-row {
                flex-direction: column;
            }
            .setting-label {
                width: 100%;
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
                <span id="last-update"></span>
            </div>
        </div>

        <!-- Таби -->
        <div class="tabs">
            <button class="tab-btn active" onclick="showTab('dashboard')">📊 Дашборд</button>
            <button class="tab-btn" onclick="showTab('settings')">⚙️ Налаштування</button>
        </div>

        <!-- Вкладка Дашборд -->
        <div id="dashboard-tab" class="tab-content active">
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
                        <label>Тип угод: 
                            <select id="heatmap-type" onchange="loadHeatmap()">
                                <option value="all">Всі можливості</option>
                                <option value="confirmed">Лише підтверджені</option>
                            </select>
                        </label>
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
                <div class="opportunities-header">
                    <h2>🔔 Останні можливості (очікують підтвердження)</h2>
                    <button class="btn-danger" onclick="rejectAllOpportunities()" style="padding: 8px 16px;">❌ Відхилити всі</button>
                </div>
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
                <div class="opportunities-header">
                    <h2>✅ Виконані угоди</h2>
                    <div class="controls">
                        <label>Показати: 
                            <select id="completed-limit" onchange="loadCompletedDeals()">
                                <option value="50">50</option>
                                <option value="100" selected>100</option>
                                <option value="200">200</option>
                                <option value="500">500</option>
                            </select>
                        </label>
                    </div>
                </div>
                <div class="table-container">
                    <table id="completed-deals-table">
                        <thead>
                            <tr>
                                <th>ID</th>
                                <th>⏰ Час</th>
                                <th>💵 Купівля</th>
                                <th>💰 Продаж</th>
                                <th>📈 Спред</th>
                                <th>💸 Сума купівлі</th>
                                <th>💵 Сума продажу</th>
                                <th>💚 Прибуток</th>
                                <th>📊 ROI</th>
                                <th>👤 Продавець</th>
                                <th>👤 Покупець</th>
                                <th>📌 Статус</th>
                            </tr>
                        </thead>
                        <tbody id="completed-deals-body">
                            <tr><td colspan="12" class="loading">Завантаження...</td></tr>
                        </tbody>
                    </table>
                </div>
            </div>

            <div class="opportunities-section">
                <div class="opportunities-header">
                    <h2>❌ Відхилені можливості</h2>
                    <div class="controls">
                        <label>Показати: 
                            <select id="rejected-limit" onchange="loadRejectedDeals()">
                                <option value="50">50</option>
                                <option value="100" selected>100</option>
                                <option value="200">200</option>
                                <option value="500">500</option>
                            </select>
                        </label>
                    </div>
                </div>
                <div class="table-container">
                    <table id="rejected-deals-table">
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
                                <th>👤 Продавець</th>
                                <th>👤 Покупець</th>
                            </tr>
                        </thead>
                        <tbody id="rejected-deals-body">
                            <tr><td colspan="10" class="loading">Завантаження...</td></tr>
                        </tbody>
                    </table>
                </div>
            </div>

            <div class="opportunities-section">
                <div class="opportunities-header">
                    <h2>📋 Логи подій</h2>
                    <div class="controls">
                        <label>Показати: 
                            <select id="logs-limit" onchange="loadLogs()">
                                <option value="50">50</option>
                                <option value="100" selected>100</option>
                                <option value="200">200</option>
                                <option value="500">500</option>
                            </select>
                        </label>
                    </div>
                </div>
                <div class="table-container">
                    <table id="logs-table">
                        <thead>
                            <tr>
                                <th>⏰ Час</th>
                                <th>📊 Рівень</th>
                                <th>📝 Повідомлення</th>
                            </tr>
                        </thead>
                        <tbody id="logs-body">
                            <tr><td colspan="3" class="loading">Завантаження...</td></tr>
                        </tbody>
                    </table>
                </div>
            </div>
        </div>

        <!-- Вкладка Налаштування -->
        <div id="settings-tab" class="tab-content">
            <div class="settings-form">
                <form id="settings-form">
                    <div class="settings-group">
                        <h3>💰 Торгові параметри</h3>
                        <div class="setting-row">
                            <div class="setting-label">
                                STARTING_CAPITAL
                                <small>Початковий капітал для розрахунку прибутку (грн)</small>
                            </div>
                            <div class="setting-input">
                                <input type="number" id="STARTING_CAPITAL" step="1000" value="40000">
                                <div class="current-value">Поточне: 40000 грн</div>
                            </div>
                        </div>
                        <div class="setting-row">
                            <div class="setting-label">
                                MIN_SPREAD_PERCENT
                                <small>Мінімальний спред для сигналу (%)</small>
                            </div>
                            <div class="setting-input">
                                <input type="number" id="MIN_SPREAD_PERCENT" step="0.1" value="0.98">
                                <div class="current-value">Поточне: 0.98%</div>
                            </div>
                        </div>
                        <div class="setting-row">
                            <div class="setting-label">
                                MIN_DEAL_AMOUNT
                                <small>Мінімальна сума угоди (грн)</small>
                            </div>
                            <div class="setting-input">
                                <input type="number" id="MIN_DEAL_AMOUNT" step="1000" value="20000">
                                <div class="current-value">Поточне: 20000 грн</div>
                            </div>
                        </div>
                        <div class="setting-row">
                            <div class="setting-label">
                                MAX_DEAL_AMOUNT
                                <small>Максимальна сума угоди (грн) | 0 = без обмежень</small>
                            </div>
                            <div class="setting-input">
                                <input type="number" id="MAX_DEAL_AMOUNT" step="1000" value="42000">
                                <div class="current-value">Поточне: 42000 грн</div>
                            </div>
                        </div>
                        <div class="setting-row">
                            <div class="setting-label">
                                SCAN_INTERVAL_SECONDS
                                <small>Інтервал сканування ринку (секунди)</small>
                            </div>
                            <div class="setting-input">
                                <input type="number" id="SCAN_INTERVAL_SECONDS" step="1" value="5">
                                <div class="current-value">Поточне: 5 сек</div>
                            </div>
                        </div>
                        <div class="setting-row">
                            <div class="setting-label">
                                SLIPPAGE_RESERVE_PERCENT
                                <small>Резерв на прослизання (%)</small>
                            </div>
                            <div class="setting-input">
                                <input type="number" id="SLIPPAGE_RESERVE_PERCENT" step="0.1" value="0.2">
                                <div class="current-value">Поточне: 0.2%</div>
                            </div>
                        </div>
                    </div>

                    <div class="settings-group">
                        <h3>🛡 Фільтри мерчантів</h3>
                        <div class="setting-row">
                            <div class="setting-label">
                                MIN_COMPLETION_RATE
                                <small>Мінімальний рейтинг мерчанта (%)</small>
                            </div>
                            <div class="setting-input">
                                <input type="number" id="MIN_COMPLETION_RATE" step="1" value="90">
                                <div class="current-value">Поточне: 90%</div>
                            </div>
                        </div>
                        <div class="setting-row">
                            <div class="setting-label">
                                MIN_ORDERS_COUNT
                                <small>Мінімальна кількість угод у мерчанта</small>
                            </div>
                            <div class="setting-input">
                                <input type="number" id="MIN_ORDERS_COUNT" step="10" value="50">
                                <div class="current-value">Поточне: 50 угод</div>
                            </div>
                        </div>
                        <div class="setting-row">
                            <div class="setting-label">
                                MERCHANT_ONLINE_ONLY
                                <small>Враховувати лише онлайн мерчантів</small>
                            </div>
                            <div class="setting-input checkbox-input">
                                <input type="checkbox" id="MERCHANT_ONLINE_ONLY" checked>
                                <label>Тільки онлайн мерчанти</label>
                            </div>
                        </div>
                    </div>

                    <div class="settings-group">
                        <h3>🏦 Ліміт НБУ</h3>
                        <div class="setting-row">
                            <div class="setting-label">
                                NBU_MONTHLY_LIMIT
                                <small>Місячний ліміт НБУ для P2P угод (грн)</small>
                            </div>
                            <div class="setting-input">
                                <input type="number" id="NBU_MONTHLY_LIMIT" step="10000" value="120000">
                                <div class="current-value">Поточне: 120000 грн</div>
                            </div>
                        </div>
                    </div>

                    <div class="settings-group">
                        <h3>📋 Інші параметри</h3>
                        <div class="setting-row">
                            <div class="setting-label">
                                COOLDOWN_SECONDS
                                <small>Пауза між однаковими сигналами (секунди)</small>
                            </div>
                            <div class="setting-input">
                                <input type="number" id="COOLDOWN_SECONDS" step="5" value="30">
                                <div class="current-value">Поточне: 30 сек</div>
                            </div>
                        </div>
                    </div>

                    <div style="text-align: center;">
                        <button type="button" class="btn-save" onclick="saveSettings()">💾 Зберегти налаштування</button>
                        <button type="button" class="btn-save" style="background: #ff9800;" onclick="loadSettings()">🔄 Перезавантажити</button>
                    </div>
                </form>
                <div id="settings-message" style="text-align: center; margin-top: 15px; color: #4caf50; display: none;">✅ Налаштування збережено! Бот буде перезапущено.</div>
            </div>
        </div>
    </div>

    <script>
        let spreadChart = null, profitChart = null, heatmapChart = null;

        function formatNumber(num, d=2) { return num ? num.toLocaleString('uk-UA', {minFractionDigits:d, maxFractionDigits:d}) : '---'; }
        function formatProfit(num) { return num ? (num >= 0 ? `+${formatNumber(num)}` : `-${formatNumber(Math.abs(num))}`) : '---'; }

        function showTab(tabName) {
            document.querySelectorAll('.tab-content').forEach(tab => tab.classList.remove('active'));
            document.querySelectorAll('.tab-btn').forEach(btn => btn.classList.remove('active'));

            document.getElementById(`${tabName}-tab`).classList.add('active');
            event.target.classList.add('active');
        }

        async function loadSettings() {
            try {
                const resp = await fetch('/api/settings');
                const data = await resp.json();
                document.getElementById('STARTING_CAPITAL').value = data.STARTING_CAPITAL;
                document.getElementById('MIN_SPREAD_PERCENT').value = data.MIN_SPREAD_PERCENT;
                document.getElementById('MIN_DEAL_AMOUNT').value = data.MIN_DEAL_AMOUNT;
                document.getElementById('MAX_DEAL_AMOUNT').value = data.MAX_DEAL_AMOUNT;
                document.getElementById('SCAN_INTERVAL_SECONDS').value = data.SCAN_INTERVAL_SECONDS;
                document.getElementById('SLIPPAGE_RESERVE_PERCENT').value = data.SLIPPAGE_RESERVE_PERCENT;
                document.getElementById('MIN_COMPLETION_RATE').value = data.MIN_COMPLETION_RATE;
                document.getElementById('MIN_ORDERS_COUNT').value = data.MIN_ORDERS_COUNT;
                document.getElementById('MERCHANT_ONLINE_ONLY').checked = data.MERCHANT_ONLINE_ONLY;
                document.getElementById('NBU_MONTHLY_LIMIT').value = data.NBU_MONTHLY_LIMIT;
                document.getElementById('COOLDOWN_SECONDS').value = data.COOLDOWN_SECONDS;
            } catch(e) { console.error(e); }
        }

        async function saveSettings() {
            const settings = {
                STARTING_CAPITAL: parseFloat(document.getElementById('STARTING_CAPITAL').value),
                MIN_SPREAD_PERCENT: parseFloat(document.getElementById('MIN_SPREAD_PERCENT').value),
                MIN_DEAL_AMOUNT: parseFloat(document.getElementById('MIN_DEAL_AMOUNT').value),
                MAX_DEAL_AMOUNT: parseFloat(document.getElementById('MAX_DEAL_AMOUNT').value),
                SCAN_INTERVAL_SECONDS: parseInt(document.getElementById('SCAN_INTERVAL_SECONDS').value),
                SLIPPAGE_RESERVE_PERCENT: parseFloat(document.getElementById('SLIPPAGE_RESERVE_PERCENT').value),
                MIN_COMPLETION_RATE: parseFloat(document.getElementById('MIN_COMPLETION_RATE').value),
                MIN_ORDERS_COUNT: parseInt(document.getElementById('MIN_ORDERS_COUNT').value),
                MERCHANT_ONLINE_ONLY: document.getElementById('MERCHANT_ONLINE_ONLY').checked,
                NBU_MONTHLY_LIMIT: parseFloat(document.getElementById('NBU_MONTHLY_LIMIT').value),
                COOLDOWN_SECONDS: parseInt(document.getElementById('COOLDOWN_SECONDS').value)
            };

            try {
                const resp = await fetch('/api/settings', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(settings)
                });
                const data = await resp.json();
                if (data.success) {
                    const msg = document.getElementById('settings-message');
                    msg.style.display = 'block';
                    setTimeout(() => msg.style.display = 'none', 3000);
                    alert('✅ Налаштування збережено! Бот перезапуститься автоматично.');
                    setTimeout(() => location.reload(), 2000);
                } else {
                    alert('❌ Помилка: ' + data.error);
                }
            } catch(e) { console.error(e); }
        }

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

        async function rejectAllOpportunities() {
            if (!confirm('⚠️ ВИ ДІЙСНО ХОЧЕТЕ ВІДХИЛИТИ ВСІ МОЖЛИВОСТІ?\\nЦю дію НЕ МОЖНА скасувати!')) return;
            if (!confirm('Видалити всі можливості, що очікують підтвердження?')) return;
            try {
                const resp = await fetch('/api/opportunities/reject-all', { method: 'POST' });
                const data = await resp.json();
                if (data.success) {
                    alert(`✅ Відхилено ${data.count} можливостей!`);
                    refreshData();
                } else {
                    alert('❌ Помилка: ' + data.error);
                }
            } catch(e) { console.error(e); }
        }

        async function loadHeatmap() {
            const days = document.getElementById('heatmap-days').value;
            const type = document.getElementById('heatmap-type').value;
            try {
                const resp = await fetch(`/api/heatmap?days=${days}&type=${type}`);
                const data = await resp.json();

                const colorscale = [
                    [0, '#90be6d'],
                    [0.33, '#f9c74f'],
                    [0.66, '#f9844a'],
                    [1, '#f44336']
                ];

                const trace = {
                    z: data.data,
                    x: data.hours,
                    y: data.days,
                    type: 'heatmap',
                    colorscale: colorscale,
                    showscale: true,
                    text: data.data.map(row => row.map(() => '')),
                    textfont: { size: 10 },
                    hovertemplate: '<b>%{y}</b> %{x}:00<br>Середній прибуток: <b>%{z:.0f} грн</b><br><extra></extra>',
                    texttemplate: '%{text}'
                };

                const layout = {
                    title: { text: `Середній прибуток по годинах (останні ${days} днів)`, font: { size: 14 } },
                    xaxis: { title: 'Година дня', tickmode: 'linear', tick0: 0, dtick: 2, tickangle: 0 },
                    yaxis: { title: 'День тижня', autorange: 'reversed' },
                    height: 350,
                    margin: { l: 60, r: 40, t: 50, b: 40 },
                    hoverlabel: { bgcolor: 'white', font: { size: 12, color: '#333' } }
                };

                if (heatmapChart) {
                    Plotly.react('heatmap-chart', [trace], layout);
                } else {
                    heatmapChart = Plotly.newPlot('heatmap-chart', [trace], layout);
                }

                updateHeatmapStats(data);
            } catch(e) { console.error(e); }
        }

        function updateHeatmapStats(data) {
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
            let statsDiv = document.getElementById('heatmap-stats');
            if (!statsDiv) {
                statsDiv = document.createElement('div');
                statsDiv.id = 'heatmap-stats';
                statsDiv.style.cssText = 'margin-top: 15px; padding: 10px; background: #f5f5f5; border-radius: 10px; text-align: center;';
                document.querySelector('.heatmap-legend').after(statsDiv);
            }
            if (bestProfit > 0) {
                statsDiv.innerHTML = `<strong>📈 Найкращий час для арбітражу:</strong> ${bestDay} ${bestHour}:00 (середній прибуток ${bestProfit.toFixed(0)} грн за угоду)`;
            } else {
                statsDiv.innerHTML = `<strong>📈 Немає даних за вибраний період</strong>`;
            }
        }

        async function confirmOpportunity(id, buyAmount, sellAmount, profit, buyMerchant, sellMerchant) {
            if (!confirm(`Підтвердити виконання можливості #${id}?\\nПрибуток: +${profit} UAH\\nВід: ${buyMerchant} → ${sellMerchant}`)) return;
            try {
                const resp = await fetch(`/api/opportunities/${id}/confirm`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ buy_amount: buyAmount, sell_amount: sellAmount }) });
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
                document.getElementById('nbu-warning').style.display = percent > 85 ? 'block' : 'none';
            } catch(e) { console.error(e); }
        }

        async function loadCompletedDeals() {
            const limit = document.getElementById('completed-limit').value;
            try {
                const resp = await fetch(`/api/completed-deals?limit=${limit}`);
                const deals = await resp.json();
                const tbody = document.getElementById('completed-deals-body');
                if (!deals || deals.length === 0) {
                    tbody.innerHTML = '<tr><td colspan="12" class="loading">📭 Немає виконаних угод</td></tr>';
                    return;
                }
                tbody.innerHTML = deals.map(t => {
                    let statusClass = t.status === 'completed' ? 'status-completed' : 'status-cancelled';
                    let statusText = t.status === 'completed' ? 'Виконано' : 'Скасовано';
                    const buyAmount = t.amount_usdt * t.buy_price;
                    const sellAmount = t.amount_usdt * t.sell_price;
                    const spread = ((t.sell_price - t.buy_price) / t.buy_price) * 100;
                    const roi = (t.profit / t.amount_uah) * 100;
                    return `<tr>
                        <td>${t.id}</td>
                        <td>${new Date(t.timestamp).toLocaleString('uk-UA')}</td>
                        <td>${formatNumber(t.buy_price)} UAH</td>
                        <td>${formatNumber(t.sell_price)} UAH</td>
                        <td>${formatNumber(spread, 2)}%</td>
                        <td class="profit-positive">${formatNumber(buyAmount, 0)} грн</td>
                        <td class="profit-positive">${formatNumber(sellAmount, 0)} грн</td>
                        <td class="profit-positive">${formatProfit(t.profit)} UAH</td>
                        <td>${formatNumber(roi, 2)}%</td>
                        <td>${t.buy_merchant}</td>
                        <td>${t.sell_merchant}</td>
                        <td><span class="status-badge ${statusClass}">${statusText}</span></td>
                    </tr>`;
                }).join('');
            } catch(e) { console.error(e); }
        }

        async function loadRejectedDeals() {
            const limit = document.getElementById('rejected-limit').value;
            try {
                const resp = await fetch(`/api/rejected-deals?limit=${limit}`);
                const deals = await resp.json();
                const tbody = document.getElementById('rejected-deals-body');
                if (!deals || deals.length === 0) {
                    tbody.innerHTML = '<tr><td colspan="10" class="loading">📭 Немає відхилених угод</td></tr>';
                    return;
                }
                tbody.innerHTML = deals.map(o => {
                    const buyAmount = o.usdt_amount ? o.usdt_amount * o.buy_price : 0;
                    const sellAmount = o.usdt_amount ? o.usdt_amount * o.sell_price : 0;
                    return `<tr>
                        <td>${new Date(o.timestamp).toLocaleString('uk-UA')}</td>
                        <td>${formatNumber(o.buy_price)} UAH</td>
                        <td>${formatNumber(o.sell_price)} UAH</td>
                        <td>${formatNumber(o.spread, 2)}%</td>
                        <td class="profit-positive">${formatNumber(buyAmount, 0)} грн</td>
                        <td class="profit-positive">${formatNumber(sellAmount, 0)} грн</td>
                        <td class="profit-positive">${formatProfit(o.profit)} UAH</td>
                        <td>${formatNumber(o.roi, 2)}%</td>
                        <td>${o.buy_merchant}</td>
                        <td>${o.sell_merchant}</td>
                    </tr>`;
                }).join('');
            } catch(e) { console.error(e); }
        }

        async function loadLogs() {
            const limit = document.getElementById('logs-limit').value;
            try {
                const resp = await fetch(`/api/logs?limit=${limit}`);
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
                    <td>${formatNumber(o.spread, 2)}%</td>
                    <td class="profit-positive">${formatNumber(buyAmount, 0)} грн</td>
                    <td class="profit-positive">${formatNumber(sellAmount, 0)} грн</td>
                    <td class="profit-positive">${formatProfit(o.profit)} UAH</td>
                    <td>${formatNumber(o.roi, 2)}%</td>
                    <td>
                        <button class="btn-success" onclick="confirmOpportunity(${o.id}, ${buyAmount}, ${sellAmount}, ${o.profit}, '${o.buy_merchant}', '${o.sell_merchant}')">✅ Підтвердити</button>
                        <button class="btn-danger" onclick="rejectOpportunity(${o.id})">❌ Відхилити</button>
                     </td>
                </tr>`;
            }).join('');
        }

        function updateCharts(opps) {
            if (!opps || opps.length === 0) return;
            const rev = [...opps].reverse();
            const times = rev.map(o => new Date(o.timestamp).toLocaleString('uk-UA'));
            const spreads = rev.map(o => o.spread);
            const profits = rev.map(o => o.profit);

            const spreadTrace = {x: times, y: spreads, type: 'scatter', mode: 'lines+markers', line: {color: '#ff9800', width: 2}};
            if (spreadChart) {
                Plotly.react('spread-chart', [spreadTrace], {title:'', xaxis:{title:'Час'}, yaxis:{title:'Спред (%)'}});
            } else {
                spreadChart = Plotly.newPlot('spread-chart', [spreadTrace], {title:'', xaxis:{title:'Час'}, yaxis:{title:'Спред (%)'}});
            }

            const profitTrace = {x: times, y: profits, type: 'bar', marker: {color: profits.map(p => p >= 0 ? '#4caf50' : '#f44336')}};
            if (profitChart) {
                Plotly.react('profit-chart', [profitTrace], {title:'', xaxis:{title:'Час'}, yaxis:{title:'Прибуток (UAH)'}});
            } else {
                profitChart = Plotly.newPlot('profit-chart', [profitTrace], {title:'', xaxis:{title:'Час'}, yaxis:{title:'Прибуток (UAH)'}});
            }
        }

        function updateStats(opps) {
            if (!opps || opps.length === 0) return;
            const total = opps.reduce((s, o) => s + o.profit, 0);
            const avg = total / opps.length;
            const max = Math.max(...opps.map(o => o.profit));
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

        function refreshData() {
            fetchData();
            loadNBULimit();
            loadCompletedDeals();
            loadRejectedDeals();
            loadLogs();
            loadHeatmap();
        }

        // Ініціалізація
        fetchData();
        loadNBULimit();
        loadCompletedDeals();
        loadRejectedDeals();
        loadLogs();
        loadHeatmap();
        loadSettings();

        // Оновлення кожні 5 секунд
        setInterval(() => {
            fetchData();
            loadNBULimit();
            loadCompletedDeals();
            loadRejectedDeals();
            loadLogs();
            loadHeatmap();
        }, 5000);
    </script>
</body>
</html>
"""


@app.get("/", response_class=HTMLResponse)
async def get_dashboard():
    return HTMLResponse(content=HTML_PAGE)


@app.get("/api/settings")
async def get_settings():
    """Отримати поточні налаштування"""
    return {
        "STARTING_CAPITAL": settings.STARTING_CAPITAL,
        "MIN_SPREAD_PERCENT": settings.MIN_SPREAD_PERCENT,
        "MIN_DEAL_AMOUNT": settings.MIN_DEAL_AMOUNT,
        "MAX_DEAL_AMOUNT": settings.MAX_DEAL_AMOUNT,
        "SCAN_INTERVAL_SECONDS": settings.SCAN_INTERVAL_SECONDS,
        "SLIPPAGE_RESERVE_PERCENT": settings.SLIPPAGE_RESERVE_PERCENT,
        "MIN_COMPLETION_RATE": settings.MIN_COMPLETION_RATE,
        "MIN_ORDERS_COUNT": settings.MIN_ORDERS_COUNT,
        "MERCHANT_ONLINE_ONLY": settings.MERCHANT_ONLINE_ONLY,
        "NBU_MONTHLY_LIMIT": settings.NBU_MONTHLY_LIMIT,
        "COOLDOWN_SECONDS": settings.COOLDOWN_SECONDS
    }


@app.post("/api/settings")
async def save_settings(request: dict):
    """Зберегти налаштування в .env та перезапустити бота"""
    import subprocess
    import sys

    try:
        # Читаємо поточний .env
        env_path = os.path.join(os.path.dirname(__file__), '..', '.env')
        with open(env_path, 'r') as f:
            lines = f.readlines()

        # Оновлюємо значення
        new_settings = {
            "STARTING_CAPITAL": str(request.get("STARTING_CAPITAL", 40000)),
            "MIN_SPREAD_PERCENT": str(request.get("MIN_SPREAD_PERCENT", 0.98)),
            "MIN_DEAL_AMOUNT": str(request.get("MIN_DEAL_AMOUNT", 20000)),
            "MAX_DEAL_AMOUNT": str(request.get("MAX_DEAL_AMOUNT", 42000)),
            "SCAN_INTERVAL_SECONDS": str(request.get("SCAN_INTERVAL_SECONDS", 5)),
            "SLIPPAGE_RESERVE_PERCENT": str(request.get("SLIPPAGE_RESERVE_PERCENT", 0.2)),
            "MIN_COMPLETION_RATE": str(request.get("MIN_COMPLETION_RATE", 90)),
            "MIN_ORDERS_COUNT": str(request.get("MIN_ORDERS_COUNT", 50)),
            "MERCHANT_ONLINE_ONLY": "true" if request.get("MERCHANT_ONLINE_ONLY", True) else "false",
            "NBU_MONTHLY_LIMIT": str(request.get("NBU_MONTHLY_LIMIT", 120000)),
            "COOLDOWN_SECONDS": str(request.get("COOLDOWN_SECONDS", 30))
        }

        updated_lines = []
        for line in lines:
            updated = False
            for key, value in new_settings.items():
                if line.startswith(f"{key}="):
                    updated_lines.append(f"{key}={value}\n")
                    updated = True
                    break
            if not updated:
                updated_lines.append(line)

        # Додаємо відсутні параметри
        existing_keys = set()
        for line in updated_lines:
            if '=' in line:
                existing_keys.add(line.split('=')[0])

        for key, value in new_settings.items():
            if key not in existing_keys:
                updated_lines.append(f"{key}={value}\n")

        # Записуємо .env
        with open(env_path, 'w') as f:
            f.writelines(updated_lines)

        # Додаємо лог
        db.add_log("INFO", "Settings updated via web interface")

        # Перезапускаємо бота (через systemd)
        try:
            subprocess.run(["sudo", "systemctl", "restart", "p2p_bot.service"], capture_output=True)
        except:
            pass  # Якщо не systemd, просто зберігаємо

        return {"success": True}
    except Exception as e:
        return {"success": False, "error": str(e)}


@app.get("/api/opportunities/pending")
async def get_pending_opportunities(limit: int = 100):
    """Отримати можливості, що очікують підтвердження"""
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
        ).order_by(desc(Opportunity.timestamp)).limit(limit).all()
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


@app.get("/api/completed-deals")
async def get_completed_deals(limit: int = 100):
    """Отримати виконані угоди (тільки ті, що були підтверджені через кнопку)"""
    from app.nbu.limits import Transaction
    from sqlalchemy import create_engine, desc
    from sqlalchemy.orm import sessionmaker
    from config.settings import settings

    engine = create_engine(settings.DATABASE_URL)
    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        transactions = session.query(Transaction).filter(
            Transaction.status == 'completed'
        ).order_by(desc(Transaction.timestamp)).limit(limit).all()
        return [
            {
                "id": t.id,
                "timestamp": t.timestamp.isoformat(),
                "amount_uah": t.amount_uah,
                "amount_usdt": t.amount_usdt,
                "profit": t.profit,
                "buy_merchant": t.buy_merchant,
                "sell_merchant": t.sell_merchant,
                "buy_price": t.buy_price,
                "sell_price": t.sell_price,
                "status": t.status
            }
            for t in transactions
        ]
    finally:
        session.close()


@app.get("/api/rejected-deals")
async def get_rejected_deals(limit: int = 100):
    """Отримати відхилені можливості"""
    from app.database.models import Opportunity
    from sqlalchemy import create_engine, desc
    from sqlalchemy.orm import sessionmaker
    from config.settings import settings

    engine = create_engine(settings.DATABASE_URL)
    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        from app.nbu.limits import Transaction
        trans_ids = [t.id for t in session.query(Transaction.id).all()]

        if not trans_ids:
            opportunities = session.query(Opportunity).filter(
                Opportunity.alert_sent == True,
                Opportunity.net_profit > 0
            ).order_by(desc(Opportunity.timestamp)).limit(limit).all()
        else:
            opportunities = session.query(Opportunity).filter(
                Opportunity.alert_sent == True,
                Opportunity.net_profit > 0,
                ~Opportunity.id.in_(trans_ids)
            ).order_by(desc(Opportunity.timestamp)).limit(limit).all()

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
                "buy_merchant": o.buy_merchant,
                "sell_merchant": o.sell_merchant
            }
            for o in opportunities
        ]
    finally:
        session.close()


@app.post("/api/opportunities/reject-all")
async def reject_all_opportunities():
    """Відхилити всі можливості, що очікують підтвердження"""
    from app.database.models import Opportunity
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from config.settings import settings

    engine = create_engine(settings.DATABASE_URL)
    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        count = session.query(Opportunity).filter(Opportunity.alert_sent == False).update(
            {Opportunity.alert_sent: True}
        )
        session.commit()
        return {"success": True, "count": count}
    except Exception as e:
        session.rollback()
        return {"success": False, "error": str(e)}
    finally:
        session.close()


@app.post("/api/opportunities/{opp_id}/confirm")
async def confirm_opportunity(opp_id: int):
    """Підтвердити можливість - створити транзакцію та зарезервувати ліміт НБУ"""
    from app.database.models import Opportunity
    from app.nbu.limits import NBULimit, Transaction
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

        current_month = datetime.now().strftime('%Y-%m')
        limit = session.query(NBULimit).filter(NBULimit.month == current_month).first()
        if not limit:
            limit = NBULimit(total_limit=settings.NBU_MONTHLY_LIMIT, used_amount=0, month=current_month)
            session.add(limit)

        amount_uah = opp.usdt_amount * opp.buy_price
        if limit.used_amount + amount_uah > limit.total_limit:
            return {"success": False,
                    "error": f"NBU limit exceeded! Need {amount_uah:,.0f}, available {limit.total_limit - limit.used_amount:,.0f}"}

        # Створюємо транзакцію
        transaction = Transaction(
            amount_uah=amount_uah,
            amount_usdt=opp.usdt_amount,
            buy_merchant=opp.buy_merchant,
            sell_merchant=opp.sell_merchant,
            buy_price=opp.buy_price,
            sell_price=opp.sell_price,
            profit=opp.net_profit,
            status='completed'
        )
        session.add(transaction)

        limit.used_amount += amount_uah
        limit.updated_at = datetime.now()
        opp.alert_sent = True

        session.commit()
        db.add_log("SUCCESS", f"Opportunity #{opp_id} confirmed! Transaction #{transaction.id} created.")

        return {"success": True, "transaction_id": transaction.id}
    except Exception as e:
        session.rollback()
        return {"success": False, "error": str(e)}
    finally:
        session.close()


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

        opp.alert_sent = True
        session.commit()
        db.add_log("INFO", f"Opportunity #{opp_id} rejected")

        return {"success": True}
    except Exception as e:
        session.rollback()
        return {"success": False, "error": str(e)}
    finally:
        session.close()


@app.get("/api/logs")
async def get_logs(limit: int = 100):
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
    finally:
        session.close()


@app.get("/api/heatmap")
async def get_heatmap(days: int = 30, type: str = "all"):
    """API для отримання даних теплової карти"""
    return db.get_heatmap_data(days=days, type=type)


@app.post("/api/reset-nbu-limit")
async def reset_nbu_limit():
    """Скинути ліміт НБУ (обнулити використання)"""
    from app.nbu.limits import NBULimit
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from config.settings import settings
    from datetime import datetime

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
            limit = NBULimit(total_limit=settings.NBU_MONTHLY_LIMIT, used_amount=0, month=current_month)
            session.add(limit)
        session.commit()
        db.add_log("INFO", "NBU limit reset by user")
        return {"success": True}
    except Exception as e:
        return {"success": False, "error": str(e)}
    finally:
        session.close()


@app.post("/api/reset-database")
async def reset_database():
    """Скинути базу даних (очистити всі таблиці)"""
    from sqlalchemy import create_engine, text
    from config.settings import settings

    try:
        engine = create_engine(settings.DATABASE_URL)
        with engine.connect() as conn:
            conn.execute(text("DELETE FROM opportunities"))
            conn.execute(text("DELETE FROM p2p_quotes"))
            conn.execute(text("DELETE FROM logs"))
            conn.execute(text("DELETE FROM nbu_limits"))
            conn.execute(text("DELETE FROM transactions"))
            conn.execute(text("DELETE FROM sqlite_sequence"))
            conn.commit()

        from app.nbu.limits import NBULimit
        from datetime import datetime
        from sqlalchemy.orm import sessionmaker
        Session = sessionmaker(bind=engine)
        session = Session()
        try:
            current_month = datetime.now().strftime('%Y-%m')
            new_limit = NBULimit(total_limit=settings.NBU_MONTHLY_LIMIT, used_amount=0, month=current_month)
            session.add(new_limit)
            session.commit()
        finally:
            session.close()

        db.add_log("INFO", "Database reset by user")
        return {"success": True}
    except Exception as e:
        return {"success": False, "error": str(e)}


@app.get("/api/nbu/limit")
async def get_nbu_limit():
    """API для отримання ліміту НБУ"""
    return {
        "total_limit": settings.NBU_MONTHLY_LIMIT,
        "used_amount": nbu.get_used_amount(),
        "remaining": nbu.get_remaining_limit(),
        "usage_percent": nbu.get_usage_percent()
    }


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