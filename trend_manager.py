# trend_manager.py
# V9.21 (Critical Fixes by AI Assistant)
#
# ИЗМЕНЕНИЯ V9.21:
# - ✅ Исправлена проверка длины DataFrame перед доступом к iloc
# - ✅ Добавлена валидация NaN значений
# - ✅ Улучшена обработка ошибок
# - ✅ Добавлена защита от некорректных данных

import pandas as pd
import numpy as np
import threading
import time
from typing import List, Dict, Any, Optional 

class TrendManager:
    def __init__(self, app, trader):
        self.app = app 
        self.trader = trader 
        self.log = app.queue_log 
        self.kline_limit = 50 
        self.last_blocked_signal: Dict[str, str] = {}
        
    def _find_trend_signal(self, symbol: str, regime: str) -> Optional[str]:
        """
        V9.21: Ищет PULLBACK для входа с улучшенной валидацией.
        """
        look_for_long = (regime == "UP_TREND")
        look_for_short = (regime == "DOWN_TREND")
        
        if not look_for_long and not look_for_short:
            return None 

        try:
            # Получаем параметры
            tf = self.app.strategy_timeframe.get() if hasattr(self.app.strategy_timeframe, 'get') else '5m'
            ema_period = self.app._get_safe_int(self.app.trend_ema_period, 10) 
            ema_filter_period = self.app._get_safe_int(self.app.trend_local_filter_ema, 50)
            
            # ✅ V9.21: Гарантируем достаточно данных
            kline_limit_needed = max(self.kline_limit, ema_filter_period + 10, ema_period + 10)
            
            klines = self.trader.get_klines(symbol, tf, kline_limit_needed)
            
            if not klines or len(klines) < kline_limit_needed:
                return None

            # Создаем DataFrame
            df = pd.DataFrame(klines, dtype=float)
            df.rename(columns={0: 't', 4: 'c'}, inplace=True)
            
            # Рассчитываем EMA
            df['ema_signal'] = df['c'].ewm(span=ema_period, adjust=False).mean()
            df['ema_filter'] = df['c'].ewm(span=ema_filter_period, adjust=False).mean()

            # ✅ V9.21: ИСПРАВЛЕНО - Проверка ДО доступа к iloc
            if len(df) < 3:
                return None
            
            # Теперь безопасно обращаемся к данным
            last = df.iloc[-2]
            prev = df.iloc[-3]
            
            # ✅ V9.21: Проверка на NaN
            if pd.isna(last['ema_signal']) or pd.isna(last['ema_filter']):
                return None
            if pd.isna(prev['ema_signal']):
                return None

            # Логика поиска сигналов
            if look_for_long:
                # Пересечение снизу вверх
                signal_fired = (prev['c'] < prev['ema_signal']) and (last['c'] > last['ema_signal'])
                
                if signal_fired:
                    # Проверка фильтра
                    if last['c'] > last['ema_filter']:
                        self.log(f"TrendManager ({symbol}): {tf} ВОЗВРАТ в ЛОНГ! Тренд: {regime}", "success")
                        self.last_blocked_signal.pop(symbol, None)
                        return 'LONG'
                    else:
                        # Сигнал заблокирован фильтром
                        if self.last_blocked_signal.get(symbol) != "LONG":
                            self.log(f"TrendManager ({symbol}): ⚠️ ЛОНГ ЗАБЛОКИРОВАН (Фильтр EMA {ema_filter_period})", "warning")
                            self.last_blocked_signal[symbol] = "LONG"
                        return None

            if look_for_short:
                # Пересечение сверху вниз
                signal_fired = (prev['c'] > prev['ema_signal']) and (last['c'] < last['ema_signal'])
                
                if signal_fired:
                    # Проверка фильтра
                    if last['c'] < last['ema_filter']:
                        self.log(f"TrendManager ({symbol}): {tf} ВОЗВРАТ в ШОРТ! Тренд: {regime}", "success")
                        self.last_blocked_signal.pop(symbol, None)
                        return 'SHORT'
                    else:
                        # Сигнал заблокирован фильтром
                        if self.last_blocked_signal.get(symbol) != "SHORT":
                            self.log(f"TrendManager ({symbol}): ⚠️ ШОРТ ЗАБЛОКИРОВАН (Фильтр EMA {ema_filter_period})", "warning")
                            self.last_blocked_signal[symbol] = "SHORT"
                        return None
            
            # Нет сигнала - очищаем блокировку
            self.last_blocked_signal.pop(symbol, None)
            return None

        except KeyError as e:
            self.log(f"TrendManager ({symbol}): Отсутствуют данные в klines - {e}", "error")
            return None
            
        except Exception as e:
            self.log(f"TrendManager ({symbol}): Ошибка - {e}", "error")
            import traceback
            self.log(traceback.format_exc(), "error")
            return None

    def check_ema_trend_on_tf(self, symbol: str, tf: str, ema_period: int = 50) -> Optional[str]:
        """
        V9.21: Проверяет направление тренда на заданном TF.
        """
        try:
            kline_limit_needed = ema_period + 5
            klines = self.trader.get_klines(symbol, tf, kline_limit_needed)
            
            if not klines or len(klines) < kline_limit_needed:
                return None
            
            df = pd.DataFrame(klines, dtype=float)
            df.rename(columns={4: 'c'}, inplace=True)
            
            # Рассчитываем EMA
            ema_series = df['c'].ewm(span=ema_period, adjust=False).mean()
            
            # ✅ V9.21: Проверка длины перед доступом
            if len(ema_series) < 2:
                return None
            
            ema = ema_series.iloc[-2]  # Последняя закрытая свеча
            close = df['c'].iloc[-2]
            
            # ✅ V9.21: Проверка на NaN
            if pd.isna(ema) or pd.isna(close):
                return None
            
            return "UP" if close > ema else "DOWN"
            
        except Exception as e:
            self.log(f"check_ema_trend_on_tf ({symbol}, {tf}): Ошибка - {e}", "error")
            return None

    def check_cascade_trend(self, symbol: str, timeframes: List[str], ema_period: int = 50) -> Optional[str]:
        """
        V9.21: Проверяет тренд на СЕРИИ таймфреймов с улучшенной обработкой.
        Возвращает 'UP' только если везде UP.
        Возвращает 'DOWN' только если везде DOWN.
        Иначе возвращает None (смешанный тренд).
        """
        try:
            # ✅ V9.21: Валидация входных данных
            if not timeframes or not isinstance(timeframes, list):
                self.log(f"check_cascade_trend ({symbol}): Некорректный список timeframes", "error")
                return None
            
            results = []
            
            for tf in timeframes:
                if not tf or not isinstance(tf, str):
                    continue
                    
                trend = self.check_ema_trend_on_tf(symbol, tf, ema_period)
                
                if trend is None:
                    # Нет данных для этого TF - пропускаем всю проверку
                    return None
                    
                results.append(trend)
            
            # ✅ V9.21: Проверка на пустой результат
            if not results:
                return None
            
            # Проверяем согласованность
            if all(t == "UP" for t in results):
                return "UP"
            
            if all(t == "DOWN" for t in results):
                return "DOWN"
            
            # Разнобой
            return None
            
        except Exception as e:
            self.log(f"check_cascade_trend ({symbol}): Ошибка - {e}", "error")
            import traceback
            self.log(traceback.format_exc(), "error")
            return None