import os
import sys
from flask import Flask, jsonify, render_template, send_from_directory, request
import pandas as pd
from datetime import datetime, timezone, timedelta

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.append(PROJECT_ROOT)

try:
    from configs import settings
    from core.data_fetcher import get_forex_data
    from ts_logic.context_analyzer_1h import (
        find_swing_points,
        analyze_market_structure_points, # Для маркеров HH/HL и контекста
        determine_overall_market_context, # Для текстовой сводки
        determine_trend_lines_v2,      # НОВАЯ функция для линий тренда
        summarize_analysis
    )
    from ts_logic.fractal_analyzer import analyze_fractal_setups

except ImportError as e:
    print(f"Ошибка импорта в app.py: {e}")
    sys.exit(1)

app = Flask(__name__, static_folder='front', template_folder='front')

INTERVAL_MAP_API = {
    "1m": "1min", "3m": "3min", "5m": "5min", "15m": "15min",
    "30m": "30min", "45m": "45min", "1h": "1h", "2h": "2h",
    "4h": "4h", "8h": "8h", "1d": "1day", "1w": "1week", "1M": "1month"
}

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/<path:filename>')
def serve_static(filename):
    return send_from_directory(app.static_folder, filename)

@app.route('/api/chart_data')
def get_chart_data():
    symbol = settings.DEFAULT_SYMBOL
    interval_from_request = request.args.get('interval', settings.CONTEXT_TIMEFRAME)
    api_interval = INTERVAL_MAP_API.get(interval_from_request, interval_from_request)
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
        symbol=symbol, interval=api_interval,
        start_date=api_start_date, end_date=api_end_date
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
    if end_date: # Фильтруем данные до указанной даты бэктеста
        market_data_df_filtered = market_data_df[market_data_df.index <= end_date]
        print(f"API: Отфильтровано данных до точной даты бэктеста {end_date}: {len(market_data_df_filtered)} свечей.")
        if market_data_df_filtered.empty:
            print(f"API: Нет данных до даты {end_date_str} после финальной фильтрации.")
            return jsonify({"ohlcv": [], "markers": [], "trendLines": [], "analysisSummary": empty_summary}), 200
    
    ohlcv_data = []
    if not market_data_df_filtered.empty:
        for index, row in market_data_df_filtered.iterrows():
            time_str = index.isoformat() # Используем ISO формат для времени
            ohlcv_data.append({
                "time": time_str, "open": row['open'], "high": row['high'],
                "low": row['low'], "close": row['close'],
            })

    # Инициализация данных для ответа
    marker_data = []
    trend_lines_data = [] 
    analysis_summary_data = empty_summary.copy() # Используем копию, чтобы не изменять оригинал

    last_df_timestamp_for_trendlines = None
    if not market_data_df_filtered.empty:
        last_df_timestamp_for_trendlines = market_data_df_filtered.index[-1]
        # Убедимся, что это Timestamp, если вдруг нет (хотя должно быть)
        if not isinstance(last_df_timestamp_for_trendlines, pd.Timestamp):
            print(f"API: Внимание! last_df_timestamp_for_trendlines не является pd.Timestamp: {type(last_df_timestamp_for_trendlines)}")
            last_df_timestamp_for_trendlines = None


    # Анализ проводится только для основного таймфрейма контекста
    if interval_from_request == settings.CONTEXT_TIMEFRAME and not market_data_df_filtered.empty:
        try:
            current_processing_datetime = market_data_df_filtered.index[-1].to_pydatetime()

            # 1. Находим все свинги (H_SWING, L_SWING)
            # Эти свинги будут использоваться для новой логики линий тренда
            # и для определения HH/HL/LH/LL (analyze_market_structure_points)
            swing_highs, swing_lows = find_swing_points(market_data_df_filtered, n=settings.SWING_POINT_N)
            
            # 2. Анализируем структуру для маркеров HH/HL и общего контекста (для текстовой сводки)
            structure_points = analyze_market_structure_points(swing_highs, swing_lows)
            overall_context = determine_overall_market_context(structure_points)
            print(f"API: Общий рыночный контекст (из HH/HL): {overall_context} для {interval_from_request}")

            # 3. Формируем маркеры для графика (HH, HL, LH, LL, H, L, сессионные фракталы, сетапы)
            all_points_for_plot = []
            if structure_points: # Добавляем HH, HL, LH, LL, H, L
                all_points_for_plot.extend(structure_points)
            
            # Добавляем сессионные фракталы и сетапы
            session_fractal_and_setup_points = analyze_fractal_setups(market_data_df_filtered, current_processing_datetime)
            if session_fractal_and_setup_points:
                all_points_for_plot.extend(session_fractal_and_setup_points)
            
            # Сортировка и удаление дубликатов маркеров
            all_points_for_plot.sort(key=lambda x: x['time'])
            unique_points_for_plot = []
            seen_marker_keys = set()
            for point in all_points_for_plot:
                # Ключ для уникальности маркера: время (до минут), тип, цена (округленная)
                time_key_str = point['time'].strftime('%Y-%m-%dT%H:%M')
                price_key_rounded = round(point['price'], 5) 
                key = (time_key_str, point.get('type', 'UNKNOWN_MARKER'), price_key_rounded)
                if key not in seen_marker_keys:
                    unique_points_for_plot.append(point)
                    seen_marker_keys.add(key)
            
            for point in unique_points_for_plot:
                marker_data.append({
                    "time": point['time'].isoformat(), # ISO формат для времени
                    "type": point.get('type', 'UNKNOWN_MARKER'), 
                    "price": point['price'],
                })

            # 4. Определяем линии тренда с использованием НОВОЙ ЛОГИКИ (determine_trend_lines_v2)
            # Передаем "сырые" swing_highs и swing_lows
            if last_df_timestamp_for_trendlines:
                 print(f"API: Вызов determine_trend_lines_v2 с last_df_timestamp: {last_df_timestamp_for_trendlines}")
                 trend_lines_data = determine_trend_lines_v2(swing_highs, swing_lows, last_df_timestamp_for_trendlines)
                 print(f"API: determine_trend_lines_v2 вернула {len(trend_lines_data)} линий.")
            else:
                print("API: last_df_timestamp_for_trendlines не определен, линии тренда не будут рассчитаны.")


            # 5. Формируем сводку анализа
            analysis_summary_data = summarize_analysis(
                market_data_df_filtered,
                structure_points, # structure_points (HH/HL) все еще нужны для текстовой сводки
                session_fractal_and_setup_points if session_fractal_and_setup_points else [],
                overall_context
            )
        except Exception as e_analysis:
            print(f"API: Ошибка во время выполнения аналитики для {interval_from_request}: {e_analysis}")
            import traceback
            print(traceback.format_exc())
            analysis_summary_data["Общая информация"].append({'description': f"Ошибка при анализе ТФ {interval_from_request}.", 'status': False})
    else:
        default_text = f"Анализ (структура, сетапы, линии, сводка) доступен только для ТФ {settings.CONTEXT_TIMEFRAME}."
        if interval_from_request != settings.CONTEXT_TIMEFRAME:
             analysis_summary_data["Общая информация"].append({'description': default_text, 'status': False})
        elif market_data_df_filtered.empty:
             analysis_summary_data["Общая информация"].append({'description': "Нет данных для анализа.", 'status': False})
        print(f"API: Анализ (структура, сетапы, линии, сводка) пропущен для таймфрейма {interval_from_request}.")


    print(f"API: Подготовлено {len(ohlcv_data)} свечей, {len(marker_data)} маркеров и {len(trend_lines_data)} линий тренда для ТФ {interval_from_request} (до {end_date_str or 'последняя дата'}).")

    return jsonify({
        "ohlcv": ohlcv_data,
        "markers": marker_data,
        "trendLines": trend_lines_data,
        "analysisSummary": analysis_summary_data
    })

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)