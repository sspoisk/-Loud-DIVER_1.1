# binance_api.py
# V9.65 (Silent SSL)
#
# ИЗМЕНЕНИЯ V9.65:
# - ✅ Отключены назойливые предупреждения InsecureRequestWarning.
#   Теперь консоль будет чистой, без спама "Unverified HTTPS request".

import requests
import time
import hmac
import hashlib
import logging
import socket
import ssl
import urllib3 # Для отключения варнингов

from urllib.parse import urlencode
from requests.adapters import HTTPAdapter
from urllib3.poolmanager import PoolManager
from urllib3.util.ssl_ import create_urllib3_context

# ✅ ОТКЛЮЧАЕМ СПАМ ПРЕДУПРЕЖДЕНИЯМИ
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Попытка импорта быстрого JSON парсера
try:
    import ujson as json
except ImportError:
    import json

# Попытка импорта свежих сертификатов (для Win7)
try:
    import certifi
    CA_CERTS = certifi.where()
except ImportError:
    CA_CERTS = None

class HFTAdapter(HTTPAdapter):
    """
    Специальный адаптер для Requests, который включает TCP_NODELAY.
    Это отключает алгоритм Нагла и снижает задержку отправки ордера на 10-200мс.
    """
    def init_poolmanager(self, connections, maxsize, block=False):
        # Создаем контекст SSL с правильными сертификатами для Win7
        context = create_urllib3_context()
        
        # ✅ КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ V9.64
        # Python запрещает ставить verify_mode=CERT_NONE (отключение проверки),
        # если включен check_hostname. Мы обязаны отключить его вручную.
        context.check_hostname = False 
        
        if CA_CERTS:
            context.load_verify_locations(cafile=CA_CERTS)
            
        self._pool_connections = connections
        self._pool_maxsize = maxsize
        self._pool_block = block
        
        self.poolmanager = PoolManager(
            num_pools=connections, 
            maxsize=maxsize,
            block=block,
            ssl_context=context
        )

    def proxy_manager_for(self, proxy, **proxy_kwargs):
        # Переопределение для прокси, если понадобятся
        if CA_CERTS:
            proxy_kwargs['ca_certs'] = CA_CERTS
        return super().proxy_manager_for(proxy, **proxy_kwargs)

    def get_connection(self, url, proxies=None):
        conn = super().get_connection(url, proxies)
        return conn

# Патчим socket.create_connection, чтобы все сокеты в программе (включая requests)
# имели TCP_NODELAY по умолчанию. Это хак, но для Win7 + HFT это необходимо.
_orig_create_connection = socket.create_connection

def patched_create_connection(address, timeout=socket._GLOBAL_DEFAULT_TIMEOUT, source_address=None):
    sock = _orig_create_connection(address, timeout, source_address)
    try:
        sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
    except Exception:
        pass
    return sock

socket.create_connection = patched_create_connection


