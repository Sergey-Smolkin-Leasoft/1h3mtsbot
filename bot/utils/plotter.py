import pandas as pd
import mplfinance as mpf
import matplotlib.pyplot as plt
from matplotlib.dates import date2num, num2date # num2date может понадобиться для отладки
from datetime import datetime
import os

# --- МОДУЛЬ ПОСТРОЕНИЯ ГРАФИКА ---
def plot_market_structure(df: pd.DataFrame, 
                          structure_points: list, 
                          symbol: str, 
                          timeframe: str, 
                          charts_directory: str, 
                          filename: str):
    """
    Рисует свечной график с отмеченными точками структуры рынка (HH, HL, LH, LL)
    и сохраняет его в указанную директорию.
    """
    print(f"\n--- plot_market_structure: Начало для {symbol} в {charts_directory}/{filename} ---")

    if df.empty:
        print("plot_market_structure: DataFrame пуст. График не будет построен.")
        return

    # Диагностика входного DataFrame
    print(f"plot_market_structure: Информация о DataFrame (df.info()):")
    df.info()
    print(f"\nplot_market_structure: Первые 3 строки DataFrame (df.head(3)):")
    print(df.head(3))
    print(f"\nplot_market_structure: Последние 3 строки DataFrame (df.tail(3)):")
    print(df.tail(3))

    if not isinstance(df.index, pd.DatetimeIndex):
        print("plot_market_structure: КРИТИЧЕСКАЯ ОШИБКА: Индекс DataFrame не является pd.DatetimeIndex!")
        # Попытка конвертации, если это возможно
        try:
            df.index = pd.to_datetime(df.index)
            print("plot_market_structure: Индекс был конвертирован в pd.DatetimeIndex.")
            if not isinstance(df.index, pd.DatetimeIndex):
                 print("plot_market_structure: Повторная проверка: Конвертация индекса не удалась. Прерывание.")
                 return
        except Exception as e:
            print(f"plot_market_structure: Ошибка при попытке конвертации индекса в DatetimeIndex: {e}. Прерывание.")
            return
            
    if not df.index.is_monotonic_increasing:
        print("plot_market_structure: Предупреждение: Индекс DataFrame не отсортирован по возрастанию. Сортировка...")
        df = df.sort_index()
        print("plot_market_structure: Индекс отсортирован.")

    print(f"plot_market_structure: Минимальное время в индексе: {df.index.min()}, Максимальное: {df.index.max()}")
    print(f"plot_market_structure: Количество уникальных временных меток в индексе: {df.index.nunique()}")


    if not os.path.exists(charts_directory):
        try:
            os.makedirs(charts_directory)
            print(f"plot_market_structure: Директория создана: {charts_directory}")
        except OSError as e:
            print(f"plot_market_structure: Ошибка при создании директории {charts_directory}: {e}")
            return

    mc = mpf.make_marketcolors(up='g', down='r', inherit=True)
    s  = mpf.make_mpf_style(marketcolors=mc, gridstyle=':', y_on_right=False)

    colors = {'HH': 'blue', 'HL': 'green', 'LH': 'red', 'LL': 'purple', 'H': 'cyan', 'L': 'magenta'}
    markers = {'HH': '^', 'HL': '^', 'LH': 'v', 'LL': 'v', 'H': 'o', 'L': 'o'}

    price_range = df['high'].max() - df['low'].min()
    if price_range == 0: 
        y_offset_factor = 0.01 
    else:
        y_offset_factor = price_range * 0.025 # Немного увеличил отступ для лучшей видимости

    fig = None 
    try:
        print("plot_market_structure: Попытка вызова mpf.plot()...")
        fig, axlist = mpf.plot(df,
                               type='candle',
                               style=s,
                               title=f'\n{symbol} - {timeframe} - Структура рынка',
                               ylabel='Цена',
                               volume='volume' in df.columns and not df['volume'].empty,
                               figratio=(16,9),
                               returnfig=True,
                               figsize=(15, 7),
                               show_nontrading=False # Может помочь с отображением оси X, если есть пропуски
                              )
        print("plot_market_structure: mpf.plot() выполнен успешно.")
    except Exception as e:
        print(f"plot_market_structure: КРИТИЧЕСКАЯ ОШИБКА при вызове mpf.plot: {e}")
        return
        
    if fig is None or not axlist:
        print("plot_market_structure: Ошибка: mpf.plot() не вернул фигуру или оси. График не будет построен.")
        return
        
    ax = axlist[0]
    
    xlims = ax.get_xlim()
    print(f"plot_market_structure: Пределы оси X после mpf.plot (числовые): {xlims}")
    # Если xlims маленькие (например, от -1 до 10 для 10 точек), mplfinance использует порядковые индексы.
    # Если xlims большие (например, 7xxxxx), mplfinance использует matplotlib date numbers.
    # Эта информация поможет понять, какую X-координату использовать для аннотаций.
    
    is_ordinal_xaxis = (xlims[1] - xlims[0]) < (len(df) + 10) # Эвристика: если диапазон оси Х сопоставим с кол-вом точек

    if is_ordinal_xaxis:
        print("plot_market_structure: Обнаружена порядковая ось X (0, 1, 2...). Аннотации будут размещаться по индексам.")
    else:
        print("plot_market_structure: Обнаружена ось X на основе дат matplotlib. Аннотации будут размещаться по date2num.")


    print(f"plot_market_structure: Добавление {len(structure_points)} точек структуры на график...")
    valid_points_plotted = 0
    for i, point in enumerate(structure_points):
        point_time = point.get('time')
        point_price = point.get('price')
        point_type = point.get('type')

        if point_time is None or point_price is None or point_type is None:
            print(f"plot_market_structure: Пропуск некорректной точки: {point}")
            continue

        point_time_for_plot = point_time 
        # Поиск ближайшего времени в индексе DataFrame, если точного совпадения нет
        if point_time not in df.index:
            try:
                nearest_time_on_chart = df.index.asof(point_time)
                if nearest_time_on_chart is pd.NaT: 
                    future_times = df.index[df.index > point_time]
                    if not future_times.empty:
                        nearest_time_on_chart = future_times[0]
                    else:
                        print(f"plot_market_structure: Предупреждение: Время точки {point_time} (тип {point_type}) вне диапазона данных DataFrame. Пропуск.")
                        continue
                point_time_for_plot = nearest_time_on_chart
            except Exception as e_asof:
                 print(f"plot_market_structure: Ошибка при поиске asof для {point_time} (тип {point_type}): {e_asof}. Пропуск.")
                 continue
        
        # Определяем X-координату для точки
        try:
            if is_ordinal_xaxis:
                # Используем порядковый индекс строки в DataFrame
                loc = df.index.get_loc(point_time_for_plot)
                time_num = float(loc)
            else:
                # Используем стандартное числовое представление даты matplotlib
                time_num = date2num(point_time_for_plot)
            
            # print(f"    Координата X для точки {point_type} ({point_time_for_plot}): {time_num}")

            ax.scatter(time_num, point_price, 
                       color=colors.get(point_type, 'black'), 
                       marker=markers.get(point_type, 'x'), 
                       s=120, zorder=5) # Немного увеличил маркер

            y_text_offset = y_offset_factor
            if point_type in ['LH', 'LL']:
                 y_text_offset = -y_offset_factor * 1.5 
            elif point_type in ['HH', 'HL']:
                 y_text_offset = y_offset_factor * 1.5 
            
            ax.text(time_num, point_price + y_text_offset, point_type, 
                    color=colors.get(point_type, 'black'),
                    fontsize=10, ha='center', 
                    va='top' if y_text_offset < 0 else 'bottom',
                    bbox=dict(boxstyle='round,pad=0.3', fc='yellow', alpha=0.4)) # Увеличил pad и alpha
            valid_points_plotted +=1
        except KeyError:
             print(f"plot_market_structure: Ключ времени {point_time_for_plot} не найден в индексе df при попытке получить get_loc. Пропуск точки {point_type}.")
        except Exception as e:
            print(f"plot_market_structure: Ошибка при нанесении точки {point_type} ({point_time_for_plot}) на график: {e}")
    
    print(f"plot_market_structure: Успешно нанесено {valid_points_plotted} точек.")

    # ax.xaxis_date() # mplfinance обычно сам это делает, если ось не порядковая
    if not is_ordinal_xaxis: # Если ось не порядковая, то форматируем даты
        fig.autofmt_xdate(rotation=30)
    else: # Если ось порядковая, то метки оси Х будут 0, 1, 2... Их можно заменить на даты, если нужно
        # Это более сложная задача, если mplfinance уже выбрал порядковую ось.
        # Пока оставим как есть, чтобы график хотя бы отображался корректно.
        # Можно попробовать установить свои тики:
        step = max(1, len(df) // 5) # Показывать примерно 5 меток
        tick_indices = range(0, len(df), step)
        ax.set_xticks(tick_indices)
        ax.set_xticklabels([df.index[i].strftime('%H:%M') for i in tick_indices], rotation=30, ha='right')


    filepath = os.path.join(charts_directory, filename)
    try:
        fig.savefig(filepath, bbox_inches='tight') 
        print(f"plot_market_structure: График УСПЕШНО сохранен в: {filepath}")
    except Exception as e:
        print(f"plot_market_structure: КРИТИЧЕСКАЯ ОШИБКА при сохранении графика в {filepath}: {e}")
    
    print(f"--- plot_market_structure: Завершение для {symbol} ---")

