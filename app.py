# app.py
import os
import sys
from flask import Flask, jsonify, render_template, send_from_directory, request
import pandas as pd
from datetime import datetime, timezone, timedelta

# Добавляем корневую директорию проекта в sys.path для корректных импортов
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.append(PROJECT_ROOT)

try:
    from configs import settings
    from core.data_fetcher import get_forex_data
    from ts_logic.context_analyzer_1h import (
        find_swing_points,
        analyze_market_structure_points, 
        determine_overall_market_context, 
        determine_trend_lines_v2, 
        summarize_analysis 
    )
    from ts_logic.fractal_analyzer import analyze_fractal_setups # Хотя он не используется для analysisSummary напрямую, оставим для маркеров

except ImportError as e:
    print(f"КРИТИЧЕСКАЯ ОШИБКА ИМПОРТА в app.py: {e}")
    print(f"PROJECT_ROOT: {PROJECT_ROOT}")
    print(f"sys.path: {sys.path}")
    # Можно добавить более детальную информацию о том, какой именно импорт не удался, если e содержит эту инфу
    sys.exit(1)

app = Flask(__name__, static_folder='front', template_folder='front')

# Маппинг интервалов фронтенда на интервалы API (если они отличаются)
INTERVAL_MAP_API = {
    "1m": "1min", "3m": "3min", "5m": "5min", "15m": "15min",
    "30m": "30min", "45m": "45min", "1h": "1h", "2h": "2h",
    "4h": "4h", "8h": "8h", "1d": "1day", "1w": "1week", "1M": "1month"
}

# Таймфреймы, для которых будет выполняться полный анализ (структура, линии, сводка)
ANALYSIS_ENABLED_TIMEFRAMES = ['1h', '4h', '1d'] # Добавил '1d' для примера


@app.route('/')
def index():
    return render_template('index.html')

@app.route('/<path:filename>')
def serve_static(filename):
    # Обслуживание статических файлов из папки front (css, js)
    return send_from_directory(app.static_folder, filename)

