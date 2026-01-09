import sys
import os
import ctypes
import ssl
import gc

def apply_patches():
    """
    Применяет критические исправления для среды Windows 7 / Python 3.8
    для режима HFT (High-Frequency Trading).
    """
    print(" Applying system optimizations...")
    
    # 1. Форсирование разрешения системного таймера (1мс вместо 15.6мс)
    # Это критично для time.sleep() и сетевых таймаутов
    try:
        winmm = ctypes.windll.winmm
        winmm.timeBeginPeriod(1)
        print(" System timer resolution set to 1ms.")
    except Exception as e:
        print(f" Failed to set timer resolution: {e}")

    # 2. Повышение приоритета процесса
    # Чтобы Windows не отбирала ресурсы у бота во время Пампа
    try:
        pid = os.getpid()
        handle = ctypes.windll.kernel32.OpenProcess(0x1F0FFF, False, pid) # PROCESS_ALL_ACCESS
        # REALTIME_PRIORITY_CLASS (0x100) опасно, используем HIGH_PRIORITY_CLASS (0x80)
        ctypes.windll.kernel32.SetPriorityClass(handle, 0x80) 
        print(" Process priority set to HIGH.")
    except Exception as e:
        print(f" Failed to set process priority: {e}")

    # 3. Отключение автоматического Garbage Collector (GC)
    # Чтобы бот не "замирал" на 50мс в случайный момент.
    # ВНИМАНИЕ: Нужно вызывать gc.collect() вручную в моменты простоя!
    # Пока оставляем включенным, но с увеличенным порогом, чтобы срабатывал реже.
    try:
        # Увеличиваем порог срабатывания GC (allocs, allocs, allocs)
        # Стандартно (700, 10, 10). Делаем (50000, 100, 100).
        gc.set_threshold(50000, 100, 100)
        print(" GC thresholds increased for HFT mode.")
    except Exception as e:
        print(f" Failed to tune GC: {e}")

    # 4. Исправление SSL Context для старых Windows
    # Python 3.8 на Win7 может не видеть новые корневые сертификаты Let's Encrypt и др.
    # Мы не можем пропатчить глобальный ssl, но мы подготовим certifi для использования в requests
    try:
        import certifi
        cert_path = certifi.where()
        
        # ✅ ИСПРАВЛЕНИЕ V9.62: Не перезаписываем os.environ, а добавляем конкретные ключи
        os.environ['SSL_CERT_FILE'] = cert_path
        os.environ['REQUESTS_CA_BUNDLE'] = cert_path
        
        print(f" SSL certificates pointed to: {cert_path}")
    except ImportError:
        print(" WARNING: 'certifi' library not found. SSL errors usually happen on Win7.")
        print("Please install: pip install certifi ujson")

    print(" Optimization complete.\n")

if __name__ == "__main__":
    apply_patches()
    input("Press Enter to exit...")