# scanner_worker.py
# V10.11 - CVD DIVERGENCE HUNTER (Rich Data)
#
# ИЗМЕНЕНИЯ V10.11:
# - ✅ Сохраняет полную информацию о сигнале (Сила, RVOL, CVD%, Price%) в watchlist.json.
# - ✅ Это позволяет Главному боту записывать эти данные в Журнал сделок.

import sys
import os
import json
import time
import logging
from datetime import datetime

# === ЛОГИРОВАНИЕ ===
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    handlers=[logging.FileHandler('scanner_worker.log', encoding='utf-8'), logging.StreamHandler()]
)
log = logging.getLogger(__name__)

# === ИМПОРТЫ ===
try:
    import win7_core
    win7_core.apply_patches()
except ImportError: pass

try:
    from binance_api import BinanceTrader
    from cvd_strategy import CVDStrategy, SignalType
except ImportError as e:
    log.error(f"Error imports: {e}"); sys.exit(1)

# === КОНФИГУРАЦИЯ ===
class ScannerConfig:
    WATCHLIST_FILE = "watchlist.json"
    LOCK_FILE = "watchlist.lock"
    BLACKLIST_FILE = "blacklist.json"
    CONFIG_FILE = "config.json"
    
    MIN_LIQUIDITY = 100000
    MIN_RVOL = 0.5
    SCAN_TIMEFRAME = "5m"
    MIN_DIVERGENCE_STRENGTH = 10
    MIN_RR_RATIO = 1.0
    MAX_SIGNALS = 5
    MIN_PRICE_CHANGE_PCT = 0.05
    MIN_CVD_CHANGE_PCT = 0.5
    
    @classmethod
    def load_from_file(cls):
        try:
            if os.path.exists(cls.CONFIG_FILE):
                with open(cls.CONFIG_FILE, 'r', encoding='utf-8') as f:
                    cfg = json.load(f)
                    cls.MIN_LIQUIDITY = cfg.get('scanner_liquidity_filter', cls.MIN_LIQUIDITY)
                    cls.MIN_RVOL = cfg.get('cvd_min_rvol', cls.MIN_RVOL)
                    cls.SCAN_TIMEFRAME = cfg.get('cvd_scan_timeframe', cls.SCAN_TIMEFRAME)
                    cls.MIN_DIVERGENCE_STRENGTH = cfg.get('cvd_min_strength', cls.MIN_DIVERGENCE_STRENGTH)
                    cls.MIN_RR_RATIO = cfg.get('cvd_min_rr', cls.MIN_RR_RATIO)
                    cls.MAX_SIGNALS = cfg.get('cvd_max_signals', cls.MAX_SIGNALS)
                    cls.MIN_PRICE_CHANGE_PCT = cfg.get('cvd_min_price_pct', cls.MIN_PRICE_CHANGE_PCT)
                    cls.MIN_CVD_CHANGE_PCT = cfg.get('cvd_min_cvd_pct', cls.MIN_CVD_CHANGE_PCT)
                    log.info(f"Config: RVOL>{cls.MIN_RVOL}, Str>{cls.MIN_DIVERGENCE_STRENGTH}, P%>{cls.MIN_PRICE_CHANGE_PCT}, C%>{cls.MIN_CVD_CHANGE_PCT}")
        except: pass

def load_blacklist() -> set:
    try:
        if os.path.exists(ScannerConfig.BLACKLIST_FILE):
            with open(ScannerConfig.BLACKLIST_FILE, 'r', encoding='utf-8') as f: return set(json.load(f))
    except: pass
    return set()

def load_api_keys() -> tuple:
    try:
        if os.path.exists('binance_keys.txt'):
            with open('binance_keys.txt', 'r', encoding='utf-8-sig') as f: return f.readline().strip(), f.readline().strip()
    except: pass
    return "", ""

def save_watchlist(signals: list):
    try:
        watchlist = {}
        for sig in signals:
            # V10.11: СОХРАНЯЕМ ПОЛНЫЙ ПАКЕТ ДАННЫХ
            watchlist[sig.symbol] = {
                "regime": f"CVD_{sig.signal_type.value}",
                "strength": sig.strength,
                "price_pct": sig.price_change_pct,
                "cvd_pct": sig.cvd_change_pct,
                "timestamp": sig.timestamp
            }
        
        tmp_file = ScannerConfig.WATCHLIST_FILE + ".tmp"
        with open(tmp_file, 'w', encoding='utf-8') as f: json.dump(watchlist, f, indent=2)
        if os.path.exists(ScannerConfig.WATCHLIST_FILE): os.remove(ScannerConfig.WATCHLIST_FILE)
        os.rename(tmp_file, ScannerConfig.WATCHLIST_FILE)
        
        if signals:
            log.info(f"[SUCCESS] ✅ Watchlist: {len(watchlist)} целей")
            
    except Exception as e: log.error(f"Watchlist save error: {e}")

def log_adapter(msg, level="info"):
    if level == "error": log.error(msg)
    elif level == "warning": log.warning(msg)
    elif level == "success": log.info(f"✅ {msg}")
    else: log.info(msg)

def run_scanner():
    log.info(f"--- CVD SCANNER V10.11 START ---")
    ScannerConfig.load_from_file()
    
    try:
        with open(ScannerConfig.LOCK_FILE, 'w') as f: f.write(str(time.time()))
    except: pass
    
    try:
        k, s = load_api_keys()
        trader = BinanceTrader(k, s, log_adapter, use_ssl_verify=False)
        if not trader.get_24h_tickers(): return
        
        strategy = CVDStrategy(trader, log_adapter)
        strategy.min_rvol = ScannerConfig.MIN_RVOL
        strategy.min_liquidity = ScannerConfig.MIN_LIQUIDITY
        strategy.scan_timeframe = ScannerConfig.SCAN_TIMEFRAME
        strategy.min_divergence_strength = ScannerConfig.MIN_DIVERGENCE_STRENGTH
        strategy.min_rr_ratio = ScannerConfig.MIN_RR_RATIO
        strategy.min_price_change_pct = ScannerConfig.MIN_PRICE_CHANGE_PCT
        strategy.min_cvd_change_pct = ScannerConfig.MIN_CVD_CHANGE_PCT
        
        log.info("🔍 Scanning...")
        signals = strategy.scan_market(load_blacklist())
        
        if not signals:
            log.info("❌ No signals")
            save_watchlist([])
            return
        
        top = signals[:ScannerConfig.MAX_SIGNALS]
        for i, sig in enumerate(top, 1):
            emoji = "🟢" if sig.signal_type == SignalType.LONG else "🔴"
            log.info(f"{emoji} #{i} {sig.symbol} | S:{sig.strength:.0f} | P:{sig.price_change_pct:+.2f}% | C:{sig.cvd_change_pct:+.1f}%")
        
        save_watchlist(top)
        
    except Exception as e: log.error(f"Critical: {e}")
    finally:
        if os.path.exists(ScannerConfig.LOCK_FILE): 
            try: os.remove(ScannerConfig.LOCK_FILE)
            except: pass

if __name__ == "__main__": run_scanner()