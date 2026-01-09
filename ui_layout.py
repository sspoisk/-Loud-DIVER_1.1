# ui_layout.py
# V10.2 - CVD DIVERGENCE HUNTER (UI UPDATE)
#
# ИЗМЕНЕНИЯ:
# - ✅ Добавлены поля "Мин. Цена %" и "Мин. CVD %" на панель

import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox

class UiBuilder:
    def __init__(self, app):
        self.app = app
        # Цвета
        self.bg_color = '#2E2E2E'
        self.fg_color = '#FFFFFF'
        self.btn_color = '#5A5A5A'
        self.acc_color = '#007ACC'
        self.entry_bg_color = '#3C3C3C'
        self.tree_bg_color = '#1E1E1E'
        # V10.0: Цвет акцента для CVD
        self.cvd_color = '#00C853'  # Зелёный

    def setup_ui(self):
        root = self.app.root
        root.configure(bg=self.bg_color)
        s = ttk.Style(root); s.theme_use('clam')
        
        # --- Стили ---
        s.configure('.', background=self.bg_color, foreground=self.fg_color, fieldbackground=self.entry_bg_color, bordercolor="#888", lightcolor=self.bg_color, darkcolor=self.bg_color)
        s.configure('TLabel', background=self.bg_color, foreground=self.fg_color)
        s.configure('TButton', background=self.btn_color, foreground=self.fg_color, relief='flat', borderwidth=0); 
        s.map('TButton', background=[('active', self.acc_color)])
        s.configure('Emergency.TButton', background='#D32F2F', foreground=self.fg_color, relief='flat')
        s.map('Emergency.TButton', background=[('active', '#B71C1C')])
        s.configure('Real.TCheckbutton', foreground='#B71C1C', background=self.bg_color, font=('TkDefaultFont',9,'bold'))
        s.configure('Sniper.TLabel', background=self.bg_color, foreground='#00C853', font=('TkDefaultFont',9,'bold')) 
        s.configure('CVD.TLabel', background=self.bg_color, foreground='#00C853', font=('TkDefaultFont',9,'bold'))
        s.configure('CVD.TLabelframe', background=self.bg_color, bordercolor="#00C853")
        s.configure('CVD.TLabelframe.Label', background=self.bg_color, foreground='#00C853', font=('TkDefaultFont',9,'bold'))
        s.configure('TLabelframe', background=self.bg_color, bordercolor="#888")
        s.configure('TLabelframe.Label', background=self.bg_color, foreground=self.fg_color)
        s.configure('Treeview', fieldbackground=self.tree_bg_color, background=self.tree_bg_color, foreground=self.fg_color, relief='flat', borderwidth=0)
        s.configure('Treeview.Heading', background=self.btn_color, foreground=self.fg_color, relief='flat')
        s.map('Treeview.Heading', background=[('active', self.acc_color)])
        s.configure('TNotebook', background=self.bg_color, borderwidth=0)
        s.configure('TNotebook.Tab', background=self.btn_color, foreground=self.fg_color, relief='flat')
        s.map('TNotebook.Tab', background=[('selected', self.acc_color)])
        s.configure('Accent.TButton', background=self.acc_color, foreground=self.fg_color, relief='flat', borderwidth=0)
        s.map('Accent.TButton', background=[('active', self.acc_color)])

        paned = ttk.PanedWindow(root, orient=tk.HORIZONTAL)
        paned.pack(fill="both", expand=True, padx=5, pady=5)
        
        # --- ЛЕВАЯ ПАНЕЛЬ ---
        left_cont = ttk.Frame(paned, width=420); paned.add(left_cont, weight=1)
        canvas = tk.Canvas(left_cont, bg=self.bg_color, highlightthickness=0)
        sb = ttk.Scrollbar(left_cont, orient="vertical", command=canvas.yview)
        l_cont = ttk.Frame(canvas)
        canvas.create_window((0,0), window=l_cont, anchor="nw")
        canvas.configure(yscrollcommand=sb.set)
        canvas.pack(side="left", fill="both", expand=True); sb.pack(side="right", fill="y")
        
        def _on_mousewheel(event):
            try: canvas.yview_scroll(int(-1*(event.delta/120)), "units")
            except: pass
        canvas.bind_all("<MouseWheel>", _on_mousewheel)
        l_cont.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))

        gr = {'sticky':'w', 'padx':5, 'pady':2}

        # Блок API
        api_f = ttk.LabelFrame(l_cont, text="API"); api_f.pack(fill="x", padx=5, pady=2)
        ttk.Checkbutton(api_f, text="Загрузить из binance_keys.txt", variable=self.app.load_keys_flag, command=self.app.toggle_load_keys).pack(anchor='w', padx=5)
        ttk.Label(api_f, text="API Key:").pack(anchor='w', padx=5)
        ttk.Entry(api_f, textvariable=self.app.api_key, show="*").pack(fill="x", padx=5)
        ttk.Label(api_f, text="API Secret:").pack(anchor='w', padx=5)
        ttk.Entry(api_f, textvariable=self.app.api_secret, show="*").pack(fill="x", padx=5, pady=(0,5))

        # ═══════════════════════════════════════════════════════════════
        # V10.2: БЛОК CVD DIVERGENCE (ОБНОВЛЕННЫЙ)
        # ═══════════════════════════════════════════════════════════════
        cvd_f = ttk.LabelFrame(l_cont, text="🎯 CVD Divergence V10.2", style='CVD.TLabelframe')
        cvd_f.pack(fill="x", padx=5, pady=5)
        
        # Основные параметры
        ttk.Label(cvd_f, text="Слоты (1-5):", style='CVD.TLabel').grid(row=0, column=0, **gr)
        ttk.Entry(cvd_f, textvariable=self.app.max_concurrent_trades, width=8).grid(row=0, column=1, **gr)
        
        ttk.Label(cvd_f, text="Сумма ($):", style='CVD.TLabel').grid(row=0, column=2, **gr)
        ttk.Entry(cvd_f, textvariable=self.app.trade_amount_usd, width=8).grid(row=0, column=3, **gr)
        
        ttk.Label(cvd_f, text="Плечо:", style='CVD.TLabel').grid(row=1, column=0, **gr)
        ttk.Entry(cvd_f, textvariable=self.app.leverage, width=8).grid(row=1, column=1, **gr)
        
        ttk.Label(cvd_f, text="ТФ Анализа:", style='CVD.TLabel').grid(row=1, column=2, **gr)
        tf_var = getattr(self.app, 'cvd_scan_timeframe', self.app.scanner_timeframe)
        ttk.Entry(cvd_f, textvariable=tf_var, width=8).grid(row=1, column=3, **gr)
        
        # CVD параметры
        ttk.Separator(cvd_f, orient='horizontal').grid(row=2, column=0, columnspan=4, sticky='ew', pady=5)
        
        ttk.Label(cvd_f, text="Мин. RVOL:").grid(row=3, column=0, **gr)
        cvd_rvol_var = getattr(self.app, 'cvd_min_rvol', tk.DoubleVar(value=0.5))
        if not hasattr(self.app, 'cvd_min_rvol'): self.app.cvd_min_rvol = cvd_rvol_var
        ttk.Entry(cvd_f, textvariable=self.app.cvd_min_rvol, width=8).grid(row=3, column=1, **gr)
        
        ttk.Label(cvd_f, text="Мин. Сила (0-100):").grid(row=3, column=2, **gr)
        cvd_str_var = getattr(self.app, 'cvd_min_strength', tk.IntVar(value=10))
        if not hasattr(self.app, 'cvd_min_strength'): self.app.cvd_min_strength = cvd_str_var
        ttk.Entry(cvd_f, textvariable=self.app.cvd_min_strength, width=8).grid(row=3, column=3, **gr)
        
        ttk.Label(cvd_f, text="Мин. R:R:").grid(row=4, column=0, **gr)
        cvd_rr_var = getattr(self.app, 'cvd_min_rr', tk.DoubleVar(value=1.5))
        if not hasattr(self.app, 'cvd_min_rr'): self.app.cvd_min_rr = cvd_rr_var
        ttk.Entry(cvd_f, textvariable=self.app.cvd_min_rr, width=8).grid(row=4, column=1, **gr)
        
        ttk.Label(cvd_f, text="Макс. Сигналов:").grid(row=4, column=2, **gr)
        cvd_max_var = getattr(self.app, 'cvd_max_signals', tk.IntVar(value=5))
        if not hasattr(self.app, 'cvd_max_signals'): self.app.cvd_max_signals = cvd_max_var
        ttk.Entry(cvd_f, textvariable=self.app.cvd_max_signals, width=8).grid(row=4, column=3, **gr)

        # --- V10.2: Новые настройки чувствительности ---
        ttk.Label(cvd_f, text="Мин. Цена %:", foreground="#FFC107").grid(row=5, column=0, **gr)
        cvd_price_var = getattr(self.app, 'cvd_min_price_pct', tk.DoubleVar(value=0.1))
        if not hasattr(self.app, 'cvd_min_price_pct'): self.app.cvd_min_price_pct = cvd_price_var
        ttk.Entry(cvd_f, textvariable=self.app.cvd_min_price_pct, width=8).grid(row=5, column=1, **gr)

        ttk.Label(cvd_f, text="Мин. CVD %:", foreground="#FFC107").grid(row=5, column=2, **gr)
        cvd_cvd_var = getattr(self.app, 'cvd_min_cvd_pct', tk.DoubleVar(value=1.0))
        if not hasattr(self.app, 'cvd_min_cvd_pct'): self.app.cvd_min_cvd_pct = cvd_cvd_var
        ttk.Entry(cvd_f, textvariable=self.app.cvd_min_cvd_pct, width=8).grid(row=5, column=3, **gr)
        # -----------------------------------------------

        # ═══════════════════════════════════════════════════════════════
        # Блок Риска
        # ═══════════════════════════════════════════════════════════════
        risk_f = ttk.LabelFrame(l_cont, text="⚠️ Риск-Менеджмент"); risk_f.pack(fill="x", padx=5, pady=2)
        
        ttk.Label(risk_f, text="ТФ ATR:").grid(row=0, column=0, **gr)
        ttk.Entry(risk_f, textvariable=self.app.atr_timeframe_strat, width=8).grid(row=0, column=1, **gr)
        ttk.Label(risk_f, text="Период ATR:").grid(row=0, column=2, **gr)
        ttk.Entry(risk_f, textvariable=self.app.atr_period_strat, width=8).grid(row=0, column=3, **gr)
        
        ttk.Label(risk_f, text="SL (xATR):").grid(row=1, column=0, **gr)
        ttk.Entry(risk_f, textvariable=self.app.sl_atr_multiplier, width=8).grid(row=1, column=1, **gr)
        ttk.Label(risk_f, text="TS (xATR):").grid(row=1, column=2, **gr)
        ttk.Entry(risk_f, textvariable=self.app.ts_atr_multiplier, width=8).grid(row=1, column=3, **gr)
        
        ttk.Checkbutton(risk_f, text="Лимит SL (%):", variable=self.app.sl_limit_enabled).grid(row=2, column=0, **gr)
        ttk.Entry(risk_f, textvariable=self.app.sl_limit_percent, width=8).grid(row=2, column=1, **gr)
        
        ttk.Checkbutton(risk_f, text="Безубыток ($):", variable=self.app.be_enabled).grid(row=2, column=2, **gr)
        ttk.Entry(risk_f, textvariable=self.app.be_trigger_profit_usd, width=8).grid(row=2, column=3, **gr)

        # ═══════════════════════════════════════════════════════════════
        # Блок Take Profit
        # ═══════════════════════════════════════════════════════════════
        tp_f = ttk.LabelFrame(l_cont, text="💰 Take Profit"); tp_f.pack(fill="x", padx=5, pady=2)
        
        ttk.Checkbutton(tp_f, text="Trey PnL (трейл позиции)", variable=self.app.per_pos_tp_enabled).grid(row=0, column=0, columnspan=2, **gr)
        ttk.Label(tp_f, text="Мин. профит ($):").grid(row=1, column=0, **gr)
        ttk.Entry(tp_f, textvariable=self.app.per_pos_tp_min_profit_usd, width=8).grid(row=1, column=1, **gr)
        ttk.Label(tp_f, text="Просадка (%):").grid(row=1, column=2, **gr)
        ttk.Entry(tp_f, textvariable=self.app.per_pos_peak_drop_pct, width=8).grid(row=1, column=3, **gr)
        
        ttk.Separator(tp_f, orient='horizontal').grid(row=2, column=0, columnspan=4, sticky='ew', pady=3)
        
        ttk.Checkbutton(tp_f, text="Глобал TP ($):", variable=self.app.global_tp_enabled).grid(row=3, column=0, **gr)
        ttk.Entry(tp_f, textvariable=self.app.global_tp_amount, width=8).grid(row=3, column=1, **gr)
        ttk.Checkbutton(tp_f, text="Трейл PnL", variable=self.app.trailing_pnl_enabled).grid(row=3, column=2, columnspan=2, **gr)

        # ═══════════════════════════════════════════════════════════════
        # Блок Сканера
        # ═══════════════════════════════════════════════════════════════
        worker_f = ttk.LabelFrame(l_cont, text="🔍 Сканер"); worker_f.pack(fill="x", padx=5, pady=2)
        
        ttk.Label(worker_f, text="Мин. Ликвидность 24ч:").grid(row=0, column=0, **gr)
        ttk.Entry(worker_f, textvariable=self.app.scanner_liquidity_filter, width=12).grid(row=0, column=1, **gr)
        
        ttk.Label(worker_f, text="Кулдаун (мин):").grid(row=1, column=0, **gr)
        ttk.Entry(worker_f, textvariable=self.app.trade_cooldown_minutes, width=8).grid(row=1, column=1, **gr)

        # ═══════════════════════════════════════════════════════════════
        # Блок Контроля
        # ═══════════════════════════════════════════════════════════════
        ctrl_f = ttk.LabelFrame(l_cont, text="🎮 Контроль"); ctrl_f.pack(fill="x", padx=5, pady=5)
        
        ttk.Checkbutton(ctrl_f, text="РЕАЛ РЕЖИМ (снять = Paper)", variable=self.app.paper_mode, 
                       onvalue=False, offvalue=True, style="Real.TCheckbutton", 
                       command=self.app.toggle_mode).pack(pady=2)
        
        bf = ttk.Frame(ctrl_f); bf.pack(fill='x', pady=2)
        self.app.btn_start = ttk.Button(bf, text="🚀 СТАРТ", command=self.app.start_strategy, style='Accent.TButton')
        self.app.btn_start.pack(side='left', expand=True, fill='x', padx=2) 
        self.app.btn_stop = ttk.Button(bf, text="⏹ СТОП", command=self.app.stop_strategy, state='disabled')
        self.app.btn_stop.pack(side='left', expand=True, fill='x', padx=2)
        
        ttk.Button(ctrl_f, text="🚨 ЗАКРЫТЬ ВСЕ", style='Emergency.TButton', 
                  command=self.app.close_all_market_emergency).pack(fill='x', padx=2, pady=(5,2))
        
        self.app.status_label = ttk.Label(ctrl_f, text="CVD Hunter V10.2 - Готов", 
                                          font=('TkDefaultFont', 10, 'bold'))
        self.app.status_label.pack(pady=2) 

        # ═══════════════════════════════════════════════════════════════
        # Блок Инфо
        # ═══════════════════════════════════════════════════════════════
        stat_f = ttk.LabelFrame(l_cont, text="📊 Статистика"); stat_f.pack(fill="x", padx=5, pady=2)
        metrics = ["Режим", "Общий PnL ($)", "Плавающий PnL ($)", "Открыто Позиций", "Баланс QUOTE"]
        for i, m in enumerate(metrics):
            ttk.Label(stat_f, text=m, font=('TkDefaultFont', 9, 'bold')).grid(row=i, column=0, sticky='w', padx=5)
            v = self.app.floating_pnl if "Плавающий" in m else tk.StringVar(value="---")
            lbl = ttk.Label(stat_f, textvariable=v)
            lbl.grid(row=i, column=1, sticky='w', padx=5)
            self.app.metric_vars[m] = v
            if "Плавающий" in m: self.app.floating_pnl_label = lbl
        ttk.Button(stat_f, text="Сброс Статистики", command=self.app.reset_history).grid(row=len(metrics), columnspan=2, sticky="ew", padx=5, pady=(5,2))

        # --- ПРАВАЯ ПАНЕЛЬ ---
        right = ttk.Frame(paned); paned.add(right, weight=3)
        self.app.notebook = ttk.Notebook(right); self.app.notebook.pack(fill="both", expand=True)
        
        # Вкладка PnL (Canvas создается ChartSystem, но фрейм здесь)
        self.app.pnl_tab_frame = ttk.Frame(self.app.notebook); self.app.notebook.add(self.app.pnl_tab_frame, text="📈 Рост PnL")
        ttk.Button(self.app.pnl_tab_frame, text="Сохранить график PnL", command=self.app.save_pnl_chart).pack(fill='x', padx=5, pady=5)

        # Вкладка Позиций
        pos_t = ttk.Frame(self.app.notebook); self.app.notebook.add(pos_t, text="📋 Позиции")
        cols_orders = ('Пара', 'Тип', 'Qty', 'Вход', 'SL', 'TS', 'PnL ($)'); 
        self.app.open_orders_tree = ttk.Treeview(pos_t, columns=cols_orders, show='headings')
        col_widths = {'Пара': 90, 'Тип': 50, 'Qty': 70, 'Вход': 100, 'SL': 100, 'TS': 80, 'PnL ($)': 80}
        for col in cols_orders: 
             self.app.open_orders_tree.heading(col, text=col)
             self.app.open_orders_tree.column(col, width=col_widths.get(col, 70), anchor='center')
        self.app.open_orders_tree.pack(fill="both", expand=True)
        self.app.open_orders_tree.bind("<Double-Button-1>", self.app._on_open_orders_double_click)

        # Вкладка Истории
        hist_t = ttk.Frame(self.app.notebook); self.app.notebook.add(hist_t, text="📜 История")
        cols_hist = ('Время','Пара','Тип','Цена','Qty','PnL');
        self.app.trade_history_tree = ttk.Treeview(hist_t, columns=cols_hist, show='headings')
        for c in cols_hist: self.app.trade_history_tree.heading(c, text=c); self.app.trade_history_tree.column(c, width=80, anchor='center')
        self.app.trade_history_tree.pack(fill="both", expand=True)
        self.app.trade_history_tree.bind("<Double-Button-1>", self.app._on_history_double_click)
        ttk.Button(hist_t, text="Копировать историю", command=self.app.copy_trade_history).pack(fill='x', padx=5, pady=5)

        # Вкладка CVD Сигналов (НОВАЯ)
        cvd_tab = ttk.Frame(self.app.notebook); self.app.notebook.add(cvd_tab, text="🎯 CVD Сигналы")
        cols_cvd = ('Пара', 'Тип', 'Сила', 'R:R', 'Цена%', 'CVD%', 'Время');
        self.app.cvd_signals_tree = ttk.Treeview(cvd_tab, columns=cols_cvd, show='headings')
        cvd_widths = {'Пара': 100, 'Тип': 60, 'Сила': 60, 'R:R': 60, 'Цена%': 70, 'CVD%': 70, 'Время': 80}
        for col in cols_cvd:
            self.app.cvd_signals_tree.heading(col, text=col)
            self.app.cvd_signals_tree.column(col, width=cvd_widths.get(col, 70), anchor='center')
        self.app.cvd_signals_tree.pack(fill="both", expand=True)
        
        # Кнопка ручного сканирования
        self.app.btn_scan = ttk.Button(cvd_tab, text="🔍 Запустить CVD сканирование", 
                                       command=self.app.start_scanner_thread, style='Accent.TButton')
        self.app.btn_scan.pack(fill='x', padx=5, pady=5)

        # Вкладка Логов
        log_t = ttk.Frame(self.app.notebook); self.app.notebook.add(log_t, text="📝 Логи")
        self.app.log_text = scrolledtext.ScrolledText(log_t, wrap=tk.WORD, height=15, bg=self.tree_bg_color, fg='#00FF00', font=('Consolas',9))
        self.app.log_text.pack(fill="both", expand=True)
        ttk.Button(log_t, text="Копировать лог", command=self.app.copy_log).pack(fill='x', padx=5, pady=5)
        
        # Вкладка Черного Списка
        self.app.tab_blacklist = ttk.Frame(self.app.notebook)
        self.app.notebook.add(self.app.tab_blacklist, text='⛔ Blacklist (0)')
        
        # Вкладка Графика (через ChartSystem)
        if hasattr(self.app, 'chart_system'):
            self.app.chart_tab, self.app.chart_title_label, self.app.chart_info_label = \
                self.app.chart_system.setup_position_chart_tab(self.app.notebook, self.app.chart_tf)

        # Наполнение Черного Списка
        bl_frame = ttk.Frame(self.app.tab_blacklist)
        bl_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        bl_scrollbar = ttk.Scrollbar(bl_frame, orient=tk.VERTICAL)
        self.app.blacklist_listbox = tk.Listbox(bl_frame, yscrollcommand=bl_scrollbar.set, bg="#1a1a1a", fg="white", selectbackground="#404040")
        bl_scrollbar.config(command=self.app.blacklist_listbox.yview)
        bl_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.app.blacklist_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.app.blacklist_listbox.bind("<Double-Button-1>", self.app._on_blacklist_double_click)
        
        # V10.0: Инициализируем переменные если их нет
        self._ensure_legacy_vars()
    
    def _ensure_legacy_vars(self):
        """V10.2: Инициализация переменных"""
        app = self.app
        
        legacy_vars = {
            'scanner_volatile_mode': tk.IntVar(value=0),
            'trend_ema_period': tk.IntVar(value=10),
            'trend_local_filter_ema': tk.IntVar(value=50),
            'trend_mid_tf': tk.StringVar(value="15m"),
            'strategy_timeframe': tk.StringVar(value="5m"),
            'rev_bb_period': tk.IntVar(value=20),
            'rev_bb_std_dev': tk.DoubleVar(value=2.0),
            'rev_rsi_period': tk.IntVar(value=14),
            'rev_rsi_oversold': tk.DoubleVar(value=30.0),
            'rev_rsi_overbought': tk.DoubleVar(value=70.0),
            'parabolic_atr_multiplier': tk.DoubleVar(value=0),
            'mid_tf_slope_threshold': tk.DoubleVar(value=0),
            'ma_ema_period': tk.IntVar(value=200),
            'ma_adx_period': tk.IntVar(value=14),
            'ma_adx_threshold': tk.DoubleVar(value=25.0),
            'reversion_top_pairs_count': tk.IntVar(value=5),
            'use_limit_orders': tk.BooleanVar(value=False),
            'limit_order_lifetime': tk.IntVar(value=60),
            'scanner_min_tf_volume': tk.DoubleVar(value=50000),
            'scanner_timeframe': tk.StringVar(value="15m"),
            'be_profit_lock_usd': tk.DoubleVar(value=0.05),
            'trailing_pnl_peak_drop_pct': tk.DoubleVar(value=30.0),
            'trailing_pnl_stagnation_time': tk.IntVar(value=180),
            'per_pos_stagnation_time': tk.IntVar(value=300),
            # CVD переменные
            'cvd_scan_timeframe': tk.StringVar(value="5m"),
            'cvd_min_rvol': tk.DoubleVar(value=0.5),
            'cvd_min_strength': tk.IntVar(value=10),
            'cvd_min_rr': tk.DoubleVar(value=1.5),
            'cvd_max_signals': tk.IntVar(value=5),
            # V10.2 НОВЫЕ ПЕРЕМЕННЫЕ
            'cvd_min_price_pct': tk.DoubleVar(value=0.1),
            'cvd_min_cvd_pct': tk.DoubleVar(value=1.0),
        }
        
        for var_name, default_var in legacy_vars.items():
            if not hasattr(app, var_name):
                setattr(app, var_name, default_var)