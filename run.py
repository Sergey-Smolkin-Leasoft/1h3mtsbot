# run.py
import os
import sys
from datetime import datetime
import pandas as pd # Для проверки market_data_df.empty

# --- Настройка путей для импорта модулей проекта ---
# Добавляем корневую директорию проекта в sys.path,
# чтобы Python мог находить модули в папках bot и configs.
# Это особенно важно, если вы запускаете run.py напрямую из корня проекта.
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.append(PROJECT_ROOT)

try:
    from configs import settings
    from bot.core.data_fetcher import get_forex_data
    from bot.strategy.context_analyzer_1h import (
        find_swing_points,
        analyze_market_structure_points,
        determine_overall_market_context # Убедитесь, что эта функция есть и импортируется
    )
    from bot.utils.plotter import plot_market_structure
except ImportError as e:
    print(f"Ошибка импорта: {e}")
    print("Убедитесь, что все файлы проекта находятся в правильных директориях,")
    print("и что в каждой поддиректории (bot, bot/core, bot/strategy, bot/utils, configs) есть файл __init__.py.")
    print(f"Текущий PROJECT_ROOT, добавленный в sys.path: {PROJECT_ROOT}")
    sys.exit(1) # Выход, если базовые импорты не работают

def run_analysis():
    """
    Основная функция для запуска анализа рыночного контекста.
    """
    print(f"--- Запуск анализа для символа: {settings.DEFAULT_SYMBOL} ---")
    print(f"API ключ используется: ...{settings.API_KEY_TWELVE_DATA[-4:] if settings.API_KEY_TWELVE_DATA else 'НЕ УСТАНОВЛЕН'}")


    # 1. Определяем директорию для сохранения графиков
    # PROJECT_ROOT уже определен выше как корневая директория проекта.
    charts_path = os.path.join(PROJECT_ROOT, settings.CHARTS_DIRECTORY_NAME)

    if not os.path.exists(charts_path):
        try:
            os.makedirs(charts_path)
            print(f"run.py: Директория для графиков создана: {charts_path}")
        except OSError as e:
            print(f"run.py: Ошибка при создании директории {charts_path}: {e}")
            # Можно решить прервать выполнение, если директория критична
            # return

    # 2. Получение данных
    print(f"\nrun.py: Получение данных для {settings.DEFAULT_SYMBOL}...")
    market_data_df = get_forex_data(
        symbol=settings.DEFAULT_SYMBOL,
        interval=settings.CONTEXT_TIMEFRAME,
        outputsize=settings.CONTEXT_OUTPUT_SIZE
        # api_key передается по умолчанию из settings в самой функции get_forex_data
    )

    if market_data_df is None or market_data_df.empty:
        print(f"run.py: Не удалось получить данные для {settings.DEFAULT_SYMBOL}. Анализ прерван.")
        return

    # 3. Поиск поворотных точек (свингов)
    print(f"\nrun.py: Поиск свингов для {settings.DEFAULT_SYMBOL}...")
    swing_highs, swing_lows = find_swing_points(market_data_df, n=settings.SWING_POINT_N)

    structure_points_for_plot = [] # Инициализируем для случая, если свингов нет

    if not swing_highs or not swing_lows:
        print(f"run.py: Не найдено достаточного количества свингов для {settings.DEFAULT_SYMBOL}.")
        # Тем не менее, можно попытаться проанализировать то, что есть, или просто нарисовать свечи
        # В данном случае, analyze_market_structure_points вернет пустой список, если свингов мало
    
    # 4. Анализ структуры рынка для получения точек HH, HL, LH, LL
    # Эта функция должна вызываться даже если свингов мало, она сама обработает этот случай.
    print(f"\nrun.py: Анализ рыночной структуры для {settings.DEFAULT_SYMBOL}...")
    structure_points_for_plot = analyze_market_structure_points(swing_highs, swing_lows)
    
    if not structure_points_for_plot: # Проверяем результат analyze_market_structure_points
        print(f"run.py: Не удалось определить значимые точки структуры рынка (HH, HL, LH, LL) для {settings.DEFAULT_SYMBOL}.")
    else:
        print(f"\nrun.py: Найденные точки структуры для {settings.DEFAULT_SYMBOL}:")
        for sp in structure_points_for_plot[-10:]: # Показываем последние 10 для краткости
            price_str = f"{sp['price']:.5f}" if isinstance(sp.get('price'), float) else str(sp.get('price'))
            print(f"  Время: {sp['time']}, Цена: {price_str}, Тип: {sp['type']}")
        
        # 5. Определение общего рыночного контекста
        # Вызываем только если есть точки структуры для анализа
        overall_context = determine_overall_market_context(structure_points_for_plot)
        print(f"\nrun.py: Общий рыночный контекст для {settings.DEFAULT_SYMBOL}: {overall_context}")

    # 6. Построение и сохранение графика
    # График строится в любом случае, даже если точек структуры нет (будут только свечи)
    print(f"\nrun.py: Построение графика для {settings.DEFAULT_SYMBOL}...")
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    chart_filename = f"{settings.DEFAULT_SYMBOL.replace('/', '_')}_{settings.CONTEXT_TIMEFRAME}_structure_{timestamp}.png"
    
    plot_market_structure(
        df=market_data_df,
        structure_points=structure_points_for_plot, # Передаем то, что получили
        symbol=settings.DEFAULT_SYMBOL,
        timeframe=settings.CONTEXT_TIMEFRAME,
        charts_directory=charts_path,
        filename=chart_filename
    )
    
    print(f"\n--- Анализ для {settings.DEFAULT_SYMBOL} завершен ---")

if __name__ == "__main__":
    # Эта проверка позволяет запускать run_analysis() только когда скрипт выполняется напрямую.
    # Например, командой: python run.py
    run_analysis()
