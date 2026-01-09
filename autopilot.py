# autopilot.py
# V9.10 (Pump Hunter Logic Added)
#
# ИЗМЕНЕНИЯ V9.10:
# - ✅ Добавлен расчет "Pump Score" (Вероятность пампа)
# - ✅ Реализован режим scanner_volatile_mode == 2 (Поиск "Зажигания"/Пампа)
# - ✅ Добавлен расчет силы закрытия свечи (Close Strength)
# - ✅ Улучшен расчет RVOL (теперь более чувствительный к недавним всплескам)

import time
import numpy as np
import threading 
import concurrent.futures 
from typing import Optional, Dict, Any 

class AutopilotManager:
    def __init__(self, app, trader):
        self.app = app 
        self.trader = trader
        
        # ✅ V9.9: Уменьшенный таймаут
        self.scan_timeout = 8.0  # 8 секунд на пару
        
        # ✅ V9.9: Адаптивный размер пула
        max_workers = min(10, (app._get_safe_int(app.max_concurrent_trades, 10) * 2))
        self.executor = concurrent.futures.ThreadPoolExecutor(max_workers=max_workers)
        
        # Статистика
        self._timeout_count = 0
        self._success_count = 0
    
    # ==============================================================================
    # БЛОК ЛОГИКИ АВТОПИЛОТА
    # ==============================================================================
    def check_for_switch(self): 
        pass
    
    def reevaluate_switch_decision(self): 
        pass
    
    def finalize_switch(self): 
        pass

    # ==============================================================================
    # V9.10: СБОР РАСШИРЕННОЙ СТАТИСТИКИ (PUMP METRICS)
    # ==============================================================================
    def _get_klines_and_stats(self, symbol: str, tf: str, min_tf_volume: float) -> Optional[Dict[str, Any]]:
        """
        V9.10: Рассчитывает Volatility, RVOL и Pump Score.
        """
        try:
            # 1. СЕТЕВОЙ ВЫЗОВ
            klines = self.trader.get_klines(symbol, tf, limit=50) # Достаточно 50 для RVOL
            
            if not klines or len(klines) < 30: 
                return None
            
            # 2. Данные (Klines: Open, High, Low, Close, Volume, ..., QuoteVol)
            # k[7] = Quote Asset Volume (USDT)
            volumes = [float(k[7]) for k in klines]
            closes = [float(k[4]) for k in klines]
            highs = [float(k[2]) for k in klines]
            lows = [float(k[3]) for k in klines]
            opens = [float(k[1]) for k in klines]
            
            # Проверка целостности
            if not volumes or len(volumes) < 30: return None
            
            # 3. Фильтр по среднему объему
            avg_tf_volume = np.mean(volumes[-24:]) # Среднее за сутки (если tf=1h) или 2 часа (5m)
            if avg_tf_volume < min_tf_volume: 
                return None
            
            current_price = closes[-1]
            if current_price < 1e-8: return None # Защита
            
            # 4. Расчет Волатильности (Std Dev %)
            std = np.std(closes[-20:])
            std_pct = (std / np.mean(closes[-20:])) * 100
            
            # Диапазон (High-Low %)
            price_range = max(highs[-20:]) - min(lows[-20:])
            vol_range = (price_range / np.mean(closes[-20:])) * 100
            
            # 5. --- V9.10: PUMP HUNTER METRICS ---
            
            # A. RVOL (Relative Volume) - Последняя свеча vs Среднее за 20
            # Если текущая свеча еще формируется, она может быть неполной, но всплеск важен
            last_vol = volumes[-1]
            # Берем среднее за предыдущие 20, исключая текущую
            prev_vol_avg = np.mean(volumes[-21:-1]) 
            
            if prev_vol_avg < 1e-8: 
                rvol = 0.0
            else:
                rvol = last_vol / prev_vol_avg

            # B. Close Strength (Сила закрытия)
            # Где закрылась цена относительно High/Low последней свечи?
            # 1.0 = на самом хае (бычий знак), 0.0 = на самом лоу.
            current_high = highs[-1]
            current_low = lows[-1]
            candle_range = current_high - current_low
            
            if candle_range > 0:
                close_strength = (current_price - current_low) / candle_range
            else:
                close_strength = 0.5 # Доджи
                
            # C. Price Impulse (Импульс цены)
            # Изменение цены в последней свече в %
            last_open = opens[-1]
            if last_open > 0:
                price_change_pct = ((current_price - last_open) / last_open) * 100
            else:
                price_change_pct = 0.0

            # D. PUMP SCORE (Балл вероятности пампа)
            # Формула: (RVOL * 2) + (CloseStrength * 3) + (PriceChange > 0 ? 1 : 0)
            # Мы ищем: Высокий объем + Закрытие у хая + Рост цены
            pump_score = 0.0
            pump_score += min(rvol, 10.0) * 1.5      # Вес RVOL (кап 10)
            pump_score += close_strength * 3.0       # Вес силы закрытия (макс 3)
            
            if price_change_pct > 0.5: pump_score += 2.0 # Бонус за рост > 0.5%
            if price_change_pct > 2.0: pump_score += 3.0 # Бонус за сильный импульс
            
            # 6. Возвращаем результат
            return {
                'pair': symbol, 
                'std_dev_percent': std_pct, 
                'volatility_percent': vol_range, 
                'avg_volume': avg_tf_volume,
                'rvol': rvol,
                'pump_score': pump_score,        # V9.10: Для сортировки
                'price_change_pct': price_change_pct # Для инфо
            }
            
        except ValueError as e:
            if hasattr(self.app, 'queue_log'):
                self.app.queue_log(f"Autopilot (ValErr) {symbol}: {e}", "warning")
            return None
        except Exception as e:
            if hasattr(self.app, 'queue_log'):
                self.app.queue_log(f"Autopilot (Err) {symbol}: {repr(e)}", "error")
            return None
            
    # ==============================================================================
    # V9.9/V9.10: ЛОГИКА СКАНЕРА
    # ==============================================================================

    def run_scanner(self, update_ui=False, pairs_to_check=None, log_progress=False):
        """
        V9.10: Сканирование с поддержкой режима Pump Hunter.
        """
        self._timeout_count = 0
        self._success_count = 0
        
        try:
            # Читаем параметры
            liq_filter = self.app._get_safe_double(self.app.scanner_liquidity_filter, 0.0)
            tf = self.app.scanner_timeframe
            if hasattr(tf, 'get'): tf = tf.get()
            min_tf_volume = self.app._get_safe_double(self.app.scanner_min_tf_volume, 0.0)
            
        except Exception as e: 
            self.app.queue_log(f"Ошибка параметров сканера: {e}", "error")
            return None

        if update_ui:
            self.app.queue_log(f"--- ЗАПУСК СКАНЕРА V9.10 (Pump Hunter) ---", "info")

        tickers = self.trader.get_24h_tickers()
        if not tickers:
            self.app.queue_log("Не удалось получить тикеры.", "error")
            return None

        target_tickers_data = [] 
        
        if pairs_to_check:
            target_tickers_data = [t for t in tickers if t.get('symbol') in pairs_to_check]
        else:
            for t in tickers:
                symbol = t.get('symbol', '')
                quote_volume = float(t.get('quoteVolume', 0))
                
                if (symbol.endswith('USDT') and 
                    quote_volume > liq_filter and
                    'UP' not in symbol and 'DOWN' not in symbol and
                    'BEAR' not in symbol and 'BULL' not in symbol):
                    target_tickers_data.append(t)

        results = []
        limit = len(target_tickers_data)
        
        # Адаптивный таймаут
        adaptive_timeout = self.scan_timeout
        if limit > 300:
            adaptive_timeout = min(self.scan_timeout * 1.5, 12.0)
        
        # --- ЦИКЛ ---
        for i, t in enumerate(target_tickers_data): 
            if (hasattr(self.app, 'running') and 
                isinstance(self.app.running, threading.Event) and 
                not self.app.running.is_set()):
                break
            
            log_this_loop = (update_ui and not pairs_to_check) or log_progress
            if log_this_loop:
                if i % 50 == 0 or i == limit - 1: 
                    current_index = i + 1
                    try:
                        success_rate = (self._success_count / max(1, i)) * 100 if i > 0 else 0
                        self.app.queue_log(
                            f"Сканирование... ({current_index}/{limit}) {t['symbol']} | OK: {success_rate:.0f}%", 
                            "info"
                        )
                    except: pass
            
            future = self.executor.submit(self._get_klines_and_stats, t['symbol'], tf, min_tf_volume)
            
            try:
                pair_result = future.result(timeout=adaptive_timeout)
                if pair_result:
                    results.append(pair_result)
                    self._success_count += 1
            except concurrent.futures.TimeoutError:
                self._timeout_count += 1
                if log_progress:
                    self.app.queue_log(f"⏱️ Тайм-аут {t['symbol']}", "warning")
            except Exception:
                pass

        # --- V9.10: ЛОГИКА СОРТИРОВКИ ПО РЕЖИМАМ ---
        scan_mode = self.app._get_safe_int(self.app.scanner_volatile_mode, 0)
        
        if scan_mode == 2:
            # 🔥 РЕЖИМ 2: PUMP HUNTER (ЗАЖИГАНИЕ) 🔥
            if update_ui:
                self.app.queue_log("🔥 РЕЖИМ: Pump Hunter (RVOL + Impulse). Сортировка по Pump Score.", "warning")
            
            # Сортируем по нашему новому баллу Pump Score
            # Фильтруем совсем мертвые пары
            pump_candidates = [r for r in results if r['rvol'] > 1.2] 
            pump_candidates.sort(key=lambda x: x['pump_score'], reverse=True)
            results = pump_candidates
            
        elif scan_mode == 1:
            # Волатильные (для скальпинга отката)
            if update_ui:
                self.app.queue_log("Режим: Высокая волатильность (max StdDev).", "warning")
            results.sort(key=lambda x: x['std_dev_percent'], reverse=True)
            
        else:
            # Стабильные (для тренда)
            if update_ui:
                self.app.queue_log("Режим: Стабильные тренды (min StdDev).", "warning")
            results.sort(key=lambda x: x['std_dev_percent'])

        if update_ui:
            self.app.queue_log(f"--- ЗАВЕРШЕНО: Найдено {len(results)} пар ---", "success")
        
        if update_ui and results: 
            self.app.scanner_queue.put(results)
        
        return results if results else None