# configs/settings.py
import os
from dotenv import load_dotenv

# Загружаем переменные окружения из файла .env
load_dotenv()

# --- НАСТРОЙКИ API ---
API_KEY_TWELVE_DATA = os.getenv("TWELVE_DATA_API_KEY", "YOUR_TWELVE_DATA_API_KEY_HERE")
BASE_URL_TWELVE_DATA = "https://api.twelvedata.com"

# --- ОБЩИЕ НАСТРОЙКИ БОТА ---
DEFAULT_SYMBOL = "EUR/USD"

# --- НАСТРОЙКИ СТРАТЕГИИ 1H (Контекст) ---
CONTEXT_TIMEFRAME = "1h"
CONTEXT_OUTPUT_SIZE = 240 # Увеличим немного, чтобы было достаточно данных для больших N (примерно 10 дней для 1H)

# Параметр 'n' для функции find_swing_points ДЛЯ ОБЩЕЙ СТРУКТУРЫ РЫНКА (HH/HL/LH/LL).
# Определяет, сколько свечей с каждой стороны от центральной должно быть ниже (для максимума)
# или выше (для минимума), чтобы точка считалась свингом.
# n=1: 3-свечной паттерн (очень чувствительный, минорные свинги).
# n=2: 5-свечной паттерн (стандартные фракталы).
# n=3: 7-свечной паттерн.
# n=5: 11-свечной паттерн (более мажорные свинги).
# n=10: 21-свечной паттерн (очень мажорные свинги).
SWING_POINT_N = 5 # Для "мажорной" структуры рынка

# --- НАСТРОЙКИ СЕССИОННЫХ ФРАКТАЛОВ ---
# НОВЫЙ ПАРАМЕТР: 'n' для определения СЕССИОННЫХ фракталов.
# Обычно сессионные экстремумы более локальны.
# n=1: 3-свечная модель (рекомендуется для сессионных фракталов)
# n=2: 5-свечная модель
SESSION_FRACTAL_N = 1 # Для определения азиатских и нью-йоркских фракталов

# Время указано в UTC.
ASIAN_SESSION_START_HOUR_UTC = 0
ASIAN_SESSION_START_MINUTE = 0
ASIAN_SESSION_END_HOUR_UTC = 9
ASIAN_SESSION_END_MINUTE = 0

NY_SESSION_START_HOUR_UTC = 13
NY_SESSION_START_MINUTE = 0
NY_SESSION_END_HOUR_UTC = 22
NY_SESSION_END_MINUTE = 0

NY_SESSIONS_TO_CHECK_PREVIOUS_DAYS = 1
FRACTAL_PROXIMITY_THRESHOLD_PIPS = 15
PIP_VALUE_DEFAULT = 0.0001

# --- НАСТРОЙКИ ДЛЯ ГРАФИКОВ ---
CHARTS_DIRECTORY_NAME = "charts"

# configs/settings.py
TRENDLINE_OFFSET_PERCENTAGE = 0.001 
CHANNEL_HEIGHT_FACTOR = 2.0 
TRENDLINE_POINTS_WINDOW_SIZE = 5
TRENDLINE_SLOPE_TOLERANCE = 1e-9


# --- ПРОВЕРКА API КЛЮЧА ---
if API_KEY_TWELVE_DATA == "YOUR_TWELVE_DATA_API_KEY_HERE":
    print("ПРЕДУПРЕЖДЕНИЕ: API ключ для Twelve Data не установлен или используется значение по умолчанию.")
    print("Пожалуйста, установите переменную окружения TWELVE_DATA_API_KEY в файле .env")
