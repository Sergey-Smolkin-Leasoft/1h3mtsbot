# app.py
import os
import sys
from flask import Flask, jsonify, render_template, send_from_directory, request
import pandas as pd
from datetime import datetime, timezone, timedelta # Импортируем timedelta

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
        determine_trend_lines,
        summarize_analysis
    )
    from ts_logic.fractal_analyzer import analyze_fractal_setups

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
    Принимает параметр 'interval' для выбора таймфрейма
    и опциональный параметр 'endDate' для бэктеста.
    """
    symbol = settings.DEFAULT_SYMBOL
    interval = request.args.get('interval', settings.CONTEXT_TIMEFRAME)

    # Получаем опциональный параметр endDate
    end_date_str = request.args.get('endDate')
    end_date = None
    if end_date_str:
        try:
            # Пытаемся распарсить дату из строки ГГГГ-ММ-ДД
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d')
            # Устанавливаем время на конец дня (23:59:59) и локализуем в UTC
            # Twelve Data API ожидает UTC
            end_date = end_date.replace(hour=23, minute=59, second=59, tzinfo=timezone.utc) # Убрано .replace(tzinfo=timezone.utc) так как datetime уже aware
            print(f"API: Запрошена дата окончания бэктеста: {end_date}")
        except ValueError:
            print(f"API: Некорректный формат даты endDate: {end_date_str}. Игнорируется.")
            end_date = None

    # Определяем конечную дату для запроса к API
    # Если endDate не указан, используем текущее время в UTC
    api_end_date = end_date if end_date else datetime.now(timezone.utc)

    # --- ИЗМЕНЕННЫЙ РАСЧЕТ НАЧАЛЬНОЙ ДАТЫ ---
    # Всегда пытаемся загрузить данные за фиксированный период (например, 60 дней) до api_end_date.
    # Это обеспечивает более консистентное окно данных независимо от интервала для анализа и отображения.
    days_to_fetch = 60  # Загружаем данные за 60 дней
    api_start_date = api_end_date - timedelta(days=days_to_fetch)
    # --- КОНЕЦ ИЗМЕНЕННОГО РАСЧЕТА НАЧАЛЬНОЙ ДАТЫ ---

    print(f"API: Запрос данных для графика {symbol} ({interval}) в диапазоне: {api_start_date.strftime('%Y-%m-%d %H:%M:%S %Z')} - {api_end_date.strftime('%Y-%m-%d %H:%M:%S %Z')}...")

    # 1. Получение данных OHLCV по диапазону дат
    market_data_df = get_forex_data(
        symbol=symbol,
        interval=interval,
        start_date=api_start_date,
        end_date=api_end_date
    )

    if market_data_df is None or market_data_df.empty:
        print(f"API: Не удалось получить данные OHLCV для таймфрейма {interval} в запрошенном диапазоне.")
        return jsonify({"ohlcv": [], "markers": [], "trendLines": [], "analysisSummary": {"general": [], "detailed": []}}), 500

    if market_data_df.index.tzinfo is None:
        market_data_df = market_data_df.tz_localize('UTC')
    else:
         market_data_df = market_data_df.tz_convert('UTC')

    # 2. Фильтрация данных по точной дате окончания бэктеста (если указана)
    # Это гарантирует, что на график не попадут данные ПОСЛЕ выбранной даты бэктеста.
    market_data_df_filtered = market_data_df
    if end_date: # end_date - это конец выбранного дня бэктеста (уже в UTC)
        market_data_df_filtered = market_data_df[market_data_df.index <= end_date]
        print(f"API: Отфильтровано данных до точной даты бэктеста {end_date}: {len(market_data_df_filtered)} свечей.")
        if market_data_df_filtered.empty:
             print(f"API: Нет данных до даты {end_date_str} после финальной фильтрации.")
             return jsonify({"ohlcv": [], "markers": [], "trendLines": [], "analysisSummary": {"general": [], "detailed": []}}), 200

    # 3. Форматирование данных OHLCV для Lightweight Charts
    ohlcv_data = []
    for index, row in market_data_df_filtered.iterrows():
        time_str = index.isoformat()
        ohlcv_data.append({
            "time": time_str,
            "open": row['open'],
            "high": row['high'],
            "low": row['low'],
            "close": row['close'],
        })

    # 4. Анализ структуры, фракталов и линий тренда
    all_points_for_plot = []
    trend_lines_data = []
    analysis_summary_data = {"Общая информация": [], "Подробная информация": [], "Цели": [], "Точки набора": [], "Другое": []}


    if interval == settings.CONTEXT_TIMEFRAME and not market_data_df_filtered.empty:
        current_processing_datetime = market_data_df_filtered.index[-1].to_pydatetime()
        swing_highs, swing_lows = find_swing_points(market_data_df_filtered, n=settings.SWING_POINT_N)
        structure_points = analyze_market_structure_points(swing_highs, swing_lows)
        session_fractal_and_setup_points = analyze_fractal_setups(market_data_df_filtered, current_processing_datetime)
        overall_context = determine_overall_market_context(structure_points)
        print(f"API: Общий рыночный контекст для {interval} (до {end_date_str or 'последняя дата'}): {overall_context}")

        if structure_points:
            all_points_for_plot.extend(structure_points)
            trend_lines_data = determine_trend_lines(structure_points, overall_context)
            print(f"API: Определено {len(trend_lines_data)} линий тренда для {interval} (до {end_date_str or 'последняя дата'}).")
            analysis_summary_data = summarize_analysis(
                market_data_df_filtered,
                structure_points,
                session_fractal_and_setup_points,
                overall_context
            )
            print(f"API: Собрана сводка анализа для {interval} (до {end_date_str or 'последняя дата'}).")

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
        marker_data = []
        trend_lines_data = []
        # Обеспечиваем, чтобы analysis_summary_data всегда имела правильную структуру
        analysis_summary_data = {
            "Общая информация": [{'description': f"Анализ не проводился для ТФ {interval} или нет данных.", 'status': False}],
            "Подробная информация": [], "Цели": [], "Точки набора": [], "Другое": []
        }
        print(f"API: Анализ (структура, сетапы, линии, сводка) пропущен для таймфрейма {interval} или нет данных до {end_date_str or 'последняя дата'}.")

    print(f"API: Подготовлено {len(ohlcv_data)} свечей, {len(marker_data)} маркеров и {len(trend_lines_data)} линий тренда для ТФ {interval} (до {end_date_str or 'последняя дата'}).")

    return jsonify({
        "ohlcv": ohlcv_data,
        "markers": marker_data,
        "trendLines": trend_lines_data,
        "analysisSummary": analysis_summary_data
    })

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0')
