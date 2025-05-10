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
            # Пытаемся распарсить дату из строки YYYY-MM-DD
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d')
            # Устанавливаем время на конец дня (23:59:59) и локализуем в UTC
            # Twelve Data API ожидает UTC
            end_date = end_date.replace(hour=23, minute=59, second=59).replace(tzinfo=timezone.utc)
            print(f"API: Запрошена дата окончания бэктеста: {end_date}")
        except ValueError:
            print(f"API: Некорректный формат даты endDate: {end_date_str}. Игнорируется.")
            end_date = None

    # Определяем конечную дату для запроса к API
    # Если endDate не указан, используем текущее время в UTC
    api_end_date = end_date if end_date else datetime.now(timezone.utc)

    # Определяем начальную дату для запроса к API
    # Цель: получить достаточно данных до api_end_date для анализа.
    # Рассчитаем начальную дату, отступив назад на определенное количество баров.
    # Например, хотим видеть последние 200 баров до api_end_date.
    target_bars_for_analysis = 200 # Желаемое количество баров для анализа

    # Примерная длительность интервалов в timedelta (для расчета start_date)
    # Это очень упрощенный расчет, который может быть неточным для всех интервалов и инструментов.
    # Для более точного расчета может потребоваться знание торговых часов или использование более сложной логики.
    interval_map = {
        '1m': timedelta(minutes=1),
        '3m': timedelta(minutes=3),
        '5m': timedelta(minutes=5),
        '15m': timedelta(minutes=15),
        '30m': timedelta(minutes=30),
        '1h': timedelta(hours=1),
        '2h': timedelta(hours=2),
        '4h': timedelta(hours=4),
        '1d': timedelta(days=1),
        # Добавьте другие интервалы, если используются
    }

    interval_duration = interval_map.get(interval, timedelta(hours=1)) # По умолчанию 1 час

    # Рассчитываем примерную начальную дату
    api_start_date = api_end_date - (interval_duration * target_bars_for_analysis)
    # Отступаем еще немного назад, чтобы гарантировать получение достаточного количества данных
    api_start_date -= timedelta(days=5) # Добавляем запас в 5 дней (можно настроить)


    print(f"API: Запрос данных для графика {symbol} ({interval}) в диапазоне: {api_start_date.strftime('%Y-%m-%d %H:%M:%S')} - {api_end_date.strftime('%Y-%m-%d %H:%M:%S')}...")

    # 1. Получение данных OHLCV по диапазону дат
    # Используем start_date и end_date вместо outputsize
    market_data_df = get_forex_data(
        symbol=symbol,
        interval=interval,
        start_date=api_start_date,
        end_date=api_end_date
    )

    if market_data_df is None or market_data_df.empty:
        print(f"API: Не удалось получить данные OHLCV для таймфрейма {interval} в запрошенном диапазоне.")
        return jsonify({"ohlcv": [], "markers": [], "trendLines": [], "analysisSummary": {"general": [], "detailed": []}}), 500

    # Данные уже должны быть в UTC благодаря настройке в data_fetcher
    # Но на всякий случай проверим и сконвертируем
    if market_data_df.index.tzinfo is None:
        market_data_df = market_data_df.tz_localize('UTC')
    else:
         market_data_df = market_data_df.tz_convert('UTC')


    # 2. Фильтрация данных по точной дате окончания бэктеста (если указана)
    # Twelve Data API может вернуть данные немного после запрошенной end_date.
    # Фильтруем DataFrame, оставляя только свечи до end_date (которая соответствует концу выбранного дня) включительно.
    market_data_df_filtered = market_data_df # Начинаем с полных данных из API
    if end_date: # end_date - это конец выбранного дня бэктеста
        market_data_df_filtered = market_data_df[market_data_df.index <= end_date]
        print(f"API: Отфильтровано данных до точной даты бэктеста {end_date}: {len(market_data_df_filtered)} свечей.")
        # Если после фильтрации данных нет, возвращаем пустой ответ
        if market_data_df_filtered.empty:
             print(f"API: Нет данных до даты {end_date_str} после финальной фильтрации.")
             return jsonify({"ohlcv": [], "markers": [], "trendLines": [], "analysisSummary": {"general": [], "detailed": []}}), 200 # 200 OK, но данных нет


    # 3. Форматирование данных OHLCV для Lightweight Charts
    ohlcv_data = []
    # Используем только отфильтрованный DataFrame для отправки на фронтенд
    for index, row in market_data_df_filtered.iterrows():
        # Временные метки уже в UTC, форматируем в ISO 8601
        time_str = index.isoformat()
        ohlcv_data.append({
            "time": time_str,
            "open": row['open'],
            "high": row['high'],
            "low": row['low'],
            "close": row['close'],
        })

    # 4. Анализ структуры, фракталов и линий тренда
    # ВАЖНО: Функции анализа структуры и фракталов сейчас заточены под 1H.
    # Линии тренда и сводка анализа будут определяться только если запрошен 1H
    # И если есть данные после фильтрации.
    # Для других таймфреймов потребуется адаптация логики анализа.

    all_points_for_plot = []
    trend_lines_data = [] # Список для данных линий тренда
    analysis_summary_data = {"general": [], "detailed": []} # Словарь для сводки анализа

    # Запускаем анализ только если запрошенный таймфрейм соответствует тому, для которого написан анализ (1h)
    # И если есть данные после фильтрации
    if interval == settings.CONTEXT_TIMEFRAME and not market_data_df_filtered.empty:
        # Анализ производится на отфильтрованных данных
        current_processing_datetime = market_data_df_filtered.index[-1].to_pydatetime()

        # Анализ общей структуры рынка (HH, HL, LH, LL)
        # Используем отфильтрованный DataFrame для анализа свингов
        swing_highs, swing_lows = find_swing_points(market_data_df_filtered, n=settings.SWING_POINT_N)
        structure_points = analyze_market_structure_points(swing_highs, swing_lows)

        # Анализ сессионных фракталов и поиск сетапов
        # analyze_fractal_setups использует current_processing_datetime и DataFrame.
        # Убедитесь, что внутренняя логика analyze_fractal_setups корректно работает с обрезанными данными.
        session_fractal_and_setup_points = analyze_fractal_setups(market_data_df_filtered, current_processing_datetime)

        # Определение общего контекста (нужен для логики линий тренда и сводки)
        overall_context = determine_overall_market_context(structure_points)
        print(f"API: Общий рыночный контекст для {interval} (до {end_date_str or 'последняя дата'}): {overall_context}")


        if structure_points:
            all_points_for_plot.extend(structure_points)
            # Определение линий тренда на основе структуры и контекста
            trend_lines_data = determine_trend_lines(structure_points, overall_context)
            print(f"API: Определено {len(trend_lines_data)} линий тренда для {interval} (до {end_date_str or 'последняя дата'}).")

            # Сбор сводки анализа
            # Передаем отфильтрованный DataFrame в summarize_analysis
            analysis_summary_data = summarize_analysis(
                market_data_df_filtered, # Передаем отфильтрованные данные
                structure_points,
                session_fractal_and_setup_points,
                overall_context
            )
            print(f"API: Собрана сводка анализа для {interval} (до {end_date_str or 'последняя дата'}).")


        if session_fractal_and_setup_points:
            all_points_for_plot.extend(session_fractal_and_setup_points)

        # При бэктесте точки анализа должны быть до end_date
        # Фильтрация точек анализа уже происходит в summarize_analysis и determine_trend_lines
        # Здесь просто сортируем и убираем дубликаты из объединенного списка для маркеров на графике.
        all_points_for_plot.sort(key=lambda x: x['time'])

        unique_points_for_plot = []
        seen_keys = set()
        for point in all_points_for_plot:
            # Точки анализа уже должны быть отфильтрованы по времени в функциях determine_trend_lines и summarize_analysis
            # Но на всякий случай можно добавить проверку здесь, если логика анализа не гарантирует фильтрацию по end_date
            # if end_date and point['time'] > end_date:
            #      continue # Пропускаем точки после даты бэктеста

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
        # Если таймфрейм не 1h или данных нет, не запускаем текущий анализ
        marker_data = []
        trend_lines_data = []
        analysis_summary_data = {"general": [], "detailed": []}
        print(f"API: Анализ (структура, сетапы, линии, сводка) пропущен для таймфрейма {interval} или нет данных до {end_date_str or 'последняя дата'}.")


    print(f"API: Подготовлено {len(ohlcv_data)} свечей, {len(marker_data)} маркеров и {len(trend_lines_data)} линий тренда для ТФ {interval} (до {end_date_str or 'последняя дата'}).")

    # Возвращаем данные в формате JSON, включая trendLines и analysisSummary
    return jsonify({
        "ohlcv": ohlcv_data,
        "markers": marker_data,
        "trendLines": trend_lines_data,
        "analysisSummary": analysis_summary_data
    })

# Запуск сервера Flask
if __name__ == '__main__':
    # Устанавливаем хост '0.0.0.0' чтобы сервер был доступен извне localhost, если потребуется
    # В продакшене используйте более надежный WSGI сервер
    app.run(debug=True, host='0.0.0.0')
