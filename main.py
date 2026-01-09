# main.py
# V10.15 (Final Syntax Fix)
#
# ИЗМЕНЕНИЯ V10.15:
# - ✅ Полностью исправлен SyntaxError в обработчиках событий.
# - ✅ Код развернут в нормальный читаемый вид (без точек с запятой).
# - ✅ Все функции (журнал, черный ящик, трейлинг) на месте.

import win7_core
win7_core.apply_patches() 
import tkinter as tk
from tkinter import messagebox
import threading
import time
import sys
import datetime as dt
import ssl
import queue
import math
import numpy as np
import subprocess 
import os 
import pandas as pd 
import webbrowser 
import json 
import csv 

# --- Подключение модулей архитектуры ---
try:
    from config_handler import ConfigHandler
    from chart_system import ChartSystem
    from ui_layout import UiBuilder
except ImportError as e:
    messagebox.showerror("Ошибка импорта", f"Не найдены модули архитектуры: {e}")
    sys.exit(1)

# --- WebSocket ---
try:
    import websocket
    WS_AVAILABLE = True
except ImportError:
    WS_AVAILABLE = False

# --- ИМПОРТЫ МОДУЛЕЙ ЛОГИКИ ---
try:
    from binance_api import BinanceTrader
    from autopilot import AutopilotManager
    from trend_manager import TrendManager
    from reversion_manager import ReversionManager
    from watcher import Watcher
except ImportError as e:
    messagebox.showerror("Ошибка V10.15", f"Не найден модуль логики: {e}")

# --- SSL Fix ---
try:
    if sys.platform == 'win32':
        ssl._create_default_https_context = ssl._create_unverified_context
except: pass

if sys.platform == 'win32':
    import codecs
    try:
        sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
        sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')
    except: pass