@app.route('/api/chart_data')
def get_chart_data_endpoint(): # Переименовал, чтобы избежать конфликта с переменной
    symbol = settings.DEFAULT_SYMBOL
    interval_from_request = request.args.get('interval', settings.CONTEXT_TIMEFRAME) # '1h' по умолчанию
    api_interval = INTERVAL_MAP_API.get(interval_from_request, interval_from_request) # Конвертация в формат API

    end_date_str = request.args.get('endDate') # Дата для бэктеста YYYY-MM-DD
    end_date_dt = None
    if end_date_str:
        try:
            # Устанавливаем время на конец дня для выбранной даты в UTC
            end_date_dt = datetime.strptime(end_date_str, '%Y-%m-%d')
            end_date_dt = end_date_dt.replace(hour=23, minute=59, second=59, tzinfo=timezone.utc)
        except ValueError:
            print(f"API: Неверный формат endDate: {end_date_str}")
            end_date_dt = None # Если формат неверный, используем текущую дату

    # Определяем диапазон дат для запроса данных
    # Если есть endDate, то это конечная точка. Если нет, то это текущий момент.
    api_request_end_date = end_date_dt if end_date_dt else datetime.now(timezone.utc)
    # Запрашиваем данные за определенный период до конечной даты
    # Это значение можно вынести в settings
    days_to_fetch_for_api = settings.API_DAYS_TO_FETCH if hasattr(settings, 'API_DAYS_TO_FETCH') else 90 
    api_request_start_date = api_request_end_date - timedelta(days=days_to_fetch_for_api)

    market_data_df = get_forex_data(
        symbol=symbol, 
        interval=api_interval,
        start_date=api_request_start_date, # Используем рассчитанный диапазон
        end_date=api_request_end_date
    )

    # Инициализация ответа
    empty_summary_list = [] 
    if market_data_df is None or market_data_df.empty:
        print(f"API: Нет данных от get_forex_data для {symbol} {api_interval}")
        return jsonify({"ohlcv": [], "markers": [], "trendLines": [], "analysisSummary": empty_summary_list}), 200 # 200, т.к. запрос корректен, но данных нет

    # Приведение индекса к UTC, если он еще не такой
    if market_data_df.index.tzinfo is None:
        market_data_df = market_data_df.tz_localize('UTC')
    else:
        market_data_df = market_data_df.tz_convert('UTC')

    # Фильтрация данных до end_date_dt, если она была указана (для бэктеста)
    # Это гарантирует, что анализ не "заглядывает в будущее" относительно выбранной даты бэктеста
    market_data_df_for_analysis = market_data_df
    if end_date_dt: 
        market_data_df_for_analysis = market_data_df[market_data_df.index <= end_date_dt]
        if market_data_df_for_analysis.empty:
            print(f"API: Нет данных для анализа до {end_date_dt} для {symbol}")
            return jsonify({"ohlcv": [], "markers": [], "trendLines": [], "analysisSummary": empty_summary_list}), 200
    
    # Подготовка данных OHLCV для графика
    ohlcv_data_for_chart = []
    if not market_data_df_for_analysis.empty:
        # Отдаем на график весь загруженный диапазон до end_date_dt
        df_to_send_to_chart = market_data_df_for_analysis.copy()
        # Можно ограничить количество свечей для графика, если их слишком много
        # max_candles_for_chart = settings.MAX_CANDLES_FOR_CHART if hasattr(settings, 'MAX_CANDLES_FOR_CHART') else 500
        # if len(df_to_send_to_chart) > max_candles_for_chart:
        #     df_to_send_to_chart = df_to_send_to_chart.tail(max_candles_for_chart)

        for index_ts, row_data in df_to_send_to_chart.iterrows():
            time_iso_str = index_ts.isoformat() # Lightweight Charts ожидает ISO или timestamp
            ohlcv_data_for_chart.append({
                "time": time_iso_str, "open": row_data['open'], "high": row_data['high'],
                "low": row_data['low'], "close": row_data['close'],
            })

    # Инициализация данных для анализа
    marker_data_for_chart = []
    trend_lines_data_for_chart = [] 
    analysis_summary_list = empty_summary_list[:] # Копируем пустой список

    # Выполняем анализ только для разрешенных таймфреймов и если есть данные
    if interval_from_request in ANALYSIS_ENABLED_TIMEFRAMES and not market_data_df_for_analysis.empty:
        try:
            # Время последней свечи в анализируемом датафрейме
            current_processing_datetime_for_analysis = market_data_df_for_analysis.index[-1].to_pydatetime()
            
            # Параметр N для свингов зависит от таймфрейма (можно сделать более гибко через settings)
            swing_n_for_current_tf = settings.SWING_POINT_N 
            if interval_from_request == '4h': swing_n_for_current_tf = settings.SWING_POINT_N_4H if hasattr(settings, 'SWING_POINT_N_4H') else 3
            elif interval_from_request == '1d': swing_n_for_current_tf = settings.SWING_POINT_N_1D if hasattr(settings, 'SWING_POINT_N_1D') else 2


            swing_highs, swing_lows = find_swing_points(market_data_df_for_analysis, n=swing_n_for_current_tf)
            structure_points = analyze_market_structure_points(swing_highs, swing_lows)
            overall_market_context_text = determine_overall_market_context(structure_points) 

            # Собираем все точки для маркеров на графике
            all_points_for_markers = []
            if structure_points: all_points_for_markers.extend(structure_points)
            
            # Анализ сессионных фракталов (если он нужен для этого ТФ)
            # Для 1D ТФ сессионные фракталы могут быть не так актуальны
            session_fractal_and_setup_points_list = []
            if interval_from_request in ['1h', '4h']: # Пример, для каких ТФ это делать
                session_fractal_and_setup_points_list = analyze_fractal_setups(market_data_df_for_analysis, current_processing_datetime_for_analysis)
                if session_fractal_and_setup_points_list:
                    all_points_for_markers.extend(session_fractal_and_setup_points_list)
            
            all_points_for_markers.sort(key=lambda p: p['time']) # Сортируем по времени
            
            # Удаление дубликатов маркеров (если есть) - простая проверка по времени, типу и цене
            unique_points_for_plot_final = []
            seen_marker_keys_set = set()
            for point_item in all_points_for_markers:
                # Ключ для уникальности: время (до минут), тип, цена (округленная)
                time_key_str_marker = point_item['time'].strftime('%Y-%m-%dT%H:%M')
                price_key_rounded_marker = round(point_item['price'], 5) 
                marker_key = (time_key_str_marker, point_item.get('type', 'UNKNOWN'), price_key_rounded_marker)
                if marker_key not in seen_marker_keys_set:
                    unique_points_for_plot_final.append(point_item)
                    seen_marker_keys_set.add(marker_key)
            
            for point_to_plot in unique_points_for_plot_final:
                marker_data_for_chart.append({
                    "time": point_to_plot['time'].isoformat(), 
                    "type": point_to_plot.get('type', 'DEF_MARKER'), 
                    "price": point_to_plot['price'],
                })

            # Расчет линий тренда
            last_df_timestamp_for_trendlines_calc = market_data_df_for_analysis.index[-1] if not market_data_df_for_analysis.empty else None
            # Данные для расчета отступа линии (например, последние N свечей из анализируемого диапазона)
            data_for_offset_calc = market_data_df_for_analysis.tail(settings.TRENDLINE_OFFSET_CALC_CANDLES if hasattr(settings, 'TRENDLINE_OFFSET_CALC_CANDLES') else 50)
            
            if last_df_timestamp_for_trendlines_calc and not data_for_offset_calc.empty: 
                 points_window_for_trendlines = settings.TRENDLINE_POINTS_WINDOW_SIZE if hasattr(settings, 'TRENDLINE_POINTS_WINDOW_SIZE') else 5
                 trend_lines_data_for_chart = determine_trend_lines_v2(
                     swing_highs, 
                     swing_lows, 
                     last_df_timestamp_for_trendlines_calc, 
                     data_for_offset_calc, # Передаем DataFrame для расчета отступа
                     points_window_size=points_window_for_trendlines
                 )
            
            # Формируем сводку анализа (список элементов для Context)
            analysis_summary_list = summarize_analysis(
                market_data_df_for_analysis,
                structure_points, 
                session_fractal_and_setup_points_list, # Передаем, даже если пустой
                overall_market_context_text,
                trend_lines_data_for_chart 
            )
        except Exception as e_analysis:
            print(f"API: Ошибка во время выполнения аналитики для {interval_from_request}: {e_analysis}")
            import traceback
            print(traceback.format_exc())
            analysis_summary_list.append({'description': f"Ошибка при анализе ТФ {interval_from_request}.", 'status': False})
    else: # Если анализ для данного ТФ не включен или нет данных
        default_text_no_analysis = f"Анализ Context (структура, линии) доступен для ТФ: {', '.join(ANALYSIS_ENABLED_TIMEFRAMES)}."
        if interval_from_request not in ANALYSIS_ENABLED_TIMEFRAMES:
             analysis_summary_list.append({'description': default_text_no_analysis, 'status': False})
        elif market_data_df_for_analysis.empty : # Проверяем именно df для анализа
             analysis_summary_list.append({'description': "Нет данных для выполнения анализа.", 'status': False})


    return jsonify({
        "ohlcv": ohlcv_data_for_chart,
        "markers": marker_data_for_chart,
        "trendLines": trend_lines_data_for_chart,
        "analysisSummary": analysis_summary_list # Это должен быть список
    })

if __name__ == '__main__':
    # Запуск Flask-приложения для разработки
    # Убедитесь, что debug=True используется только для разработки
    app.run(debug=True, host='0.0.0.0', port=int(os.environ.get("PORT", 5000)))
