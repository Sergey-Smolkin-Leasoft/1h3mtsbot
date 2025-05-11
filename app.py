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
    # ... (остальная часть обработки ошибки импорта)
    sys.exit(1)

# Указываем Flask искать шаблоны и статические файлы в папке 'front'
app = Flask(__name__, static_folder='front', template_folder='front')

# --- СЛОВАРЬ ДЛЯ СОПОСТАВЛЕНИЯ ИНТЕРВАЛОВ ---
INTERVAL_MAP_API = {
    "1m": "1min",
    "3m": "3min",
    "5m": "5min",
    "15m": "15min",
    "30m": "30min",
    "45m": "45min", # На случай, если API поддерживает, а вы добавите на фронт
    "1h": "1h",
    "2h": "2h",
    "4h": "4h",
    "8h": "8h",   # На случай, если API поддерживает
    "1d": "1day", # API ожидает '1day'
    "1w": "1week", # API ожидает '1week'
    "1M": "1month" # API ожидает '1month' (обратите внимание на регистр 'M')
}
# Убедитесь, что значения в select на фронтенде (1m, 3m, 5m, 15m, 30m, 1h, 2h, 4h, 1d)
# являются ключами в этом словаре.

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
    """
    symbol = settings.DEFAULT_SYMBOL
    interval_from_request = request.args.get('interval', settings.CONTEXT_TIMEFRAME)

    # Преобразуем интервал в формат API
    api_interval = INTERVAL_MAP_API.get(interval_from_request, interval_from_request)
    # Если интервала нет в карте, используем его как есть (например, для '1h' это сработает)
    # но для '5m' он станет '5min'.

    print(f"API: Запрошен интервал '{interval_from_request}', используется для API '{api_interval}'")


    end_date_str = request.args.get('endDate')
    end_date = None
    if end_date_str:
        try:
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d')
            end_date = end_date.replace(hour=23, minute=59, second=59, tzinfo=timezone.utc)
            print(f"API: Запрошена дата окончания бэктеста: {end_date}")
        except ValueError:
            print(f"API: Некорректный формат даты endDate: {end_date_str}. Игнорируется.")
            end_date = None

    api_end_date = end_date if end_date else datetime.now(timezone.utc)
    days_to_fetch = 60
    api_start_date = api_end_date - timedelta(days=days_to_fetch)

    print(f"API: Запрос данных для графика {symbol} ({api_interval}) в диапазоне: {api_start_date.strftime('%Y-%m-%d %H:%M:%S %Z')} - {api_end_date.strftime('%Y-%m-%d %H:%M:%S %Z')}...")

    market_data_df = get_forex_data(
        symbol=symbol,
        interval=api_interval, # Используем преобразованный api_interval
        start_date=api_start_date,
        end_date=api_end_date
    )

    empty_summary = {"Общая информация": [], "Подробная информация": [], "Цели": [], "Точки набора": [], "Другое": []}
    if market_data_df is None or market_data_df.empty:
        print(f"API: Не удалось получить данные OHLCV для таймфрейма {api_interval} в запрошенном диапазоне.")
        return jsonify({"ohlcv": [], "markers": [], "trendLines": [], "analysisSummary": empty_summary}), 500

    if market_data_df.index.tzinfo is None:
        market_data_df = market_data_df.tz_localize('UTC')
    else:
        market_data_df = market_data_df.tz_convert('UTC')

    market_data_df_filtered = market_data_df
    if end_date:
        market_data_df_filtered = market_data_df[market_data_df.index <= end_date]
        print(f"API: Отфильтровано данных до точной даты бэктеста {end_date}: {len(market_data_df_filtered)} свечей.")
        if market_data_df_filtered.empty:
            print(f"API: Нет данных до даты {end_date_str} после финальной фильтрации.")
            return jsonify({"ohlcv": [], "markers": [], "trendLines": [], "analysisSummary": empty_summary}), 200
    
    ohlcv_data = []
    if not market_data_df_filtered.empty:
        for index, row in market_data_df_filtered.iterrows():
            time_str = index.isoformat()
            ohlcv_data.append({
                "time": time_str, "open": row['open'], "high": row['high'],
                "low": row['low'], "close": row['close'],
            })

    marker_data = []
    trend_lines_data = []
    analysis_summary_data = {
        "Общая информация": [], "Подробная информация": [], "Цели": [],
        "Точки набора": [], "Другое": []
    }

    # Используем interval_from_request для сравнения с settings.CONTEXT_TIMEFRAME,
    # так как CONTEXT_TIMEFRAME ('1h') соответствует формату фронтенда.
    if interval_from_request == settings.CONTEXT_TIMEFRAME and not market_data_df_filtered.empty:
        try:
            current_processing_datetime = market_data_df_filtered.index[-1].to_pydatetime()
            swing_highs, swing_lows = find_swing_points(market_data_df_filtered, n=settings.SWING_POINT_N)
            structure_points = analyze_market_structure_points(swing_highs, swing_lows)
            # Для session_fractal_and_setup_points используется settings.SESSION_FRACTAL_N, который не зависит от текущего интервала графика
            session_fractal_and_setup_points = analyze_fractal_setups(market_data_df_filtered, current_processing_datetime)
            overall_context = determine_overall_market_context(structure_points)
            
            print(f"API: Общий рыночный контекст для {interval_from_request} (до {end_date_str or 'последняя дата'}): {overall_context}")

            all_points_for_plot = []
            if structure_points:
                all_points_for_plot.extend(structure_points)
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
            
            for point in unique_points_for_plot:
                time_str = point['time'].isoformat()
                marker_data.append({
                    "time": time_str, "type": point.get('type', 'UNKNOWN'), "price": point['price'],
                })

            trend_lines_data = determine_trend_lines(structure_points, overall_context)
            analysis_summary_data = summarize_analysis(
                market_data_df_filtered,
                structure_points,
                session_fractal_and_setup_points if session_fractal_and_setup_points else [],
                overall_context
            )
        except Exception as e_analysis:
            print(f"API: Ошибка во время выполнения аналитики для {interval_from_request}: {e_analysis}")
            import traceback
            print(traceback.format_exc()) # Выводим полный traceback ошибки аналитики
            analysis_summary_data["Общая информация"].append({'description': f"Ошибка при анализе ТФ {interval_from_request}.", 'status': False})
    else:
        analysis_summary_data["Общая информация"].append({'description': f"Анализ не проводится для ТФ {interval_from_request}.", 'status': False})
        print(f"API: Анализ (структура, сетапы, линии, сводка) пропущен для таймфрейма {interval_from_request}.")

    print(f"API: Подготовлено {len(ohlcv_data)} свечей, {len(marker_data)} маркеров и {len(trend_lines_data)} линий тренда для ТФ {interval_from_request} (до {end_date_str or 'последняя дата'}).")

    return jsonify({
        "ohlcv": ohlcv_data,
        "markers": marker_data,
        "trendLines": trend_lines_data,
        "analysisSummary": analysis_summary_data
    })

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0')