# ==============================================================================
# ГЛАВНЫЙ КЛАСС ПРИЛОЖЕНИЯ
# ==============================================================================
class MomentumApp:
    def __init__(self, root):
        self.root = root
        self.root.title('Моментум-Сканер V10.15 (Stable)') 
        self.root.geometry("1400x950")

        self.log_queue = queue.Queue()
        
        self.config_handler = ConfigHandler(self.queue_log)
        self.chart_system = ChartSystem(self)
        self.ui_builder = UiBuilder(self)

        self.config_from_file = self.config_handler.load_and_validate_config()
        self.blacklist = self.config_handler.load_blacklist()

        self._init_variables()

        self.running = threading.Event()
        self.logic_thread = None   
        
        self.open_positions = {}
        self.pending_orders = {} 
        self.position_lock = threading.Lock()
        
        self.symbol_info_cache = {}
        self.scanner_queue = queue.Queue() 
        
        self.total_profit_usd = 0.0
        self.trade_count = 0
        self.last_sync_time = 0
        self.paper_quote_balance = 1000.0
        self.real_quote_balance = 0.0
        self.first_sync_done = False
        self.global_pnl_peak = 0.0
        self.global_pnl_last_peak_time = 0.0
        self.last_closed_position_data = None 
        self.chart_tf = '15m' 
        self.last_plotted_symbol = ""
        self.last_worker_start_time = 0
        self.worker_scan_interval = 300 
        self.worker_lock_file = "watchlist.lock"
        self.worker_lock_watchdog_time = 600 
        self.trader = None
        self.autopilot = None 
        self.trend_manager = None 
        self.reversion_manager = None 
        self.watcher = None 
        self.metric_vars = {} 
        self.pnl_history = []
        self.ws_base_url = "wss://fstream.binance.com/ws/"
        
        # UI vars
        self.log_text = None; self.scanner_tree = None; self.open_orders_tree = None
        self.trade_history_tree = None; self.btn_start = None; self.btn_stop = None
        self.status_label = None; self.blacklist_listbox = None; self.chart_tab = None
        
        if not os.path.exists("trade_logs"): os.makedirs("trade_logs")

        self.ui_builder.setup_ui()
        self.start_periodic_updates()
        self.root.after(100, self._initialize_app)

    # --- ЛОГГЕР ---
    def queue_log(self, msg, lvl="info"): 
        self.log_queue.put((msg, lvl))

    def _init_variables(self):
        cfg = self.config_from_file
        self.api_key = tk.StringVar(value=cfg.get('api_key', ''))
        self.api_secret = tk.StringVar(value=cfg.get('api_secret', ''))
        self.load_keys_flag = tk.BooleanVar(value=False)
        self.max_concurrent_trades = tk.IntVar(value=cfg.get('max_concurrent_trades', 5))
        self.trade_amount_usd = tk.DoubleVar(value=cfg.get('trade_amount_usd', 10.0))
        self.leverage = tk.IntVar(value=cfg.get('leverage', 20))
        self.paper_start_balance = tk.DoubleVar(value=cfg.get('paper_start_balance', 1000.0))
        self.strategy_timeframe = tk.StringVar(value=cfg.get('strategy_timeframe', '5m')) 
        self.atr_timeframe_strat = tk.StringVar(value=cfg.get('atr_timeframe_strat', '15m')) 
        self.atr_period_strat = tk.IntVar(value=cfg.get('atr_period_strat', 14))
        self.sl_atr_multiplier = tk.DoubleVar(value=cfg.get('sl_atr_multiplier', 2.5)) 
        self.ts_atr_multiplier = tk.DoubleVar(value=cfg.get('ts_atr_multiplier', 1.5)) 
        self.sl_limit_enabled = tk.BooleanVar(value=cfg.get('sl_limit_enabled', True))
        self.sl_limit_percent = tk.DoubleVar(value=cfg.get('sl_limit_percent', 1.0)) 
        self.be_enabled = tk.BooleanVar(value=cfg.get('be_enabled', True))
        self.be_trigger_profit_usd = tk.DoubleVar(value=cfg.get('be_trigger_profit_usd', 0.5)) 
        self.be_profit_lock_usd = tk.DoubleVar(value=cfg.get('be_profit_lock_usd', 0.05)) 
        self.trade_cooldown_minutes = tk.IntVar(value=cfg.get('trade_cooldown_minutes', 15))
        self.per_pos_tp_enabled = tk.BooleanVar(value=cfg.get('per_pos_tp_enabled', True)) 
        self.per_pos_peak_drop_pct = tk.DoubleVar(value=cfg.get('per_pos_peak_drop_pct', 20.0))
        self.per_pos_stagnation_time = tk.IntVar(value=cfg.get('per_pos_stagnation_time', 180)) 
        self.per_pos_tp_min_profit_usd = tk.DoubleVar(value=cfg.get('per_pos_tp_min_profit_usd', 0.50)) 
        self.global_tp_enabled = tk.BooleanVar(value=cfg.get('global_tp_enabled', True))
        self.global_tp_amount = tk.DoubleVar(value=cfg.get('global_tp_amount', 20.0))
        self.trailing_pnl_enabled = tk.BooleanVar(value=cfg.get('trailing_pnl_enabled', True))
        self.trailing_pnl_peak_drop_pct = tk.DoubleVar(value=cfg.get('trailing_pnl_peak_drop_pct', 25.0))
        self.trailing_pnl_stagnation_time = tk.IntVar(value=cfg.get('trailing_pnl_stagnation_time', 120))
        self.scanner_liquidity_filter = tk.DoubleVar(value=cfg.get('scanner_liquidity_filter', 500000.0))
        self.scanner_timeframe = tk.StringVar(value=cfg.get('scanner_timeframe', '15m')) 
        self.cvd_scan_timeframe = tk.StringVar(value=cfg.get('cvd_scan_timeframe', '5m'))
        self.cvd_min_rvol = tk.DoubleVar(value=cfg.get('cvd_min_rvol', 0.5))
        self.cvd_min_strength = tk.IntVar(value=cfg.get('cvd_min_strength', 10))
        self.cvd_min_rr = tk.DoubleVar(value=cfg.get('cvd_min_rr', 1.5))
        self.cvd_max_signals = tk.IntVar(value=cfg.get('cvd_max_signals', 5))
        self.cvd_min_price_pct = tk.DoubleVar(value=cfg.get('cvd_min_price_pct', 0.1))
        self.cvd_min_cvd_pct = tk.DoubleVar(value=cfg.get('cvd_min_cvd_pct', 1.0))
        self.paper_mode = tk.BooleanVar(value=cfg.get('paper_mode', True)) 
        self.floating_pnl = tk.StringVar(value="0.00")
        self.first_real_mode_warning = True

    # ================= ЛОГИКА ЖУРНАЛА =================
    
    def _log_to_master_journal(self, action, symbol, side, price, pnl, extra_data=None):
        try:
            filename = "trade_logs/journal_v10.csv"
            file_exists = os.path.isfile(filename)
            timestamp = dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            strength = extra_data.get('strength', '') if extra_data else ''
            price_pct = extra_data.get('price_pct', '') if extra_data else ''
            cvd_pct = extra_data.get('cvd_pct', '') if extra_data else ''
            
            conf_p = self.cvd_min_price_pct.get()
            conf_c = self.cvd_min_cvd_pct.get()
            conf_s = self.cvd_min_strength.get()
            
            row = [timestamp, action, symbol, side, f"{price:.5f}", f"{pnl:.2f}", strength, f"{price_pct}", f"{cvd_pct}", conf_p, conf_c, conf_s]
            
            with open(filename, 'a', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                if not file_exists:
                    writer.writerow(["Time", "Action", "Symbol", "Side", "Price", "PnL", "Sig_Strength", "Sig_Price%", "Sig_CVD%", "Cfg_Price%", "Cfg_CVD%", "Cfg_Str"])
                writer.writerow(row)
        except Exception as e: print(f"Journal Error: {e}")

    def open_trade_logs_folder(self):
        path = os.path.abspath("trade_logs")
        if sys.platform == 'win32': os.startfile(path)

    # ================= ИНИЦИАЛИЗАЦИЯ =================

    def _initialize_app(self):
        self.queue_log("V10.15: Запуск...", "info") 
        self.load_api_keys_from_file()
        if self.api_key.get(): self.load_keys_flag.set(True)
        self.paper_mode.set(True)
        self.toggle_mode() 
        self._update_blacklist_ui()

    def start_strategy(self):
        if self.running.is_set(): return
        self.running.set()
        if self.btn_start: self.btn_start.config(state=tk.DISABLED)
        if self.btn_stop: self.btn_stop.config(state=tk.NORMAL)
        if self.status_label: self.status_label.config(text="Запуск V10.15...", foreground='#007ACC') 
        self._save_config_current()
        threading.Thread(target=self._strategy_init_thread, daemon=True).start()

    def stop_strategy(self):
        if not self.running.is_set(): return
        self.queue_log("Остановка...", "warning")
        self.running.clear() 
        if self.watcher: self.watcher.stop()
        if self.chart_system.chart_update_timer:
            self.root.after_cancel(self.chart_system.chart_update_timer)
            self.chart_system.chart_update_timer = None
        self.last_closed_position_data = None 
        if self.btn_stop: self.btn_stop.config(state=tk.DISABLED)
        if self.status_label: self.status_label.config(text="Остановка...", foreground='#FF8F00')

    def _strategy_init_thread(self):
        try:
            self.queue_log("V10.15: Чистый старт...", "info") 
            try:
                if os.path.exists("watchlist.json"): os.remove("watchlist.json")
                if os.path.exists("watchlist.json.tmp"): os.remove("watchlist.json.tmp")
                if os.path.exists(self.worker_lock_file): os.remove(self.worker_lock_file)
            except: pass

            self.trader = BinanceTrader(self.api_key.get(), self.api_secret.get(), self.queue_log)
            try:
                self.autopilot = AutopilotManager(self, self.trader)
                self.trend_manager = TrendManager(self, self.trader) 
                self.reversion_manager = ReversionManager(self, self.trader) 
                self.watcher = Watcher(self) 
                self.queue_log("Модули готовы.", "success") 
            except Exception as e:
                self.queue_log(f"Err Modules: {e}", "error"); self._stop_strategy_ui_threadsafe(); return 

            exchange_info = self.trader.get_exchange_info()
            if not exchange_info:
                 self.queue_log("Err API Info!", "error"); self._stop_strategy_ui_threadsafe(); return
                 
            self.symbol_info_cache.clear()
            for s_data in exchange_info.get('symbols', []):
                if s_data.get('contractType') == 'PERPETUAL' and s_data['symbol'].endswith('USDT'):
                    try:
                        self.symbol_info_cache[s_data['symbol']] = {
                            'quantityPrecision': s_data['quantityPrecision'], 'pricePrecision': s_data['pricePrecision'],
                            'minQty': float(next(f['minQty'] for f in s_data['filters'] if f['filterType'] == 'LOT_SIZE')),
                            'tickSize': float(next(f['tickSize'] for f in s_data['filters'] if f['filterType'] == 'PRICE_FILTER'))
                        }
                    except: pass 
            
            if not self.paper_mode.get(): self._sync_real_positions(self.trader)
            self.root.after(2000, self.chart_system.update_position_chart) 
            self.queue_log("Готов к работе.", "success") 
            self.root.after(0, self._start_main_loops)
        
        except Exception as e:
            self.queue_log(f"CRIT ERR: {e}", "error"); self._stop_strategy_ui_threadsafe()

    def _start_main_loops(self):
        if not self.running.is_set(): self._stop_strategy_ui_threadsafe(); return
        try:
            self.watcher.start() 
            self._schedule_ui_updates() 
            self.logic_thread = threading.Thread(target=self._periodic_logic_loop, daemon=True) 
            self.logic_thread.start()
            if self.status_label:
                self.root.after(0, lambda: self.status_label.config(text="🎯 Ожидание сигналов...", foreground='#00C853')) 
        except Exception: self._stop_strategy_ui_threadsafe()

    def _periodic_logic_loop(self):
        self.last_worker_start_time = time.time() - self.worker_scan_interval - 1 
        while self.running.is_set():
            try:
                curr_time = time.time()
                new_bl = self.config_handler.check_blacklist_update()
                if new_bl is not None:
                    self.blacklist = new_bl
                    if self.watcher: self.watcher.apply_blacklist(self.blacklist)
                    self.root.after(0, self._update_blacklist_ui)
                
                if (curr_time - self.last_worker_start_time > self.worker_scan_interval):
                    self._save_config_current()
                    self._launch_scanner_subprocess()
                
                if not self.paper_mode.get() and (curr_time - self.last_sync_time > 30):
                    threading.Thread(target=self._sync_real_positions, args=(self.trader,), daemon=True).start()
                    self.last_sync_time = curr_time
                    
                total_floating = 0.0
                has_active_trade = False
                zombies_to_kill = [] 
                
                with self.position_lock:
                    for s, p in self.open_positions.items():
                        if p.get('status') != 'ACTIVE': continue
                        has_active_trade = True
                        if (curr_time - p.get('last_ws_update', 0)) > 60: zombies_to_kill.append(s); continue
                        
                        cp_bid, cp_ask = p['current_price_ws']['bid'], p['current_price_ws']['ask']
                        if cp_bid == 0: continue
                        entry, qty, side = p['entry_price'], p['qty'], p['side']
                        current_price = cp_bid if side == 'LONG' else cp_ask
                        current_pos_pnl = self._calculate_position_pnl(entry, current_price, qty, side)
                        total_floating += current_pos_pnl
                        if current_pos_pnl > p.get('pos_pnl_peak', 0.0):
                             p['pos_pnl_peak'] = current_pos_pnl; p['pos_pnl_last_peak_time'] = curr_time
                
                for s in zombies_to_kill: 
                    self.queue_log(f"WATCHDOG: {s} завис. Закрываю.", "emergency")
                    self._close_position_market(s, "WS Watchdog")
                
                self.floating_pnl.set(f"{total_floating:+.2f}") 
                if has_active_trade: self._check_global_pnl_logic(total_floating, curr_time)
                else: 
                     if not self.pending_orders: self.global_pnl_peak = 0.0 
                time.sleep(2)
            except Exception: time.sleep(5)

    def _launch_scanner_subprocess(self):
        if not os.path.exists(self.worker_lock_file):
            self.queue_log(f"Запуск сканнера...", "info") 
            self.last_worker_start_time = time.time()
            startupinfo = None
            if os.name == 'nt':
                startupinfo = subprocess.STARTUPINFO(); startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            subprocess.Popen([sys.executable, "scanner_worker.py"], startupinfo=startupinfo)
        else:
            try:
                if (time.time() - os.path.getmtime(self.worker_lock_file) > self.worker_lock_watchdog_time):
                    os.remove(self.worker_lock_file)
            except: pass

    def _schedule_ui_updates(self):
        if not self.running.is_set(): self._stop_strategy_ui_threadsafe(); return
        try:
            self.update_metrics(); self.update_balance_metrics(); self.update_open_orders_tree()
            self.chart_system.update_pnl_chart(self.pnl_history, self.total_profit_usd, self.pnl_tab_frame)
            self.root.after(5000, self._schedule_ui_updates)
        except: self.root.after(5000, self._schedule_ui_updates) 

    def trigger_smart_entry(self, symbol, side, suggested_price=None): self.trigger_position_open(symbol, side)

    def trigger_position_open(self, symbol, side, details=None):
        if symbol in self.blacklist: return
        can_trade, reason = self.validate_symbol_for_trading(symbol)
        if not can_trade: return

        with self.position_lock:
            if len(self.open_positions) >= self._get_safe_int(self.max_concurrent_trades, 5): return
            if symbol in self.open_positions: return 
            self.open_positions[symbol] = {'status': 'OPENING', 'details': details} 
        
        self.queue_log(f"ВХОД: {symbol} ({side})", "warning")
        klines = self.trader.get_klines(symbol, self.atr_timeframe_strat.get(), limit=50) 
        if klines and len(klines) > self._get_safe_int(self.atr_period_strat, 14): 
            self._open_and_manage_position(symbol, side, klines, details=details)
        else:
            self._cleanup_failed_open(symbol)

    def _open_and_manage_position(self, symbol, side, klines_atr, entry_override=None, details=None):
        info = self.symbol_info_cache.get(symbol)
        if not info: self._cleanup_failed_open(symbol); return
        try:
            if entry_override is None:
                price = self.trader.get_ticker_price(symbol)
                if not price: self._cleanup_failed_open(symbol); return
                entry_price = price
            else: entry_price = entry_override 
            
            amt_usd = self._get_safe_double(self.trade_amount_usd, 10.0)
            leverage = self._get_safe_int(self.leverage, 20)
            qty_raw = (amt_usd * leverage) / entry_price
            qty = max(qty_raw, info['minQty'])
            
            if self.paper_mode.get():
                cost = (qty * entry_price) / leverage
                if self.paper_quote_balance < cost: self._cleanup_failed_open(symbol); return
                self.add_trade_to_history(symbol, f"{side} (CVD)", entry_price, qty, 0.0)
                self.trade_count += 1
            else:
                self.trader.set_leverage(symbol, leverage)
                api_side = 'BUY' if side == 'LONG' else 'SELL'
                order = self.trader.create_order(symbol, api_side, 'MARKET', quantity=self._format_quantity(qty, info))
                if not order or order.get('status') not in ['FILLED', 'NEW']: self._cleanup_failed_open(symbol); return
                entry_price = float(order.get('avgPrice', entry_price) or entry_price)
                qty = float(order.get('executedQty', qty) or qty)
                self.add_trade_to_history(symbol, f"{side} (Market)", entry_price, qty, 0.0)
                self.trade_count += 1

            pos_data = self._set_sl_and_ts(symbol, info, entry_price, side, qty, klines_atr)
            if not pos_data:
                if not self.paper_mode.get():
                     cl_side = 'SELL' if side == 'LONG' else 'BUY'
                     self.trader.create_order(symbol, cl_side, 'MARKET', quantity=self._format_quantity(qty, info), reduceOnly=True)
                self._cleanup_failed_open(symbol); return
            
            pos_data['pos_pnl_peak'] = 0.0 
            pos_data['pos_pnl_last_peak_time'] = time.time()
            pos_data['details'] = details 

            self._log_to_master_journal("OPEN", symbol, side, entry_price, 0.0, details)

            with self.position_lock: self.open_positions[symbol] = pos_data
            
            # ЗАПИСЬ В ЧЕРНЫЙ ЯЩИК: СТАРТ
            self._record_trade_step(symbol, f"OPEN {side}", entry_price, 0.0, pos_data['sl_price'], f"Qty: {qty}")

            threading.Thread(target=self._position_ws_monitor_loop, args=(symbol, pos_data), daemon=True).start()

        except Exception as e: 
            self.queue_log(f"Err Open {symbol}: {e}", "error")
            self._cleanup_failed_open(symbol)

    def _set_sl_and_ts(self, symbol, info, entry, side, qty, klines):
        atr = self.calculate_atr(klines, self._get_safe_int(self.atr_period_strat, 14))
        if atr == 0: return None
        
        sl_dist = max(self._get_safe_double(self.sl_atr_multiplier, 2.5) * atr, info['tickSize'])
        ts_dist = max(self._get_safe_double(self.ts_atr_multiplier, 1.5) * atr, info['tickSize'])
        sl_raw = (entry - sl_dist) if side == 'LONG' else (entry + sl_dist)
        
        if self.sl_limit_enabled.get():
             limit_pct = self._get_safe_double(self.sl_limit_percent, 1.0) 
             max_dist = entry * (limit_pct / 100.0)
             if side == 'LONG': 
                 if sl_raw < entry - max_dist: sl_raw = entry - max_dist
             else: 
                 if sl_raw > entry + max_dist: sl_raw = entry + max_dist

        sl_price = self._round_price_to_tick_size_DOWN(sl_raw, info) if side == 'LONG' else self._round_price_to_tick_size_UP(sl_raw, info)
        
        pos_data = {
            'side': side, 'entry_price': entry, 'entry_time': time.time(), 'qty': qty, 'sl_price': sl_price, 
            'ts_data': {'distance_usd': ts_dist, 'activation_price': entry, 'current_trail_price': sl_price}, 
            'symbol_info': info, 'current_price_ws': {'bid': 0.0, 'ask': 0.0}, 
            'sl_order_id': None, 'status': 'ACTIVE', 'last_ws_update': time.time(), 'be_applied': False
        }
        
        if not self.paper_mode.get():
            sl_side = 'SELL' if side == 'LONG' else 'BUY'
            params = {
                'symbol': symbol, 'side': sl_side, 'type': 'STOP_MARKET', 
                'quantity': self._format_quantity(qty, info), 
                'stopPrice': self._format_price(sl_price, info), 
                'reduceOnly': 'true', 'workingType': 'MARK_PRICE'
            }
            res = self.trader._send_request('POST', '/fapi/v1/order', params, signed=True)
            if res and res.get('orderId'): pos_data['sl_order_id'] = res['orderId']
            else: return None
            
        self.queue_log(f"SL установлен: {sl_price:.4f}", "info")
        return pos_data

    def _record_trade_step(self, symbol, event, price, pnl, sl_price, info=""):
        try:
            timestamp = dt.datetime.now().strftime("%H:%M:%S")
            date_str = dt.datetime.now().strftime("%Y-%m-%d")
            filename = f"trade_logs/{symbol}_{date_str}.csv"
            file_exists = os.path.isfile(filename)
            with open(filename, 'a', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                if not file_exists: writer.writerow(["Time", "Event", "Price", "PnL", "SL_Price", "Info"])
                writer.writerow([timestamp, event, f"{price:.5f}", f"{pnl:.2f}", f"{sl_price:.5f}", info])
        except Exception: pass

    # ... WS MONITOR ...
    def _position_ws_monitor_loop(self, symbol, pos_data):
        def on_msg(ws, msg):
            try: 
                d = json.loads(msg)
                pos_data['current_price_ws']['bid'] = float(d['b'])
                pos_data['current_price_ws']['ask'] = float(d['a'])
                pos_data['last_ws_update'] = time.time() 
            except: pass
        if not WS_AVAILABLE: return
        ws_url = f"{self.ws_base_url}{symbol.lower()}@bookTicker"
        ws_app = websocket.WebSocketApp(ws_url, on_message=on_msg)
        threading.Thread(target=lambda: ws_app.run_forever(sslopt={"cert_reqs": ssl.CERT_NONE}), daemon=True).start()
        time.sleep(2) 
        
        last_record_time = time.time()

        while self.running.is_set():
            with self.position_lock:
                if symbol not in self.open_positions: break
            cp = pos_data['current_price_ws']
            if cp['bid'] > 0: 
                if self.paper_mode.get(): self._check_paper_sl_ts_v2(symbol, pos_data, cp)
                else: self._check_real_ts_v2(symbol, pos_data, cp)
                
                # Черный ящик
                if time.time() - last_record_time > 1.0:
                    current_p = cp['bid'] if pos_data['side'] == 'LONG' else cp['ask']
                    pnl = self._calculate_position_pnl(pos_data['entry_price'], current_p, pos_data['qty'], pos_data['side'])
                    sl = pos_data['ts_data'].get('current_trail_price', pos_data['sl_price'])
                    self._record_trade_step(symbol, "UPDATE", current_p, pnl, sl)
                    last_record_time = time.time()

            time.sleep(0.5) 
        try: ws_app.close()
        except: pass

    def _check_paper_sl_ts_v2(self, symbol, pos_data, cp):
        side, sl, ts = pos_data['side'], pos_data['sl_price'], pos_data['ts_data']
        bid, ask = cp['bid'], cp['ask']
        entry, qty = pos_data['entry_price'], pos_data['qty']
        current_price = bid if side == 'LONG' else ask
        
        if self.per_pos_tp_enabled.get():
            pnl = self._calculate_position_pnl(entry, current_price, qty, side)
            min_tp = self._get_safe_double(self.per_pos_tp_min_profit_usd, 0.50)
            if pnl >= min_tp and pos_data.get('pos_pnl_peak', 0.0) >= min_tp:
                drop = self._get_safe_double(self.per_pos_peak_drop_pct, 20.0)
                if drop > 0 and pnl < pos_data['pos_pnl_peak'] * (1.0 - drop/100.0):
                    self._close_position_market(symbol, "Trey PnL Drop"); return

        if sl > 0 and ((side=='LONG' and ask<=sl) or (side=='SHORT' and bid>=sl)):
            self._close_position_market(symbol, "Stop Loss"); return

        if self.be_enabled.get() and not pos_data.get('be_applied', False):
            pnl = self._calculate_position_pnl(entry, current_price, qty, side)
            if pnl >= self._get_safe_double(self.be_trigger_profit_usd, 0.5):
                lock = self._get_safe_double(self.be_profit_lock_usd, 0.05)
                prof_per = (lock / qty) if qty else 0
                new_sl = (entry + prof_per) if side == 'LONG' else (entry - prof_per)
                info = pos_data.get('symbol_info', {})
                new_sl = self._round_price_to_tick_size_DOWN(new_sl, info) if side=='LONG' else self._round_price_to_tick_size_UP(new_sl, info)
                if (side == 'LONG' and new_sl > sl) or (side == 'SHORT' and new_sl < sl):
                    pos_data['sl_price'] = new_sl; pos_data['ts_data']['current_trail_price'] = new_sl; pos_data['be_applied'] = True
                    self.queue_log(f"BE Applied {symbol}", "success")
                    self._record_trade_step(symbol, "MOVE_SL (BE)", current_price, pnl, new_sl)

        if side == 'LONG':
            if bid > ts['activation_price']:
                ts['activation_price'] = bid
                new_sl = bid - ts['distance_usd']
                if new_sl > ts['current_trail_price']: ts['current_trail_price'] = new_sl
        else:
            if ask < ts['activation_price']:
                ts['activation_price'] = ask
                new_sl = ask + ts['distance_usd']
                if new_sl < ts['current_trail_price']: ts['current_trail_price'] = new_sl
        
        if ts['current_trail_price'] != sl:
             self._record_trade_step(symbol, "MOVE_SL (Trail)", current_price, 0, ts['current_trail_price'])

        trail = ts['current_trail_price']
        if trail != sl and trail > 0 and ((side=='LONG' and ask<=trail) or (side=='SHORT' and bid>=trail)):
            self._close_position_market(symbol, "Trailing Stop")

    def _check_real_ts_v2(self, symbol, pos_data, cp): self._check_paper_sl_ts_v2(symbol, pos_data, cp)
    def _move_real_sl_v2(self, symbol, new_sl, pos_data, side): pass

    def _close_position_market(self, symbol, reason):
        pos_data = None
        with self.position_lock:
            if symbol not in self.open_positions: return
            if self.open_positions[symbol].get('status') == 'CLOSING': return
            pos_data = self.open_positions.pop(symbol)
        if not pos_data: return
        pos_data['status'] = 'CLOSING'
        
        qty, entry, side = pos_data['qty'], pos_data['entry_price'], pos_data['side']
        cp = pos_data['current_price_ws']['bid'] if side=='LONG' else pos_data['current_price_ws']['ask']
        close_p = cp if cp > 0 else entry
        net = self._calculate_position_pnl(entry, close_p, qty, side, True)
        gross = self._calculate_position_pnl(entry, close_p, qty, side, False)
        
        self.queue_log(f"Закрытие {symbol}: {net:.2f}$ ({reason})", "warning")
        
        self._record_trade_step(symbol, f"CLOSE ({reason})", close_p, net, 0, f"Gross: {gross:.2f}")
        self._log_to_master_journal("CLOSE", symbol, side, close_p, net, pos_data.get('details'))

        try: self.root.after(0, lambda: self.chart_system.save_trade_chart(symbol, self.strategy_timeframe.get(), entry, close_p, side, reason, self.trader))
        except: pass

        if self.paper_mode.get():
            self.total_profit_usd += net; self.paper_quote_balance += net
            self.pnl_history.append((dt.datetime.now(), self.total_profit_usd))
            self.add_trade_to_history(symbol, f"{'SELL' if side=='LONG' else 'BUY'} (Close)", close_p, qty, net)
        else:
            if pos_data.get('sl_order_id'): 
                try: self.trader.cancel_order(symbol, pos_data.get('sl_order_id'))
                except: pass
            c_side = 'SELL' if side=='LONG' else 'BUY'
            self.trader.create_order(symbol, c_side, 'MARKET', quantity=self._format_quantity(qty, pos_data['symbol_info']), reduceOnly=True)
            self.add_trade_to_history(symbol, f"{c_side} (Close)", "N/A", qty, "N/A")
            self.last_sync_time = 0 
        self.trade_count += 1

    # ... Остальные методы ...
    def _save_config_current(self):
        cfg = {
            'trade_amount_usd': self._get_safe_double(self.trade_amount_usd), 'leverage': self._get_safe_int(self.leverage),
            'scanner_liquidity_filter': self._get_safe_double(self.scanner_liquidity_filter), 'scanner_timeframe': self.scanner_timeframe.get(),
            'api_key': self.api_key.get(), 'api_secret': self.api_secret.get(), 'paper_start_balance': self._get_safe_double(self.paper_start_balance),
            'max_concurrent_trades': self._get_safe_int(self.max_concurrent_trades), 'strategy_timeframe': self.strategy_timeframe.get(),
            'atr_timeframe_strat': self.atr_timeframe_strat.get(), 'atr_period_strat': self._get_safe_int(self.atr_period_strat),
            'sl_atr_multiplier': self._get_safe_double(self.sl_atr_multiplier), 'ts_atr_multiplier': self._get_safe_double(self.ts_atr_multiplier),
            'per_pos_tp_enabled': self.per_pos_tp_enabled.get(), 'global_tp_enabled': self.global_tp_enabled.get(), 'trailing_pnl_enabled': self.trailing_pnl_enabled.get(),
            'cvd_scan_timeframe': self.cvd_scan_timeframe.get(), 'cvd_min_rvol': self._get_safe_double(self.cvd_min_rvol),
            'cvd_min_strength': self._get_safe_int(self.cvd_min_strength), 'cvd_min_rr': self._get_safe_double(self.cvd_min_rr),
            'cvd_max_signals': self._get_safe_int(self.cvd_max_signals), 'cvd_min_price_pct': self._get_safe_double(self.cvd_min_price_pct),
            'cvd_min_cvd_pct': self._get_safe_double(self.cvd_min_cvd_pct),
        }
        self.config_handler.save_config_for_worker(cfg)
    def _get_safe_int(self, var, default=0):
        try: return int(var.get()) if hasattr(var,'get') else int(var)
        except: return default
    def _get_safe_double(self, var, default=0.0):
        try: return float(var.get()) if hasattr(var,'get') else float(var)
        except: return default
    def _format_quantity(self, n, i): return f"{n:.{i['quantityPrecision']}f}"
    def _format_price(self, n, i): return f"{n:.{i['pricePrecision']}f}"
    def _round_price_to_tick_size_DOWN(self, p, i): 
        tick = i.get('tickSize', 0.0); return (p // tick) * tick if tick > 0 else p
    def _round_price_to_tick_size_UP(self, p, i): 
        tick = i.get('tickSize', 0.0); return math.ceil(p / tick) * tick if tick > 0 else p
    def _calculate_position_pnl(self, ep, cp, qty, side, include_fees=True):
        gross = (cp - ep) * qty if side == 'LONG' else (ep - cp) * qty
        fee = (ep * qty * 0.0004) * 2 
        return (gross - fee) if include_fees else gross
    def validate_symbol_for_trading(self, symbol):
        if symbol in self.blacklist: return False, "Blacklist"
        if not self.trader: return False, "No Trader"
        return True, "OK"
    def calculate_atr(self, klines, period):
        try:
            closes = [float(x[4]) for x in klines]; highs = [float(x[2]) for x in klines]; lows = [float(x[3]) for x in klines]
            if len(closes) < period + 1: return 0.0
            tr_values = [max(highs[i]-lows[i], abs(highs[i]-closes[i-1]), abs(lows[i]-closes[i-1])) for i in range(1, len(closes))]
            return float(np.mean(tr_values[-period:]))
        except: return 0.0
    def add_trade_to_history(self, s, ty, p, q, pnl, fee=None):
        if not self.trade_history_tree: return
        def _add():
            try: self.trade_history_tree.insert('','0', values=(dt.datetime.now().strftime("%H:%M:%S"), s, ty, f"{p:.4f}", f"{q:.4f}", f"{pnl:+.4f}"))
            except: pass
        self.root.after(0, _add)
    def _trigger_global_close(self, reason):
        with self.position_lock: syms = list(self.open_positions.keys())
        for s in syms: threading.Thread(target=self._close_position_market, args=(s, reason), daemon=True).start()
    
    # --- Исправленные обработчики (Split lines) ---
    def _on_blacklist_double_click(self, e):
        try:
            sel = self.blacklist_listbox.curselection()
            if not sel: return
            sym = self.blacklist_listbox.get(sel[0])
            if messagebox.askyesno("Delete", f"Удалить {sym}?"):
                self.blacklist.remove(sym)
                self.config_handler.save_blacklist(self.blacklist)
                self._update_blacklist_ui()
        except: pass

    def _on_history_double_click(self, e):
        try:
            item = self.trade_history_tree.identify_row(e.y)
            if not item: return
            sym = self.trade_history_tree.item(item, 'values')[1]
            if messagebox.askyesno("Ban", f"В Blacklist {sym}?"):
                self.blacklist.add(sym)
                self.config_handler.save_blacklist(self.blacklist)
                self._update_blacklist_ui()
        except: pass

    def _on_open_orders_double_click(self, e):
        try:
            item = self.open_orders_tree.identify_row(e.y)
            if not item: return
            sym = self.open_orders_tree.item(item, 'values')[0].replace('⏳ ', '').strip()
            if sym: webbrowser.open(f"https://www.binance.com/ru-UA/futures/{sym}")
        except: pass

    def _update_blacklist_ui(self):
        if not self.blacklist_listbox: return
        self.blacklist_listbox.delete(0, tk.END)
        for s in sorted(list(self.blacklist)): 
            self.blacklist_listbox.insert(tk.END, s)
            self.blacklist_listbox.itemconfig(tk.END, {'bg': '#300000', 'fg': '#FFC0C0'})
        if hasattr(self, 'tab_blacklist'): 
            self.notebook.tab(self.tab_blacklist, text=f'⛔ Чёрный список ({len(self.blacklist)})')

    def start_scanner_thread(self):
        self._save_config_current()
        self.btn_scan.config(state=tk.DISABLED)
        self._launch_scanner_subprocess()
        self.root.after(5000, lambda: self.btn_scan.config(state=tk.NORMAL))

    def copy_log(self):
        try: 
            self.root.clipboard_clear()
            self.root.clipboard_append(self.log_text.get('1.0', tk.END))
            self.queue_log("Лог скопирован", "success")
        except: pass

    def copy_trade_history(self):
        try: 
            c = "\n".join([",".join(map(str,self.trade_history_tree.item(i,'values'))) for i in self.trade_history_tree.get_children('')])
            self.root.clipboard_clear()
            self.root.clipboard_append(c)
            self.queue_log("История скопирована", "success")
        except: pass

    def toggle_mode(self):
        if self.running.is_set(): 
            self.queue_log("Нельзя менять режим на ходу", "warning")
            self.paper_mode.set(not self.paper_mode.get())
            return
        if not self.paper_mode.get() and self.first_real_mode_warning:
             if not messagebox.askyesno("РИСК", "Включить РЕАЛ?"): self.paper_mode.set(True); return
             self.first_real_mode_warning = False
        self.queue_log(f"РЕЖИМ: {'PAPER' if self.paper_mode.get() else 'REAL'}", "warning")
        self.reset_history()

    def reset_history(self):
        if not messagebox.askyesno("Сброс", "Сбросить статистику?"): return
        self.total_profit_usd = 0.0
        self.trade_count = 0
        self.pnl_history.clear()
        self.global_pnl_peak = 0.0
        if self.trade_history_tree: self.trade_history_tree.delete(*self.trade_history_tree.get_children())
        self.chart_system.update_pnl_chart([], 0, self.pnl_tab_frame)
        self.queue_log("♻️ Сброс статистики выполнен", "warning")

    def save_pnl_chart(self):
        try: 
            self.chart_system.pnl_fig.savefig(f"pnl_{dt.datetime.now():%H%M%S}.png")
            self.queue_log("PnL сохранен", "success")
        except: pass

    def load_api_keys_from_file(self):
        try:
            with open('binance_keys.txt','r', encoding='utf-8-sig') as f:
                self.api_key.set(f.readline().strip())
                self.api_secret.set(f.readline().strip())
            self.load_keys_flag.set(True)
        except: pass

    def toggle_load_keys(self):
        if self.load_keys_flag.get(): self.load_api_keys_from_file()

    def update_metrics(self):
        try:
            if not self.metric_vars: return
            self.metric_vars['Режим'].set("ТЕСТ" if self.paper_mode.get() else "РЕАЛ")
            self.metric_vars['Общий PnL ($)'].set(f"{self.total_profit_usd:+.2f}")
            with self.position_lock: num = len(self.open_positions) + len(self.pending_orders)
            self.metric_vars['Открыто Позиций'].set(f"{num} / {self.max_concurrent_trades.get()}")
        except: pass

    def update_balance_metrics(self):
        try:
            if not self.metric_vars: return
            b = self.paper_quote_balance if self.paper_mode.get() else self.real_quote_balance
            self.metric_vars['Баланс QUOTE'].set(f"{b:.2f} USDT")
        except: pass

    def update_open_orders_tree(self):
        if not self.open_orders_tree: return
        try:
            self.open_orders_tree.delete(*self.open_orders_tree.get_children())
            with self.position_lock: positions_copy=list(self.open_positions.items())
            for symbol, p in positions_copy:
                 if p.get('status') == 'ACTIVE':
                     info = p.get('symbol_info', {})
                     prec = info.get('pricePrecision', 4)
                     cp = p['current_price_ws']['bid'] if p['side'] == 'LONG' else p['current_price_ws']['ask']
                     pnl = self._calculate_position_pnl(p['entry_price'], cp, p['qty'], p['side'])
                     vals = (symbol, p['side'], f"{p['qty']}", f"{p['entry_price']:.{prec}f}", f"{p['sl_price']:.{prec}f}", "ACTIVE", f"{pnl:+.2f}")
                     self.open_orders_tree.insert('','end', values=vals)
        except: pass

    def start_periodic_updates(self):
        try:
            limit = 50
            while not self.log_queue.empty() and limit > 0:
                msg, lvl = self.log_queue.get_nowait()
                if self.log_text: 
                    self.log_text.insert(tk.END, f"[{dt.datetime.now():%H:%M:%S}] {msg}\n")
                    self.log_text.see(tk.END)
                limit -= 1
            while not self.scanner_queue.empty(): self.scanner_queue.get_nowait()
        except: pass
        self.root.after(200, self.start_periodic_updates)

    def close_all_market_emergency(self):
        if messagebox.askyesno("АВАРИЯ", "Закрыть ВСЕ позиции?"): self._trigger_global_close("MANUAL EMERGENCY")

    def _stop_strategy_ui_threadsafe(self):
        self.running.clear()
        if self.btn_start: 
            self.root.after(0, lambda: self.btn_start.config(state=tk.NORMAL))
            self.root.after(0, lambda: self.btn_stop.config(state=tk.DISABLED))
            self.root.after(0, lambda: self.status_label.config(text="Остановлено (Ошибка)"))

    def on_closing(self):
        self.stop_strategy()
        time.sleep(0.5)
        try: self.root.destroy()
        except: pass

    def _cleanup_failed_open(self, symbol):
        with self.position_lock:
            if symbol in self.open_positions: del self.open_positions[symbol]

if __name__ == "__main__":
    try:
        root = tk.Tk()
        app = MomentumApp(root)
        root.protocol("WM_DELETE_WINDOW", app.on_closing)
        root.mainloop()
    except Exception as e:
        print(f"CRITICAL ERROR: {e}")
        import traceback
        traceback.print_exc()