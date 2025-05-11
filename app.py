# app.py
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
        analyze_market_structure_points,
        determine_overall_market_context,
        determine_trend_lines_v2,
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

ANALYSIS_ENABLED_TIMEFRAMES = ['1h', '4h']


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

    end_date_str = request.args.get('endDate')
    end_date = None
    if end_date_str:
        try:
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d')
            end_date = end_date.replace(hour=23, minute=59, second=59, tzinfo=timezone.utc)
        except ValueError:
            end_date = None

    api_end_date = end_date if end_date else datetime.now(timezone.utc)
    days_to_fetch = 60
    api_start_date = api_end_date - timedelta(days=days_to_fetch)

    market_data_df = get_forex_data(
        symbol=symbol, interval=api_interval,
        start_date=api_start_date, end_date=api_end_date
    )

    empty_summary = []
    # Initialize fractal_count to 0
    fractal_count = 0
    # Initialize overall_context to a default value
    overall_context = "NEUTRAL (нет данных)"

    if market_data_df is None or market_data_df.empty:
        # Include fractal_count and overall_context in the response
        return jsonify({"ohlcv": [], "markers": [], "trendLines": [], "analysisSummary": empty_summary, "fractalCount": fractal_count, "overallContext": overall_context}), 500

    if market_data_df.index.tzinfo is None:
        market_data_df = market_data_df.tz_localize('UTC')
    else:
        market_data_df = market_data_df.tz_convert('UTC')

    market_data_df_filtered = market_data_df
    if end_date:
        market_data_df_filtered = market_data_df[market_data_df.index <= end_date]
        if market_data_df_filtered.empty:
            # Use the new empty_summary list and include fractal_count and overall_context
            return jsonify({"ohlcv": [], "markers": [], "trendLines": [], "analysisSummary": empty_summary, "fractalCount": fractal_count, "overallContext": overall_context}), 200

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
    analysis_summary_data = empty_summary[:] # Use a copy
    # Initialize fractal_count to 0
    fractal_count = 0
    # Initialize overall_context again for the analysis part
    overall_context = "NEUTRAL (недостаточно данных для анализа)"


    last_df_timestamp_for_trendlines = None
    data_for_offset_calculation = None

    if not market_data_df_filtered.empty:
        last_df_timestamp_for_trendlines = market_data_df_filtered.index[-1]
        if not isinstance(last_df_timestamp_for_trendlines, pd.Timestamp):
            last_df_timestamp_for_trendlines = None
        data_for_offset_calculation = market_data_df_filtered

    if interval_from_request in ANALYSIS_ENABLED_TIMEFRAMES and not market_data_df_filtered.empty:
        try:
            current_processing_datetime = market_data_df_filtered.index[-1].to_pydatetime()
            swing_n_for_current_tf = settings.SWING_POINT_N

            swing_highs, swing_lows = find_swing_points(market_data_df_filtered, n=swing_n_for_current_tf)
            structure_points = analyze_market_structure_points(swing_highs, swing_lows)
            overall_context = determine_overall_market_context(structure_points)

            all_points_for_plot = []
            if structure_points:
                all_points_for_plot.extend(structure_points)

            session_fractal_and_setup_points = analyze_fractal_setups(market_data_df_filtered, current_processing_datetime)
            if session_fractal_and_setup_points:
                all_points_for_plot.extend(session_fractal_and_setup_points)

                # MODIFIED: Count fractals based on overall_context and session
                relevant_fractals = [
                    p for p in session_fractal_and_setup_points
                    if p.get('type', '').startswith('F_') and (p.get('session') == 'Asia' or p.get('session') == 'NY (Day -1)')
                ]

                if "SHORT" in overall_context.upper():
                    # In a SHORT context, count only High fractals (potential long entries)
                    fractal_count = sum(1 for p in relevant_fractals if p.get('type', '').startswith('F_H_'))
                elif "LONG" in overall_context.upper():
                    # In a LONG context, count only Low fractals (potential short entries)
                    fractal_count = sum(1 for p in relevant_fractals if p.get('type', '').startswith('F_L_'))
                else:
                    # In NEUTRAL or other contexts, count all relevant session fractals
                    fractal_count = len(relevant_fractals)


            all_points_for_plot.sort(key=lambda x: x['time'])
            unique_points_for_plot = []
            seen_marker_keys = set()
            for point in all_points_for_plot:
                time_key_str = point['time'].strftime('%Y-%m-%dT%H:%M')
                price_key_rounded = round(point['price'], 5)
                key = (time_key_str, point.get('type', 'UNKNOWN_MARKER'), price_key_rounded)
                if key not in seen_marker_keys:
                    unique_points_for_plot.append(point)
                    seen_marker_keys.add(key)

            for point in unique_points_for_plot:
                marker_data.append({
                    "time": point['time'].isoformat(),
                    "type": point.get('type', 'UNKNOWN_MARKER'),
                    "price": point['price'],
                })

            if last_df_timestamp_for_trendlines and data_for_offset_calculation is not None and not data_for_offset_calculation.empty:
                 points_window = settings.TRENDLINE_POINTS_WINDOW_SIZE if hasattr(settings, 'TRENDLINE_POINTS_WINDOW_SIZE') else 5
                 trend_lines_data = determine_trend_lines_v2(
                     swing_highs,
                     swing_lows,
                     last_df_timestamp_for_trendlines,
                     data_for_offset_calculation,
                     points_window_size=points_window
                 )

            # summarize_analysis now returns a list of context items
            analysis_summary_data = summarize_analysis(
                market_data_df_filtered,
                structure_points,
                session_fractal_and_setup_points if session_fractal_and_setup_points else [],
                overall_context,
                trend_lines_data
            )
        except Exception as e_analysis:
            print(f"API: Ошибка во время выполнения аналитики для {interval_from_request}: {e_analysis}")
            import traceback
            print(traceback.format_exc())
            # Add error to the list
            analysis_summary_data.append({'description': f"Ошибка при анализе ТФ {interval_from_request}.", 'status': False})
            overall_context = "Ошибка анализа контекста" # Set context to error state

    else:
        default_text = f"Полный анализ (линии, структура HH/HL, сессии, сводка) доступен для ТФ: {', '.join(ANALYSIS_ENABLED_TIMEFRAMES)}."
        if interval_from_request not in ANALYSIS_ENABLED_TIMEFRAMES:
             analysis_summary_data.append({'description': default_text, 'status': False})
        elif market_data_df_filtered.empty:
             analysis_summary_data.append({'description': "Нет данных для анализа.", 'status': False})


    return jsonify({
        "ohlcv": ohlcv_data,
        "markers": marker_data,
        "trendLines": trend_lines_data,
        "analysisSummary": analysis_summary_data, # This is now a list of context items
        "fractalCount": fractal_count, # Include fractal count in the response
        "overallContext": overall_context # Include overall context in the response
    })

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