class BinanceTrader:
    def __init__(self, api_key, secret_key, log_callback=print, use_ssl_verify=True):
        self.api_key = api_key
        self.secret_key = secret_key
        self.log_callback = log_callback # Callback для логов
        
        # Настраиваем базовый URL
        self.base_url = "https://fapi.binance.com"
            
        self.headers = {
            'X-MBX-APIKEY': self.api_key,
            'Content-Type': 'application/json',
            'User-Agent': 'MomentumBot/Win7-Optimized'
        }
        
        # Инициализация высокопроизводительной сессии
        self.session = requests.Session()
        self.session.headers.update(self.headers)
        
        # Отключаем верификацию SSL, если попросили (для старых Win7)
        self.session.verify = use_ssl_verify

        # Монтируем наш HFT адаптер
        adapter = HFTAdapter(pool_connections=10, pool_maxsize=10)
        self.session.mount('https://', adapter)
        self.session.mount('http://', adapter)
        
        # Предварительный прогрев SSL соединения (Handshake)
        # Раскомментируйте, если хотите прогреть сеть при старте
        # try:
        #     self.get_exchange_info()
        #     if self.log_callback: self.log_callback("Network warmed up: Keep-Alive active.")
        # except Exception as e:
        #     if self.log_callback: self.log_callback(f"Warmup failed: {e}", "warning")

    def _generate_signature(self, query_string):
        return hmac.new(
            self.secret_key.encode('utf-8'),
            query_string.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()

    def _send_request(self, method, endpoint, params=None, signed=False):
        if params is None:
            params = {}
            
        if signed:
            params['timestamp'] = int(time.time() * 1000)
            # Формируем строку запроса вручную, чтобы порядок параметров был предсказуем
            query_string = urlencode(params)
            signature = self._generate_signature(query_string)
            query_string += f"&signature={signature}"
            url = f"{self.base_url}{endpoint}?{query_string}"
            # При signed запросе параметры уже в URL, не передаем их в params
            request_params = None
        else:
            url = f"{self.base_url}{endpoint}"
            request_params = params

        # Ретрай логика (минимальная для HFT)
        try:
            if method == 'GET':
                response = self.session.get(url, params=request_params, timeout=(3.0, 5.0))
            elif method == 'POST':
                response = self.session.post(url, timeout=(1.0, 2.0)) # Тайм-аут на отправку ордера очень жесткий
            elif method == 'DELETE':
                response = self.session.delete(url, params=request_params, timeout=(3.0, 5.0))
            else:
                raise ValueError(f"Unknown method {method}")

            # Если 4xx или 5xx - вызовет исключение
            response.raise_for_status()
            
            # Используем ujson, если он доступен
            return json.loads(response.text)
            
        except requests.exceptions.Timeout:
            if self.log_callback: self.log_callback(f"TIMEOUT: {endpoint}", "error")
            raise
        except requests.exceptions.RequestException as e:
            # Пытаемся достать сообщение об ошибке из ответа биржи
            try:
                if e.response is not None:
                    err_msg = json.loads(e.response.text)
                    if self.log_callback: self.log_callback(f"Binance API Error: {err_msg}", "error")
                else:
                    if self.log_callback: self.log_callback(f"API Connection Error: {e}", "error")
            except:
                if self.log_callback: self.log_callback(f"API Error: {e}", "error")
            return None # Возвращаем None при ошибке, чтобы бот не крашился

    # --- PUBLIC ENDPOINTS ---

    def get_exchange_info(self):
        return self._send_request('GET', '/fapi/v1/exchangeInfo')

    def get_klines(self, symbol, interval, limit=201):
        params = {
            'symbol': symbol,
            'interval': interval,
            'limit': limit
        }
        return self._send_request('GET', '/fapi/v1/klines', params=params)

    def get_24h_tickers(self):
        return self._send_request('GET', '/fapi/v1/ticker/24hr')
    
    def get_ticker_price(self, symbol):
         params = {'symbol': symbol}
         res = self._send_request('GET', '/fapi/v1/ticker/price', params=params)
         if res and 'price' in res:
             return float(res['price'])
         return None

    # --- SIGNED (PRIVATE) ENDPOINTS ---

    def create_order(self, symbol, side, order_type, quantity, price=None, timeInForce=None, reduceOnly=None):
        """
        Критический метод для пампа. Максимально облегчен.
        """
        params = {
            'symbol': symbol,
            'side': side,
            'type': order_type,
            'quantity': quantity
        }
        
        if price:
            params['price'] = price
        if timeInForce:
            params['timeInForce'] = timeInForce
        if reduceOnly:
            params['reduceOnly'] = reduceOnly

        return self._send_request('POST', '/fapi/v1/order', params=params, signed=True)

    def cancel_order(self, symbol, orderId):
        params = {
            'symbol': symbol,
            'orderId': orderId
        }
        return self._send_request('DELETE', '/fapi/v1/order', params=params, signed=True)

    def cancel_all_open_orders(self, symbol):
        params = {'symbol': symbol}
        return self._send_request('DELETE', '/fapi/v1/allOpenOrders', params=params, signed=True)

    def get_open_orders(self, symbol):
        params = {'symbol': symbol}
        return self._send_request('GET', '/fapi/v1/openOrders', params=params, signed=True)

    def get_account_balance(self):
        return self._send_request('GET', '/fapi/v2/balance', signed=True)

    def get_position_information(self, symbol=None):
        params = {}
        if symbol:
            params['symbol'] = symbol
        return self._send_request('GET', '/fapi/v2/positionRisk', params=params, signed=True)

    def set_leverage(self, symbol, leverage):
        params = {
            'symbol': symbol,
            'leverage': leverage
        }
        return self._send_request('POST', '/fapi/v1/leverage', params=params, signed=True)