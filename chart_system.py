# chart_system.py
# V1.0 (Module Separation)
#
# Отвечает за:
# 1. Отрисовку графика позиции (Matplotlib)
# 2. Сохранение скриншотов сделок
# 3. Отрисовку графика PnL

import os
import datetime as dt
import pandas as pd
import tkinter as tk
from tkinter import ttk

# --- Библиотеки для графика ---
try:
    from matplotlib.figure import Figure
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
    MATPLOTLIB_AVAILABLE = True 
except ImportError:
    print("ВНИМАНИЕ: Matplotlib не установлен.")
    MATPLOTLIB_AVAILABLE = False

class ChartSystem:
    def __init__(self, app):
        self.app = app # Ссылка на главный объект для доступа к данным
        self.log = app.queue_log
        
        self.plot_figure = None
        self.plot_canvas = None
        self.plot_canvas_widget = None
        
        self.pnl_fig = None
        self.ax_pnl = None
        self.pnl_canvas = None
        
        self.last_plotted_symbol = ""
        self.last_plotted_tf = ""
        self.chart_update_timer = None
        
        # Цвета
        self.bg_color = '#2E2E2E'
        self.fg_color = '#FFFFFF'
        self.tree_bg_color = '#1E1E1E'
        self.acc_color = '#007ACC'

    def setup_position_chart_tab(self, parent_notebook, chart_tf_var):
        """Создает вкладку графика"""
        if not MATPLOTLIB_AVAILABLE:
            chart_tab = ttk.Frame(parent_notebook)
            parent_notebook.add(chart_tab, text="📈 График (X)")
            ttk.Label(chart_tab, text="График недоступен.\npip install matplotlib pandas", 
                      justify=tk.CENTER).pack(expand=True)
            return chart_tab, None, None

        chart_tab = ttk.Frame(parent_notebook)
        parent_notebook.add(chart_tab, text="📈 График Позиции")
        
        title_label = ttk.Label(chart_tab, text=f"Мониторинг активной позиции", font=('Arial', 12, 'bold'))
        title_label.pack(pady=5)

        tf_frame = ttk.Frame(chart_tab)
        tf_frame.pack(pady=2)
        
        # Кнопки ТФ
        self.app.active_tf_button = None
        
        from functools import partial
        for tf in ['5m', '15m', '1h', '4h']:
            btn = ttk.Button(tf_frame, text=tf, width=5, 
                           command=partial(self.set_chart_tf, tf, title_label))
            btn.pack(side=tk.LEFT, padx=3)
            if tf == self.app.chart_tf:
                btn.config(style="Accent.TButton") 
                self.app.active_tf_button = btn
        
        self.plot_figure = Figure(figsize=(8, 6), dpi=100)
        self.plot_figure.patch.set_facecolor(self.bg_color) 
        
        ax = self.plot_figure.add_subplot(111)
        ax.set_facecolor(self.tree_bg_color)
        ax.text(0.5, 0.5, "Ожидание данных...", ha='center', va='center', fontsize=14, color=self.fg_color)
        ax.set_xticks([]); ax.set_yticks([])
        for spine in ax.spines.values(): spine.set_edgecolor('gray')
        
        self.plot_canvas = FigureCanvasTkAgg(self.plot_figure, master=chart_tab)
        self.plot_canvas_widget = self.plot_canvas.get_tk_widget()
        self.plot_canvas_widget.pack(side=tk.TOP, fill=tk.BOTH, expand=1, padx=5, pady=5)
        self.plot_canvas.draw()
        
        info_label = ttk.Label(chart_tab, text="Ожидание активной позиции...", font=('Arial', 10, 'bold'))
        info_label.pack(pady=5)
        
        return chart_tab, title_label, info_label

    def set_chart_tf(self, new_tf, title_label):
        """Смена ТФ графика"""
        if new_tf == self.app.chart_tf and self.last_plotted_symbol != "":
            return 
            
        self.log(f"График: Смена ТФ на {new_tf}", "info")
        self.app.chart_tf = new_tf
        title_label.config(text=f"Мониторинг позиции ({new_tf})")
        
        # Обновление стиля кнопок
        try:
            if self.app.active_tf_button:
                self.app.active_tf_button.config(style='TButton')
            # Поиск новой кнопки (через widget traversal в ui_layout сложно, но state обновлен)
            # В данном упрощенном варианте мы просто сбрасываем график
        except: pass

        if self.chart_update_timer:
            self.app.root.after_cancel(self.chart_update_timer)
            self.chart_update_timer = None
            
        self.last_plotted_symbol = "" 
        self.update_position_chart()

    def update_position_chart(self):
        """Логика отрисовки графика"""
        if self.chart_update_timer:
            self.app.root.after_cancel(self.chart_update_timer)
            self.chart_update_timer = None

        if not MATPLOTLIB_AVAILABLE or not self.plot_figure:
            if hasattr(self.app, 'root') and self.app.running.is_set():
                self.chart_update_timer = self.app.root.after(15000, self.update_position_chart)
            return

        active_symbol = next(iter(self.app.open_positions.keys()), None)
        
        plot_symbol = None
        plot_entry = 0.0
        plot_side = 'LONG'
        plot_sl = 0.0
        plot_exit = None
        info_text = ""
        is_active_pos = False

        # Определение что рисовать
        if active_symbol:
            is_active_pos = True
            pos_data = self.app.open_positions.get(active_symbol, {})
            plot_symbol = active_symbol
            plot_entry = pos_data.get('entry_price', 0.0)
            plot_side = pos_data.get('side', 'LONG')
            plot_sl = pos_data.get('ts_data', {}).get('current_trail_price', pos_data.get('sl_price', 0))
            info_text = f"АКТИВНА: {plot_symbol} | Вход: {plot_entry:.4f} | SL: {plot_sl:.4f}"
        
        elif self.app.last_closed_position_data:
            is_active_pos = False
            d = self.app.last_closed_position_data
            plot_symbol = d['symbol']
            plot_entry = d['entry_price']
            plot_side = d['side']
            plot_sl = d['sl_price'] 
            plot_exit = d['exit_price']
            info_text = f"ЗАКРЫТА: {plot_symbol} | Вход: {plot_entry:.4f} | Выход: {plot_exit:.4f} ({d['reason']})"

        # Если рисовать нечего
        if not plot_symbol:
            if self.last_plotted_symbol != "NONE":
                self.plot_figure.clear()
                self.plot_figure.patch.set_facecolor(self.bg_color) 
                ax = self.plot_figure.add_subplot(111)
                ax.set_facecolor(self.tree_bg_color)
                ax.text(0.5, 0.5, "Нет активных позиций.", ha='center', va='center', fontsize=14, color=self.fg_color)
                ax.set_xticks([]); ax.set_yticks([])
                for spine in ax.spines.values(): spine.set_edgecolor('gray')
                self.plot_canvas.draw()
                if self.app.chart_info_label: self.app.chart_info_label.config(text="Ожидание...")
                self.last_plotted_symbol = "NONE"
            
            if self.app.running.is_set():
                self.chart_update_timer = self.app.root.after(5000, self.update_position_chart) 
            return

        # Проверка на повторную отрисовку того же самого
        current_plot_id = f"{plot_symbol}_{plot_exit}" 
        if self.last_plotted_symbol == current_plot_id and self.last_plotted_tf == self.app.chart_tf:
            if not is_active_pos:
                if self.app.running.is_set():
                    self.chart_update_timer = self.app.root.after(15000, self.update_position_chart)
                return

        if self.app.chart_info_label: self.app.chart_info_label.config(text=info_text)
        
        try:
            if not self.app.trader:
                 if self.app.running.is_set():
                     self.chart_update_timer = self.app.root.after(5000, self.update_position_chart)
                 return
                 
            klines = self.app.trader.get_klines(plot_symbol, self.app.chart_tf, 100)
            if not klines:
                if self.app.running.is_set():
                    self.chart_update_timer = self.app.root.after(5000, self.update_position_chart)
                return
                
            df = pd.DataFrame(klines, dtype=float, columns=['t', 'o', 'h', 'l', 'c', 'v', 'ct', 'qv', 'n', 'qa', 'tb', 'ta'])
            df['Time'] = pd.to_datetime(df['t'], unit='ms')
            
            self.plot_figure.clear()
            self.plot_figure.patch.set_facecolor(self.bg_color) 
            ax = self.plot_figure.add_subplot(111)
            ax.set_facecolor(self.tree_bg_color) 
            
            ax.plot(df['Time'], df['c'], label='Close Price', color='#007ACC', linewidth=1.5) 
            
            entry_color = '#00C853' if plot_side == 'LONG' else '#FF1744' 
            ax.axhline(plot_entry, color=entry_color, linestyle='--', linewidth=2, label=f'Entry {plot_entry:.4f}')
            
            if plot_sl > 0:
                ax.axhline(plot_sl, color='orange', linestyle=':', linewidth=2, label=f'SL/TS {plot_sl:.4f}')

            if plot_exit:
                is_profit = (plot_side == 'LONG' and plot_exit > plot_entry) or (plot_side == 'SHORT' and plot_exit < plot_entry)
                exit_color = '#00C853' if is_profit else '#FF1744'
                ax.axhline(plot_exit, color=exit_color, linestyle='--', linewidth=2, label=f'Exit {plot_exit:.4f}')

            ax.set_title(f"Мониторинг {plot_symbol} ({self.app.chart_tf})", color=self.fg_color)
            ax.set_xlabel("Время", color=self.fg_color)
            ax.set_ylabel("Цена", color=self.fg_color)
            ax.tick_params(axis='x', colors='white', rotation=15, labelsize=8)
            ax.tick_params(axis='y', colors='white', labelsize=8)
            ax.grid(True, linestyle=':', alpha=0.6, color='gray')
            
            legend = ax.legend(loc='upper left')
            for text in legend.get_texts(): text.set_color(self.fg_color)
            legend.get_frame().set_alpha(0.2)
            legend.get_frame().set_facecolor(self.bg_color)
            
            for spine in ax.spines.values(): spine.set_edgecolor('gray')

            self.plot_figure.tight_layout()
            self.plot_canvas.draw()
            
            self.last_plotted_symbol = current_plot_id
            self.last_plotted_tf = self.app.chart_tf
            
        except Exception as e:
            self.log(f"Ошибка построения графика {plot_symbol}: {e}", "error")

        if self.app.running.is_set():
            self.chart_update_timer = self.app.root.after(15000, self.update_position_chart)

    def save_trade_chart(self, symbol, timeframe, entry_price, exit_price, side, reason, trader):
        """Сохраняет график сделки в PNG"""
        if not MATPLOTLIB_AVAILABLE: return
        
        fig = None 
        try:
            history_dir = "history"
            os.makedirs(history_dir, exist_ok=True)
            timestamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = os.path.join(history_dir, f"{symbol}_{timestamp}_{side}.png")
            
            if not trader: return
                
            klines = trader.get_klines(symbol, timeframe, 100)
            if not klines or len(klines) < 20: return
            
            df = pd.DataFrame(klines, dtype=float, columns=['t', 'o', 'h', 'l', 'c', 'v', 'ct', 'qv', 'n', 'qa', 'tb', 'ta'])
            df['Time'] = pd.to_datetime(df['t'], unit='ms')
            
            fig = Figure(figsize=(12, 7))
            ax = fig.add_subplot(111)
            fig.patch.set_facecolor(self.bg_color)
            ax.set_facecolor(self.tree_bg_color)
            
            ax.plot(df['Time'], df['c'], label=f'Цена {symbol} ({timeframe})', color='#007ACC', linewidth=1)
            
            entry_color = '#00C853' if side == 'LONG' else '#FF1744'
            ax.axhline(entry_price, color=entry_color, linestyle='--', linewidth=1.5, label=f'Вход: {entry_price}')
            
            is_profit = (side == 'LONG' and exit_price > entry_price) or (side == 'SHORT' and exit_price < entry_price)
            exit_color = '#00C853' if is_profit else '#FF1744'
            ax.axhline(exit_price, color=exit_color, linestyle=':', linewidth=1.5, label=f'Выход: {exit_price}')
            
            ax.set_title(f"Сделка: {symbol} ({side}) | Причина: {reason}", color=self.fg_color)
            ax.set_ylabel("Цена", color=self.fg_color)
            ax.tick_params(axis='x', colors='white', rotation=15, labelsize=8)
            ax.tick_params(axis='y', colors='white', labelsize=8)
            ax.grid(True, linestyle=':', alpha=0.6, color='gray')
            
            legend = ax.legend(loc='upper left')
            for text in legend.get_texts(): text.set_color(self.fg_color)
            for spine in ax.spines.values(): spine.set_edgecolor('gray')
            
            fig.tight_layout()
            fig.savefig(filename, dpi=150)
            self.log(f"📈 График сделки сохранен: {filename}", "success")
            
        except Exception as e:
            self.log(f"КРИТ. ОШИБКА сохранения графика: {e}", "error")
        finally:
            if fig is not None:
                try: 
                    fig.clf()
                    del fig
                except: pass

    def update_pnl_chart(self, pnl_history, total_profit_usd, pnl_tab_frame):
        """Отрисовка PnL графика"""
        if not MATPLOTLIB_AVAILABLE: return
        
        # Если фигуры еще нет - создаем
        if not self.pnl_fig:
            self.pnl_fig = Figure(figsize=(5, 4), dpi=100)
            self.pnl_fig.patch.set_facecolor(self.bg_color)
            self.ax_pnl = self.pnl_fig.add_subplot(111)
            self.ax_pnl.set_facecolor(self.tree_bg_color)
            self.pnl_canvas = FigureCanvasTkAgg(self.pnl_fig, master=pnl_tab_frame)
            self.pnl_canvas.get_tk_widget().pack(expand=True, fill='both', padx=5, pady=5)
            
        self.ax_pnl.clear()
        
        history_to_plot = pnl_history.copy()
        if not history_to_plot or (history_to_plot and history_to_plot[-1][1] != total_profit_usd):
             history_to_plot.append((dt.datetime.now(), total_profit_usd))

        ax = self.ax_pnl 

        if history_to_plot: 
            times, pnls = zip(*history_to_plot)
            ax.plot(times, pnls, marker='o', linestyle='-', color=self.acc_color, markersize=3)
        else: 
            ax.plot([],[])
            
        ax.set_title("Динамика PnL", color=self.fg_color)
        ax.set_xlabel("Время", color=self.fg_color)
        ax.set_ylabel("Общий PnL (USDT)", color=self.fg_color)
        ax.tick_params(axis='x', colors='white', rotation=15, labelsize=8)
        ax.tick_params(axis='y', colors='white', labelsize=8)
        ax.grid(True, linestyle='--', color='gray', alpha=0.5)
        
        ax.set_facecolor(self.tree_bg_color)
        for spine in ax.spines.values(): spine.set_edgecolor('gray')
            
        self.pnl_fig.tight_layout(pad=1.5)
        try: self.pnl_canvas.draw()
        except tk.TclError: pass