# cvd_strategy.py
# V10.6 - SMART SCORING
#
# ИЗМЕНЕНИЯ V10.6:
# - ✅ Исправлен расчет силы (Strength): теперь используется логарифмическая шкала.
# - ✅ Гигантские проценты CVD (1000%+) больше не ломают шкалу, упираясь в 100.
# - ✅ Сила 100 теперь означает действительно мощный, подтвержденный сигнал.

import numpy as np
import time
import math
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from enum import Enum


class SignalType(Enum):
    LONG = "LONG"
    SHORT = "SHORT"
    NONE = "NONE"


@dataclass
class DivergenceSignal:
    """Структура сигнала дивергенции"""
    symbol: str
    signal_type: SignalType
    strength: float
    price_change_pct: float
    cvd_change_pct: float
    entry_price: float
    stop_loss: float
    take_profit: float
    timestamp: float
    
    def risk_reward_ratio(self) -> float:
        if self.signal_type == SignalType.LONG:
            risk = self.entry_price - self.stop_loss
            reward = self.take_profit - self.entry_price
        else:
            risk = self.stop_loss - self.entry_price
            reward = self.entry_price - self.take_profit
        
        if risk <= 0: return 0
        return reward / risk


class CVDStrategy:
    def __init__(self, trader, log_callback=print):
        self.trader = trader
        self.log = log_callback
        
        # Дефолтные настройки (будут перезаписаны из конфига)
        self.min_rvol = 1.5
        self.min_liquidity = 500_000
        self.scan_timeframe = "15m"
        
        self.divergence_lookback = 50
        self.recent_window = 12
        self.past_window_start = 45
        self.past_window_end = 18
        self.min_divergence_distance = 10
        
        self.min_price_change_pct = 0.5
        self.min_cvd_change_pct = 5.0
        self.min_divergence_strength = 30
        
        self.risk_percent = 1.5
        self.min_rr_ratio = 1.5
        self.sl_atr_multiplier = 2.0
        self.tp_atr_multiplier = 3.0
        
        self._cache: Dict[str, Tuple[float, Any]] = {}
        self._cache_ttl = 60
        
    def _get_klines_data(self, symbol: str, tf: str, limit: int = 100) -> Optional[Dict]:
        try:
            klines = self.trader.get_klines(symbol, tf, limit)
            if not klines or len(klines) < 50: return None
            
            opens = np.array([float(k[1]) for k in klines])
            highs = np.array([float(k[2]) for k in klines])
            lows = np.array([float(k[3]) for k in klines])
            closes = np.array([float(k[4]) for k in klines])
            volumes = np.array([float(k[5]) for k in klines])
            quote_volumes = np.array([float(k[7]) for k in klines])
            taker_buy_volumes = np.array([float(k[9]) for k in klines])
            
            sell_volumes = volumes - taker_buy_volumes
            deltas = taker_buy_volumes - sell_volumes
            cvd = np.cumsum(deltas)
            
            avg_vol = np.mean(volumes)
            cvd_normalized = cvd / avg_vol if avg_vol > 0 else cvd
            
            tr = np.maximum(highs - lows, np.maximum(np.abs(highs - np.roll(closes, 1)), np.abs(lows - np.roll(closes, 1))))
            tr[0] = highs[0] - lows[0]
            atr = np.mean(tr[-14:])
            
            current_vol = quote_volumes[-1]
            avg_vol_20 = np.mean(quote_volumes[-21:-1])
            rvol = current_vol / avg_vol_20 if avg_vol_20 > 0 else 0
            
            return {
                'opens': opens, 'highs': highs, 'lows': lows, 'closes': closes,
                'volumes': volumes, 'quote_volumes': quote_volumes,
                'cvd': cvd, 'cvd_normalized': cvd_normalized, 'deltas': deltas,
                'atr': atr, 'rvol': rvol, 'current_price': closes[-1]
            }
        except: return None

    def find_divergence(self, symbol: str, tf: str = None) -> Optional[DivergenceSignal]:
        if tf is None: tf = self.scan_timeframe
        try:
            cache_key = f"{symbol}_{tf}_div"
            if cache_key in self._cache:
                timestamp, result = self._cache[cache_key]
                if time.time() - timestamp < self._cache_ttl: return result
            
            data = self._get_klines_data(symbol, tf, self.divergence_lookback + 10)
            if data is None: return None
            
            closes, cvd, atr = data['closes'], data['cvd_normalized'], data['atr']
            current_price = data['current_price']
            
            if len(closes) < self.divergence_lookback: return None
            
            bullish = self._find_bullish_divergence(closes, cvd)
            bearish = self._find_bearish_divergence(closes, cvd)
            
            signal = None
            if bullish and bearish:
                signal = bullish if bullish['strength'] > bearish['strength'] else bearish
            elif bullish: signal = bullish
            elif bearish: signal = bearish
            
            if signal is None or signal['strength'] < self.min_divergence_strength:
                self._cache[cache_key] = (time.time(), None)
                return None
            
            signal_type = SignalType.LONG if signal['type'] == 'BULLISH' else SignalType.SHORT
            
            if signal_type == SignalType.LONG:
                entry_price = current_price
                stop_loss = current_price - (atr * self.sl_atr_multiplier)
                take_profit = current_price + (atr * self.tp_atr_multiplier)
            else:
                entry_price = current_price
                stop_loss = current_price + (atr * self.sl_atr_multiplier)
                take_profit = current_price - (atr * self.tp_atr_multiplier)
            
            result = DivergenceSignal(
                symbol=symbol, signal_type=signal_type, strength=signal['strength'],
                price_change_pct=signal['price_change_pct'], cvd_change_pct=signal['cvd_change_pct'],
                entry_price=entry_price, stop_loss=stop_loss, take_profit=take_profit, timestamp=time.time()
            )
            
            if result.risk_reward_ratio() < self.min_rr_ratio:
                self._cache[cache_key] = (time.time(), None)
                return None
            
            self._cache[cache_key] = (time.time(), result)
            return result
        except: return None

    def _calculate_smart_strength(self, price_pct, cvd_pct):
        """
        Умный расчет силы сигнала.
        Сглаживает гигантские всплески CVD с помощью логарифма.
        """
        # 1. Очки за изменение цены (Линейно)
        # 1% движения цены = 25 очков силы (макс 50)
        price_score = min(50, abs(price_pct) * 25)
        
        # 2. Очки за CVD (Логарифмически)
        # CVD 10% -> ~20 очков
        # CVD 100% -> ~40 очков
        # CVD 1000% -> ~60 очков
        # Это убирает проблему "4000% = 10000 очков"
        try:
            cvd_abs = abs(cvd_pct)
            if cvd_abs < 1: cvd_score = cvd_abs * 2 # Для малых значений линейно
            else: cvd_score = math.log10(cvd_abs) * 20
        except: cvd_score = 0
        
        # Суммируем и ограничиваем
        total_strength = min(100, price_score + cvd_score)
        return total_strength

    def _find_bullish_divergence(self, closes: np.ndarray, cvd: np.ndarray) -> Optional[Dict]:
        try:
            recent_start, recent_end = -(self.recent_window + 1), -1
            recent_low_idx = np.argmin(closes[recent_start:recent_end])
            recent_low_price = closes[recent_start:recent_end][recent_low_idx]
            recent_low_cvd = cvd[recent_start:recent_end][recent_low_idx]
            
            past_start, past_end = -self.past_window_start, -self.past_window_end
            past_low_idx = np.argmin(closes[past_start:past_end])
            past_low_price = closes[past_start:past_end][past_low_idx]
            past_low_cvd = cvd[past_start:past_end][past_low_idx]
            
            dist = (len(closes) + recent_start + recent_low_idx) - (len(closes) + past_start + past_low_idx)
            if dist < self.min_divergence_distance: return None
            
            # Динамические проверки
            price_threshold = past_low_price * (1.0 - (self.min_price_change_pct / 100.0))
            if recent_low_price >= price_threshold: return None
            
            cvd_diff_needed = abs(past_low_cvd) * (self.min_cvd_change_pct / 100.0)
            if recent_low_cvd <= (past_low_cvd + cvd_diff_needed): return None
            
            # Расчет процентов
            price_drop_pct = abs((recent_low_price - past_low_price) / past_low_price * 100)
            cvd_rise_pct = (recent_low_cvd - past_low_cvd) / (abs(past_low_cvd) + 0.001) * 100
            
            # Умная сила
            strength = self._calculate_smart_strength(price_drop_pct, cvd_rise_pct)
            
            return {'type': 'BULLISH', 'strength': strength, 'price_change_pct': -price_drop_pct, 'cvd_change_pct': cvd_rise_pct}
        except: return None

    def _find_bearish_divergence(self, closes: np.ndarray, cvd: np.ndarray) -> Optional[Dict]:
        try:
            recent_start, recent_end = -(self.recent_window + 1), -1
            recent_high_idx = np.argmax(closes[recent_start:recent_end])
            recent_high_price = closes[recent_start:recent_end][recent_high_idx]
            recent_high_cvd = cvd[recent_start:recent_end][recent_high_idx]
            
            past_start, past_end = -self.past_window_start, -self.past_window_end
            past_high_idx = np.argmax(closes[past_start:past_end])
            past_high_price = closes[past_start:past_end][past_high_idx]
            past_high_cvd = cvd[past_start:past_end][past_high_idx]
            
            dist = (len(closes) + recent_start + recent_high_idx) - (len(closes) + past_start + past_high_idx)
            if dist < self.min_divergence_distance: return None
            
            # Динамические проверки
            price_threshold = past_high_price * (1.0 + (self.min_price_change_pct / 100.0))
            if recent_high_price <= price_threshold: return None
            
            cvd_diff_needed = abs(past_high_cvd) * (self.min_cvd_change_pct / 100.0)
            if recent_high_cvd >= (past_high_cvd - cvd_diff_needed): return None
            
            # Расчет процентов
            price_rise_pct = abs((recent_high_price - past_high_price) / past_high_price * 100)
            cvd_drop_pct = (past_high_cvd - recent_high_cvd) / (abs(past_high_cvd) + 0.001) * 100
            
            # Умная сила
            strength = self._calculate_smart_strength(price_rise_pct, cvd_drop_pct)
            
            return {'type': 'BEARISH', 'strength': strength, 'price_change_pct': price_rise_pct, 'cvd_change_pct': -cvd_drop_pct}
        except: return None

    def scan_market(self, blacklist: set = None) -> List[DivergenceSignal]:
        if blacklist is None: blacklist = set()
        signals = []
        try:
            tickers = self.trader.get_24h_tickers()
            if not tickers: return signals
            candidates = [t['symbol'] for t in tickers if t['symbol'].endswith('USDT') and t['symbol'] not in blacklist and float(t.get('quoteVolume', 0)) >= self.min_liquidity]
            
            total = len(candidates)
            for i, symbol in enumerate(candidates):
                if i % 50 == 0: self.log(f"CVD Scan: {i}/{total}...", "info")
                signal = self.find_divergence(symbol)
                if signal: signals.append(signal)
                time.sleep(0.01)
            
            signals.sort(key=lambda x: x.strength, reverse=True)
            self.log(f"CVD Strategy: Найдено {len(signals)} сигналов", "success")
            return signals
        except Exception as e:
            self.log(f"Scan error: {e}", "error"); return signals

    def get_cvd_trend(self, symbol: str, tf: str = "15m", lookback: int = 20) -> Optional[str]:
        try:
            data = self._get_klines_data(symbol, tf, lookback + 5)
            if not data: return None
            cvd = data['cvd_normalized']
            if len(cvd) < 5: return None
            slope = (cvd[-1] - cvd[-5]) / 5
            return "UP" if slope > 0.05 else "DOWN" if slope < -0.05 else None
        except: return None