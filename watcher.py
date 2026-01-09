# watcher.py
# V10.11 - CVD WATCHER (Data Relay)
#
# ИЗМЕНЕНИЯ V10.11:
# - ✅ Читает расширенный формат JSON от сканера.
# - ✅ Передает данные о Силе, CVD% и Price% в Main бот.

import threading
import time
import json
import os
from typing import Dict, Optional

STATUS_ENTRY = "ENTRY"
STATUS_WAIT = "WAIT"
STATUS_EXPIRED = "EXPIRED"
STATUS_REJECTED = "REJECTED"

class Watcher:
    def __init__(self, app):
        self.app = app
        self.log = app.queue_log
        self.watchlist = {}
        self.lock = threading.Lock()
        self.running = False
        self.thread = None
        self.watchlist_file = "watchlist.json"
        self.last_mtime = 0
        
        self.cooldown_until = {}
        
    def start(self):
        if not self.running:
            self.running = True
            self.thread = threading.Thread(target=self._loop, daemon=True)
            self.thread.start()
    
    def stop(self):
        self.running = False
        if self.thread: self.thread.join(timeout=1)
    
    def apply_blacklist(self, bl):
        with self.lock:
            for s in list(self.watchlist.keys()):
                if s in bl: del self.watchlist[s]

    def _load_watchlist(self):
        if not os.path.exists(self.watchlist_file): return
        try:
            mtime = os.path.getmtime(self.watchlist_file)
            if mtime <= self.last_mtime or os.path.getsize(self.watchlist_file) == 0: return
            
            with open(self.watchlist_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            self.last_mtime = mtime
            current_time = time.time()
            
            with self.lock:
                for symbol, info in data.items():
                    if symbol in self.watchlist: continue
                    if symbol in getattr(self.app, 'blacklist', set()): continue
                    
                    # V10.11: Поддержка и старого (строка) и нового (dict) формата
                    if isinstance(info, str):
                        regime = info
                        details = {}
                    else:
                        regime = info.get('regime', '')
                        details = info # Весь словарь с данными
                        
                    if not regime.startswith("CVD_"): continue
                    
                    self.watchlist[symbol] = {
                        'signal_type': regime.replace("CVD_", ""),
                        'timestamp': current_time,
                        'attempts': 0,
                        'details': details # Сохраняем детали для лога
                    }
        except: pass

    def _loop(self):
        while self.running:
            self._load_watchlist()
            
            # Очистка кулдаунов
            now = time.time()
            self.cooldown_until = {s:t for s,t in self.cooldown_until.items() if now < t}
            
            with self.lock: targets = list(self.watchlist.items())
            
            for symbol, data in targets:
                if not self.running: break
                if symbol in self.cooldown_until: continue
                
                # Простая логика входа (без лишних проверок, так как сканер уже проверил)
                # Проверяем только слоты и дубликаты
                
                res = self._check_entry(symbol)
                if res == STATUS_ENTRY:
                    # ! V10.11: Передаем details (Силу и прочее) в Main !
                    self.app.trigger_position_open(symbol, data['signal_type'], data.get('details', {}))
                    
                    self.cooldown_until[symbol] = time.time() + 600
                    with self.lock: del self.watchlist[symbol]
                
                elif res in (STATUS_REJECTED, STATUS_EXPIRED):
                    with self.lock: del self.watchlist[symbol]
            
            time.sleep(1)

    def _check_entry(self, symbol):
        # Проверка возраста (15 мин)
        # Проверка наличия позиции
        with self.app.position_lock:
            if symbol in self.app.open_positions or symbol in self.app.pending_orders:
                return STATUS_REJECTED
            if len(self.app.open_positions) >= self.app._get_safe_int(self.app.max_concurrent_trades, 5):
                return STATUS_WAIT
        return STATUS_ENTRY