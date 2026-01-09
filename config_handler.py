# config_handler.py
# V1.1 (Smart Sync Enabled)
#
# ИЗМЕНЕНИЯ V1.1:
# - Добавлена переменная self.last_blacklist_mtime
# - Добавлен метод check_blacklist_update(), который проверяет,
#   не изменил ли кто-то (например, ShadowBrain) файл черного списка.

import json
import os
import sys

class ConfigHandler:
    def __init__(self, log_callback):
        self.log = log_callback
        self.config_file = 'config.json'
        self.blacklist_file = 'blacklist.json'
        
        # Для отслеживания изменений файла
        self.last_blacklist_mtime = 0

    def load_and_validate_config(self) -> dict:
        """Загружает и валидирует config.json"""
        default_config = {
            'trade_amount_usd': 10.0,
            'leverage': 20,
            'paper_start_balance': 1000.0,
            'maker_fee': 0.02,
            'max_concurrent_trades': 10,
            'use_limit_orders': True,
            'limit_order_lifetime': 30,
            'strategy_timeframe': '5m',
            'trend_mid_tf': '15m',
            'ma_ema_period': 200,
            'ma_adx_period': 14,
            'ma_adx_threshold': 30.0,
            'trend_ema_period': 10,
            'trend_local_filter_ema': 50,
            'rev_bb_period': 20,
            'rev_bb_std_dev': 2.5,
            'rev_rsi_period': 14,
            'rev_rsi_oversold': 35.0,
            'rev_rsi_overbought': 65.0,
            'parabolic_atr_multiplier': 3.0,
            'mid_tf_slope_threshold': 0.04,
            'per_pos_tp_enabled': True,
            'per_pos_peak_drop_pct': 20.0,
            'per_pos_stagnation_time': 180,
            'per_pos_tp_min_profit_usd': 0.50,
            'trade_cooldown_minutes': 15,
            'sl_limit_enabled': True,
            'sl_limit_percent': 1.0,
            'scanner_volatile_mode': 0,
            'api_key': '',
            'api_secret': '',
            'global_tp_enabled': True,
            'global_tp_amount': 20.0,
            'trailing_pnl_enabled': True,
            'trailing_pnl_peak_drop_pct': 25.0,
            'trailing_pnl_stagnation_time': 120,
            'scanner_liquidity_filter': 100000.0,
            'scanner_min_tf_volume': 50000.0,
            'scanner_timeframe': '1h',
            'reversion_top_pairs_count': 10,
            'atr_timeframe_strat': '15m',
            'atr_period_strat': 14,
            'sl_atr_multiplier': 2.5,
            'ts_atr_multiplier': 1.5,
            'paper_mode': True
        }
        
        if not os.path.exists(self.config_file):
            return default_config
            
        try:
            with open(self.config_file, 'r', encoding='utf-8') as f:
                loaded_config = json.load(f)
            
            validated = {}
            for key, default_value in default_config.items():
                if key in loaded_config:
                    try:
                        if isinstance(default_value, bool): validated[key] = bool(loaded_config[key])
                        elif isinstance(default_value, int): validated[key] = int(loaded_config[key])
                        elif isinstance(default_value, float): validated[key] = float(loaded_config[key])
                        else: validated[key] = loaded_config[key]
                    except: validated[key] = default_value
                else:
                    validated[key] = default_value
            
            # Сохраняем остальные ключи
            for k, v in loaded_config.items():
                if k not in validated: validated[k] = v
                    
            return validated
        except: return default_config

    def save_config_for_worker(self, current_config: dict):
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(current_config, f, indent=4)
        except Exception as e:
            self.log(f"КРИТ. ОШИБКА сохранения config.json: {e}", "error")

    def load_blacklist(self) -> set:
        """Первичная загрузка"""
        if not os.path.exists(self.blacklist_file):
            self.save_blacklist(set())
            return set()

        try:
            # Запоминаем время последнего изменения
            self.last_blacklist_mtime = os.path.getmtime(self.blacklist_file)
            
            with open(self.blacklist_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return set(data)
        except Exception as e:
            self.log(f"Ошибка чтения blacklist: {e}", "error")
            return set()

    def check_blacklist_update(self) -> set:
        """
        V1.1: Проверяет, изменился ли файл на диске.
        Возвращает set() с новыми данными, если файл изменился.
        Возвращает None, если изменений нет.
        """
        if not os.path.exists(self.blacklist_file): return None
        
        try:
            current_mtime = os.path.getmtime(self.blacklist_file)
            if current_mtime > self.last_blacklist_mtime:
                # Файл обновился! (ShadowBrain записал кого-то)
                self.last_blacklist_mtime = current_mtime
                with open(self.blacklist_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    return set(data)
        except: pass
        
        return None

    def save_blacklist(self, blacklist_set: set):
        try:
            with open(self.blacklist_file, 'w', encoding='utf-8') as f:
                json.dump(list(blacklist_set), f, indent=4)
            # Обновляем таймстамп, чтобы не триггерить самого себя
            if os.path.exists(self.blacklist_file):
                self.last_blacklist_mtime = os.path.getmtime(self.blacklist_file)
        except Exception as e:
            self.log(f"Ошибка сохранения blacklist: {e}", "error")