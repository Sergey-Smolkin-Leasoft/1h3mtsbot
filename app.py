# app.py
import os
import sys
from flask import Flask, jsonify, render_template, send_from_directory

# Добавляем корень проекта в sys.path для корректных импортов
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.append(PROJECT_ROOT)

try:
    # Импортируем функции из ваших существующих модулей
    from configs import settings
    from core.data_fetcher import get_forex_data
    from ts_logic.context_analyzer_1h import (
        find_swing_points,
        analyze_market_structure_points,
        determine_overall_market_context # Хотя контекст не отправляем на фронтенд, функция может быть полезна
    )
    from ts_logic.fractal_analyzer import analyze_fractal_setups
    import pandas as pd # Импортируем pandas здесь, так как он используется в get_chart_data

except ImportError as e:
    print(f"Ошибка импорта в app.py: {e}")
    print("Убедитесь, что все файлы проекта находятся в правильных директориях,")
    print("и что в каждой поддиректории (core, ts_logic, utils, configs) есть файл __init__.py.")
    print(f"Текущий PROJECT_ROOT, добавленный в sys.path: {PROJECT_ROOT}")
    sys.exit(1)

# Указываем Flask искать шаблоны и статические файлы в папке 'front'
app = Flask(__name__, static_folder='front', template_folder='front')

# Маршрут для главной страницы (index.html)
@app.route('/')
def index():
    """Отдает главную HTML страницу."""
    # Flask будет искать index.html в папке 'front'
    return render_template('index.html')

# Явный маршрут для статических файлов из папки 'front'
# Это может помочь, если автоматическое обслуживание через static_folder не срабатывает
@app.route('/<path:filename>')
def serve_static(filename):
    """Отдает статические файлы из директории 'front'."""
    # Используем send_from_directory для явной отправки файла из статической папки
    return send_from_directory(app.static_folder, filename)


# API маршрут для получения данных графика
@app.route('/api/chart_data')
def get_chart_data():
    """
    Получает данные OHLCV и точки анализа, форматирует их и возвращает в JSON.
    """
    symbol = settings.DEFAULT_SYMBOL
    interval = settings.CONTEXT_TIMEFRAME
    outputsize = settings.CONTEXT_OUTPUT_SIZE

    print(f"API: Запрос данных для графика {symbol} ({interval}, {outputsize} свечей)...")

    # 1. Получение данных OHLCV
    market_data_df = get_forex_data(
        symbol=symbol,
        interval=interval,
        outputsize=outputsize
    )

    if market_data_df is None or market_data_df.empty:
        print("API: Не удалось получить данные OHLCV.")
        return jsonify({"ohlcv": [], "markers": []}), 500 # Возвращаем пустые данные и код ошибки

    # Убедимся, что индекс DatetimeIndex и в UTC для консистентности
    if market_data_df.index.tzinfo is None:
        market_data_df = market_data_df.tz_localize('UTC')
    else:
         market_data_df = market_data_df.tz_convert('UTC') # Конвертируем в UTC, если уже есть таймзона

    # Форматируем данные OHLCV для Lightweight Charts
    # Lightweight Charts ожидает timestamp в секундах или строку ISO 8601
    # Используем ISO 8601 для простоты
    ohlcv_data = []
    # Проходимся по DataFrame и форматируем каждую строку
    for index, row in market_data_df.iterrows():
         # Преобразуем Timestamp в строку ISO 8601 с учетом UTC
        time_str = index.isoformat()
        ohlcv_data.append({
            "time": time_str,
            "open": row['open'],
            "high": row['high'],
            "low": row['low'],
            "close": row['close'],
            # "volume": row.get('volume', 0) # Объем опционален
        })


    # 2. Анализ структуры и фракталов для маркеров
    # Используем время последней свечи для анализа сессионных фракталов
    current_processing_datetime = market_data_df.index[-1].to_pydatetime()

    # Анализ общей структуры рынка (HH, HL, LH, LL)
    swing_highs, swing_lows = find_swing_points(market_data_df, n=settings.SWING_POINT_N)
    structure_points = analyze_market_structure_points(swing_highs, swing_lows)

    # Анализ сессионных фракталов и поиск сетапов
    session_fractal_and_setup_points = analyze_fractal_setups(market_data_df, current_processing_datetime)

    # Объединяем все точки для графика
    all_points_for_plot = []
    if structure_points:
        all_points_for_plot.extend(structure_points)
    if session_fractal_and_setup_points:
        all_points_for_plot.extend(session_fractal_and_setup_points)

    # Удаляем дубликаты (могут быть точки с одинаковым временем и ценой, но разным типом,
    # или точки структуры и фракталы на одной свече)
    # Сортируем по времени, чтобы дубликаты были рядом
    all_points_for_plot.sort(key=lambda x: x['time'])

    unique_points_for_plot = []
    seen_keys = set()
    for point in all_points_for_plot:
        # Создаем уникальный ключ на основе времени (с точностью до минуты), типа и цены
        # Время приводим к строке ISO 8601 для хеширования
        time_key_str = point['time'].isoformat(timespec='minutes')
        # Цену округляем для сравнения
        price_key_rounded = round(point['price'], 5) # Округляем до 5 знаков после запятой
        key = (time_key_str, point.get('type', 'UNKNOWN'), price_key_rounded)

        if key not in seen_keys:
            unique_points_for_plot.append(point)
            seen_keys.add(key)

    # Форматируем данные маркеров для Lightweight Charts
    # Lightweight Charts ожидает timestamp в секундах или строку ISO 8601
    # Используем ISO 8601 для консистентности с OHLCV
    marker_data = []
    for point in unique_points_for_plot:
        # Преобразуем Timestamp в строку ISO 8601 с учетом UTC
        time_str = point['time'].isoformat()
        marker_data.append({
            "time": time_str,
            "type": point.get('type', 'UNKNOWN'), # Тип точки (HH, LL, F_H_AS, SETUP_Resist и т.д.)
            "price": point['price'],
            # 'details' и 'session' можно добавить, если нужно отображать их во всплывающих подсказках
            # "details": point.get('details', ''),
            # "session": point.get('session', ''),
        })

    print(f"API: Подготовлено {len(ohlcv_data)} свечей и {len(marker_data)} маркеров.")

    # Возвращаем данные в формате JSON
    return jsonify({
        "ohlcv": ohlcv_data,
        "markers": marker_data
    })

# Запуск сервера Flask
if __name__ == '__main__':
    # Для запуска используйте: python app.py
    # debug=True позволяет автоматически перезагружать сервер при изменениях кода
    app.run(debug=True)
