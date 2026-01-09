# SpreadMaker v10.15 — CVD Divergence Hunter & Trailing Grid

**Advanced Binance Futures trading terminal featuring automated market scanning and smart execution strategies.**

Advanced Binance Futures trading bot featuring automated CVD Divergence scanning and Trailing Grid strategies. Includes a real-time market scanner, interactive charts, and robust risk management. Built in Python for high-performance execution, supporting both Paper Trading and live API integration. Perfect for automated scalping.

---

## 🚀 Key Features

* **CVD Divergence Hunter:** Automatically scans hundreds of pairs to find volume/price imbalances (V10.x Smart Scoring).
* **Trailing Grid Strategy:** Dynamic grid that follows the price (Up/Down) to maximize profits during trends.
* **Real-time Scanner:** Built-in worker that updates a watchlist based on volatility, volume, and divergence strength.
* **Interactive Dashboard:** Tkinter-based UI with real-time logging, position tracking, and professional `mplfinance` charts.
* **Dual Mode:** Seamlessly switch between **Paper Trading** (simulation) and **Real Trading**.
* **Risk Management:** Integrated Stop Loss, Take Profit, and "Zero-Protect" logic to prevent invalid orders.

## 🛠 Tech Stack

* **Language:** Python 3.9+
* **GUI:** Tkinter (Custom Dark Theme)
* **Data Analysis:** NumPy, Pandas
* **Charts:** Matplotlib, Mplfinance
* **API:** Binance Futures REST API & WebSockets

## 📦 Quick Start

1.  **Clone the repo:**
    ```bash
    git clone [https://github.com/YOUR_USERNAME/SpreadMaker.git](https://github.com/YOUR_USERNAME/SpreadMaker.git)
    cd SpreadMaker
    ```
2.  **Install dependencies:**
    ```bash
    pip install numpy pandas matplotlib mplfinance requests websocket-client
    ```
3.  **Run the app:**
    ```bash
    python main.py
    ```

## ⚙️ Configuration
- Use the **Settings** panel in the UI to enter your Binance API Key and Secret.
- Adjust **CVD Strength** and **RVOL** thresholds to filter signals.
- Configure **Trailing intensity** and **Grid steps** for the Trailing strategy.

## ⚠️ Disclaimer
Trading cryptocurrencies involves significant risk. This bot is provided for educational purposes. Always test your strategies in **Paper Trading** mode before using real funds. Use at your own risk.

---
*Developed by cryptowolf programmer*
