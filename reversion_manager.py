# reversion_manager.py
# V9.25 (Restored & Optimized)
#
# Модуль отвечает за:
# 1. Расчет границ канала (Bollinger Bands) для определения Flat/Trend.
# 2. Фильтрацию параболических движений (защита от входа на хаях).
# 3. Расчет угла наклона тренда (Slope) для Watcher'а.

import pandas as pd
import numpy as np
import threading
import time
from typing import List, Dict, Any, Optional

class ReversionManager:
    def __init__(self, app, trader):
        self.app = app 
        self.trader = trader 
        self.log = app.queue_log 
        self.kline_limit = 100 

    def check_parabolic_volatility(self, symbol: str) -> bool:
        """
        Проверяет, не является ли последнее движение аномально резким (Парабола).
        Защищает от входа в сделку в самый разгар пампа/дампа, когда риск разворота максимален.
        """
        try:
            # Читаем настройки множителя из GUI
            multiplier = self.app._get_safe_double(self.app.parabolic_atr_multiplier, 3.0)
            if multiplier <= 0: 
                return False # Фильтр отключен
            
            tf = self.app.strategy_timeframe.get()
            
            # Запрашиваем свечи (нужно немного для расчета ATR)
            klines = self.trader.get_klines(symbol, tf, 25)
            if not klines or len(klines) < 20: 
                return False
            
            # Считаем размер каждой свечи (High - Low)
            ranges = [float(k[2]) - float(k[3]) for k in klines]
            
            # Размер последней закрытой свечи
            current_range = ranges[-2] 
            
            # Средний размер за предыдущие 14 свечей (ATR approximation)
            avg_range = np.mean(ranges[-16:-2]) 
            
            # Если текущая свеча в X раз больше средней -> Парабола
            if avg_range > 0 and current_range > (avg_range * multiplier):
                # self.log(f"{symbol}: Параболическое движение! Range {current_range:.4f} > {multiplier}x ATR", "info")
                return True
                
            return False
            
        except Exception as e:
            # self.log(f"Parabolic Check Error {symbol}: {e}", "error")
            return False

    def get_channel_limits(self, symbol: str) -> Optional[Dict[str, float]]:
        """
        Расчет границ канала (Bollinger Bands).
        Используется Снайпером (Watcher) для определения точек входа во флэте
        и для выставления Take Profit / Stop Loss.
        """
        try:
            # Параметры из GUI
            tf = self.app.trend_mid_tf.get() # Обычно 15m для канала
            period = self.app._get_safe_int(self.app.rev_bb_period, 20)
            std_dev_mult = self.app._get_safe_double(self.app.rev_bb_std_dev, 2.0)
            
            klines = self.trader.get_klines(symbol, tf, period + 10)
            if not klines or len(klines) < period: 
                return None
            
            closes = [float(k[4]) for k in klines]
            df = pd.DataFrame(closes, columns=['close'])
            
            # Расчет Bollinger Bands
            df['ma'] = df['close'].rolling(window=period).mean()
            df['std'] = df['close'].rolling(window=period).std()
            
            df['upper'] = df['ma'] + (df['std'] * std_dev_mult)
            df['lower'] = df['ma'] - (df['std'] * std_dev_mult)
            
            # Берем значения последней закрытой свечи
            last = df.iloc[-2] 
            
            return {
                'current_close': float(last['close']),
                'middle': float(last['ma']),
                'upper': float(last['upper']),
                'lower': float(last['lower'])
            }
            
        except Exception as e:
            self.log(f"Reversion Error {symbol}: {e}", "error")
            return None

    def get_linreg_slope(self, symbol: str) -> float:
        """
        Обертка для получения наклона на текущем таймфрейме стратегии.
        """
        tf = self.app.strategy_timeframe.get()
        return self.get_linreg_slope_on_tf(symbol, tf)

    def get_linreg_slope_on_tf(self, symbol: str, tf: str) -> float:
        """
        Расчет угла наклона линейной регрессии (Slope) на заданном ТФ.
        Помогает отфильтровать сделки против сильного импульса.
        """
        try:
            klines = self.trader.get_klines(symbol, tf, 30)
            if not klines or len(klines) < 20: 
                return 0.0
            
            # Берем последние 20 свечей закрытия
            closes = np.array([float(k[4]) for k in klines[-20:]])
            
            # Нормализуем цену, чтобы Slope был сопоставим для разных монет (BTC vs DOGE)
            # Приводим к виду: изменение в процентах относительно первой точки
            y = closes / closes[0]
            x = np.arange(len(y))
            
            # Линейная регрессия (y = mx + c), где m - наклон (slope)
            slope, _ = np.polyfit(x, y, 1)
            
            # Умножаем на 100 для удобства (0.0005 -> 0.05)
            # Значения обычно от -0.10 до +0.10
            return slope * 100 
            
        except Exception:
            return 0.0