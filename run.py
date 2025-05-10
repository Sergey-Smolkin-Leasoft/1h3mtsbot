# run.py
import os
import sys
from datetime import datetime, timezone
import pandas as pd # Для проверки market_data_df.empty

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.append(PROJECT_ROOT)

try:
    from configs import settings
    from core.data_fetcher import get_forex_data
    from ts_logic.context_analyzer_1h import (
        find_swing_points,
        analyze_market_structure_points,
        determine_overall_market_context
    )
    from ts_logic.fractal_analyzer import analyze_fractal_setups 
    from utils.plotter import plot_market_structure
except ImportError as e:
    print(f"Ошибка импорта: {e}")
    print("Убедитесь, что все файлы проекта находятся в правильных директориях,")
    print("и что в каждой поддиректории (core, ts_logic, utils, configs) есть файл __init__.py.")
    print(f"Текущий PROJECT_ROOT, добавленный в sys.path: {PROJECT_ROOT}")
    sys.exit(1)

def run_analysis():
    """
    Основная функция для запуска анализа рыночного контекста и сессионных фракталов.
    """
    print(f"--- Запуск анализа для символа: {settings.DEFAULT_SYMBOL} ---") # Оставим этот высокоуровневый лог
    # print(f"API ключ используется: ...{settings.API_KEY_TWELVE_DATA[-4:] if settings.API_KEY_TWELVE_DATA else 'НЕ УСТАНОВЛЕН'}")

    charts_path = os.path.join(PROJECT_ROOT, settings.CHARTS_DIRECTORY_NAME)
    if not os.path.exists(charts_path):
        try:
            os.makedirs(charts_path)
            # print(f"run.py: Директория для графиков создана: {charts_path}")
        except OSError as e:
            print(f"run.py: Ошибка при создании директории {charts_path}: {e}")
            return

    # print(f"\nrun.py: Получение данных для {settings.DEFAULT_SYMBOL}...")
    market_data_df = get_forex_data(
        symbol=settings.DEFAULT_SYMBOL,
        interval=settings.CONTEXT_TIMEFRAME,
        outputsize=settings.CONTEXT_OUTPUT_SIZE
    )

    if market_data_df is None or market_data_df.empty:
        print(f"run.py: Не удалось получить данные для {settings.DEFAULT_SYMBOL}. Анализ прерван.")
        return

    if market_data_df.index.tzinfo is None:
        # print("run.py: ВНИМАНИЕ: Индекс DataFrame не имеет таймзоны. Локализация в UTC.")
        market_data_df = market_data_df.tz_localize('UTC')
    
    current_processing_datetime = market_data_df.index[-1].to_pydatetime()
    # print(f"run.py: Анализ будет производиться относительно времени последней свечи: {current_processing_datetime.strftime('%Y-%m-%d %H:%M:%S %Z')}")

    # --- 1. Анализ общей структуры рынка (HH, HL, LH, LL) ---
    # print(f"\nrun.py: Поиск свингов для общей структуры {settings.DEFAULT_SYMBOL}...")
    swing_highs, swing_lows = find_swing_points(market_data_df, n=settings.SWING_POINT_N)
    
    all_points_for_plot = [] 

    # if not swing_highs and not swing_lows: 
        # print(f"run.py: Не найдено достаточного количества свингов для общей структуры {settings.DEFAULT_SYMBOL}.")
    
    # print(f"\nrun.py: Анализ общей рыночной структуры для {settings.DEFAULT_SYMBOL}...")
    structure_points = analyze_market_structure_points(swing_highs, swing_lows)
    
    if not structure_points:
        # print(f"run.py: Не удалось определить значимые точки общей структуры рынка (HH, HL, LH, LL) для {settings.DEFAULT_SYMBOL}.")
        pass
    else:
        # print(f"\nrun.py: Найденные точки общей структуры для {settings.DEFAULT_SYMBOL}:")
        # for sp in structure_points[-5:]: 
            # price_str = f"{sp['price']:.5f}" if isinstance(sp.get('price'), float) else str(sp.get('price'))
            # print(f"  Время: {sp['time']}, Цена: {price_str}, Тип: {sp['type']}")
        all_points_for_plot.extend(structure_points)
        
        overall_context = determine_overall_market_context(structure_points)
        # print(f"\nrun.py: Общий рыночный контекст для {settings.DEFAULT_SYMBOL}: {overall_context}")
        # Можно вывести общий контекст, если он важен
        print(f"run.py: Общий рыночный контекст: {overall_context}")


    # --- 2. Анализ сессионных фракталов и поиск сетапов ---
    session_fractal_and_setup_points = analyze_fractal_setups(market_data_df, current_processing_datetime)
    
    if session_fractal_and_setup_points:
        # print(f"\nrun.py: Найдены сессионные фракталы и/или точки сетапа:")
        # for p in session_fractal_and_setup_points[-10:]:
             # details_str = f" - {p['details']}" if 'details' in p and p['details'] else ""
             # print(f"  Время: {p['time']}, Цена: {p['price']:.5f}, Тип: {p['type']}, Сессия: {p['session']}{details_str}")
        all_points_for_plot.extend(session_fractal_and_setup_points)
        
        # Подсчитаем количество именно сетапов
        actual_setup_points_count = sum(1 for p in session_fractal_and_setup_points if 'SETUP' in p.get('type', ''))
        if actual_setup_points_count > 0:
             print(f"run.py: Найдено {actual_setup_points_count} точек сетапа.")
        # else:
            # print(f"\nrun.py: Сессионные фракталы найдены, но точки сетапа не сформированы.")

    # else:
        # print(f"\nrun.py: Сессионные фракталы или точки сетапа не найдены.")
        
    all_points_for_plot.sort(key=lambda x: x['time'])
    
    if all_points_for_plot:
        unique_points_for_plot = []
        seen_keys = set()
        for point in all_points_for_plot:
            time_key = point['time'].replace(second=0, microsecond=0)
            price_key = round(point['price'], 5) 
            key = (time_key, point['type'], price_key)
            if key not in seen_keys:
                unique_points_for_plot.append(point)
                seen_keys.add(key)
        all_points_for_plot = unique_points_for_plot
        # print(f"\nrun.py: Всего уникальных точек для графика: {len(all_points_for_plot)}")


    # --- 3. Построение и сохранение графика ---
    # print(f"\nrun.py: Построение графика для {settings.DEFAULT_SYMBOL}...")
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    chart_filename = f"{settings.DEFAULT_SYMBOL.replace('/', '_')}_{settings.CONTEXT_TIMEFRAME}_FULL_ANALYSIS_{timestamp}.png"
    
    plot_market_structure(
        df=market_data_df, 
        structure_points=all_points_for_plot, 
        symbol=settings.DEFAULT_SYMBOL,
        timeframe=settings.CONTEXT_TIMEFRAME,
        charts_directory=charts_path,
        filename=chart_filename
    )
    
    print(f"--- Анализ для {settings.DEFAULT_SYMBOL} завершен ---") # Оставим этот высокоуровневый лог

if __name__ == "__main__":
    run_analysis()
