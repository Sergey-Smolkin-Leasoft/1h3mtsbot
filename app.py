# app.py
import os
import sys
from flask import Flask, jsonify, render_template, send_from_directory, request

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
        determine_overall_market_context,
        determine_trend_lines # Импортируем новую функцию
    )
    from ts_logic.fractal_analyzer import analyze_fractal_setups
    import pandas as pd

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
    return render_template('index.html')

# Явный маршрут для статических файлов из папки 'front'
@app.route('/<path:filename>')
def serve_static(filename):
    """Отдает статические файлы из директории 'front'."""
    return send_from_directory(app.static_folder, filename)


# API маршрут для получения данных графика
@app.route('/api/chart_data')
def get_chart_data():
    """
    Получает данные OHLCV и точки анализа, форматирует их и возвращает в JSON.
    Принимает параметр 'interval' для выбора таймфрейма.
    """
    symbol = settings.DEFAULT_SYMBOL
    # Получаем таймфрейм из параметров запроса. По умолчанию используем settings.CONTEXT_TIMEFRAME
    interval = request.args.get('interval', settings.CONTEXT_TIMEFRAME)
    outputsize = settings.CONTEXT_OUTPUT_SIZE # Возможно, outputsize тоже нужно будет адаптировать под ТФ

    print(f"API: Запрос данных для графика {symbol} ({interval}, {outputsize} свечей)...")

    # 1. Получение данных OHLCV
    market_data_df = get_forex_data(
        symbol=symbol,
        interval=interval, # Используем полученный таймфрейм
        outputsize=outputsize
    )

    if market_data_df is None or market_data_df.empty:
        print(f"API: Не удалось получить данные OHLCV для таймфрейма {interval}.")
        return jsonify({"ohlcv": [], "markers": [], "trendLines": []}), 500

    if market_data_df.index.tzinfo is None:
        market_data_df = market_data_df.tz_localize('UTC')
    else:
         market_data_df = market_data_df.tz_convert('UTC')

    ohlcv_data = []
    for index, row in market_data_df.iterrows():
        time_str = index.isoformat()
        ohlcv_data.append({
            "time": time_str,
            "open": row['open'],
            "high": row['high'],
            "low": row['low'],
            "close": row['close'],
        })

    # 2. Анализ структуры, фракталов и линий тренда
    # ВАЖНО: Функции анализа структуры и фракталов сейчас заточены под 1H.
    # Линии тренда будут определяться только если запрошен 1H.
    # Для других таймфреймов потребуется адаптация логики анализа.

    all_points_for_plot = []
    trend_lines_data = [] # Список для данных линий тренда

    # Запускаем анализ только если запрошенный таймфрейм соответствует тому, для которого написан анализ (1h)
    if interval == settings.CONTEXT_TIMEFRAME:
        current_processing_datetime = market_data_df.index[-1].to_pydatetime()

        # Анализ общей структуры рынка (HH, HL, LH, LL)
        swing_highs, swing_lows = find_swing_points(market_data_df, n=settings.SWING_POINT_N)
        structure_points = analyze_market_structure_points(swing_highs, swing_lows)

        # Анализ сессионных фракталов и поиск сетапов
        session_fractal_and_setup_points = analyze_fractal_setups(market_data_df, current_processing_datetime)

        # Определение общего контекста (нужен для логики линий тренда)
        overall_context = determine_overall_market_context(structure_points)
        print(f"API: Общий рыночный контекст для {interval}: {overall_context}")


        if structure_points:
            all_points_for_plot.extend(structure_points)
            # Определение линий тренда на основе структуры и контекста
            trend_lines_data = determine_trend_lines(structure_points, overall_context)
            print(f"API: Определено {len(trend_lines_data)} линий тренда для {interval}.")

        if session_fractal_and_setup_points:
            all_points_for_plot.extend(session_fractal_and_setup_points)

        all_points_for_plot.sort(key=lambda x: x['time'])

        unique_points_for_plot = []
        seen_keys = set()
        for point in all_points_for_plot:
            time_key_str = point['time'].isoformat(timespec='minutes')
            price_key_rounded = round(point['price'], 5)
            key = (time_key_str, point.get('type', 'UNKNOWN'), price_key_rounded)

            if key not in seen_keys:
                unique_points_for_plot.append(point)
                seen_keys.add(key)

        marker_data = []
        for point in unique_points_for_plot:
            time_str = point['time'].isoformat()
            marker_data.append({
                "time": time_str,
                "type": point.get('type', 'UNKNOWN'),
                "price": point['price'],
            })
    else:
        # Если таймфрейм не 1h, не запускаем текущий анализ структуры/фракталов/линий тренда
        marker_data = []
        trend_lines_data = []
        print(f"API: Анализ структуры, сетапов и линий тренда пропущен для таймфрейма {interval}, т.к. он отличается от {settings.CONTEXT_TIMEFRAME}.")


    print(f"API: Подготовлено {len(ohlcv_data)} свечей, {len(marker_data)} маркеров и {len(trend_lines_data)} линий тренда для ТФ {interval}.")

    # Возвращаем данные в формате JSON, включая trendLines
    return jsonify({
        "ohlcv": ohlcv_data,
        "markers": marker_data,
        "trendLines": trend_lines_data # Добавляем данные о линиях тренда
    })

# Запуск сервера Flask
if __name__ == '__main__':
    app.run(debug=True)