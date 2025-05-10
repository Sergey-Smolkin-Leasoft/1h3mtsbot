# utils/plotter.py
import pandas as pd
import mplfinance as mpf
import matplotlib.pyplot as plt
from matplotlib.dates import date2num # num2date может понадобиться для отладки
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
    Рисует свечной график с отмеченными точками структуры рынка, сессионными фракталами
    и точками сетапов. Сохраняет его в указанную директорию.
    """
    print(f"\n--- plot_market_structure: Начало для {symbol} в {charts_directory}/{filename} ---")

    if df.empty:
        print("plot_market_structure: DataFrame пуст. График не будет построен.")
        return

    # Диагностика входного DataFrame
    # print(f"plot_market_structure: Информация о DataFrame (df.info()):")
    # df.info()
    # print(f"\nplot_market_structure: Первые 3 строки DataFrame (df.head(3)):")
    # print(df.head(3))
    
    if not isinstance(df.index, pd.DatetimeIndex):
        print("plot_market_structure: КРИТИЧЕСКАЯ ОШИБКА: Индекс DataFrame не является pd.DatetimeIndex!")
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

    if not os.path.exists(charts_directory):
        try:
            os.makedirs(charts_directory)
            print(f"plot_market_structure: Директория создана: {charts_directory}")
        except OSError as e:
            print(f"plot_market_structure: Ошибка при создании директории {charts_directory}: {e}")
            return

    # Расширенные цвета и маркеры для новых типов точек
    # F_H_AS: Fractal High Asian Session
    # F_L_AS: Fractal Low Asian Session
    # F_H_NY1: Fractal High New York Session (Day -1)
    # F_L_NY1: Fractal Low New York Session (Day -1)
    # SETUP_Resist: Setup point for resistance
    # SETUP_Support: Setup point for support
    
    colors = {
        'HH': 'blue', 'HL': 'green', 'LH': 'red', 'LL': 'purple', 
        'H': 'cyan', 'L': 'magenta',
        'F_H_AS': 'darkorange', 'F_L_AS': 'darkorange',
        'F_H_NY1': 'dodgerblue', 'F_L_NY1': 'dodgerblue', 
        'F_H_NY2': 'deepskyblue', 'F_L_NY2': 'deepskyblue', # Если будете смотреть дальше NY-2
        'SETUP_Resist': 'black', 'SETUP_Support': 'black',
        'UNKNOWN_SETUP': 'grey' 
    }
    markers = {
        'HH': '^', 'HL': '^', 'LH': 'v', 'LL': 'v', 
        'H': 'o', 'L': 'o',
        'F_H_AS': 'x', 'F_L_AS': 'x',             # Азиатские фракталы - крестик
        'F_H_NY1': '+', 'F_L_NY1': '+',           # НЙ фракталы прошлого - плюсик
        'F_H_NY2': 'P', 'F_L_NY2': 'P',
        'SETUP_Resist': 'D', 'SETUP_Support': 'D', # Сетапы - ромб (Diamond)
        'UNKNOWN_SETUP': '.'
    }
    # Размеры маркеров можно тоже кастомизировать
    marker_sizes = {
        'HH': 120, 'HL': 120, 'LH': 120, 'LL': 120,
        'H': 100, 'L': 100,
        'F_H_AS': 90, 'F_L_AS': 90,
        'F_H_NY1': 90, 'F_L_NY1': 90,
        'F_H_NY2': 90, 'F_L_NY2': 90,
        'SETUP_Resist': 150, 'SETUP_Support': 150, # Делаем сетапы заметнее
        'UNKNOWN_SETUP': 70
    }
    # Смещения для текста аннотаций
    text_y_offsets_factors = { # Множители для y_offset_factor
        'HH': 1.5, 'HL': 1.5, 'LH': -1.5, 'LL': -1.5,
        'H': 1.2, 'L': -1.2,
        'F_H_AS': 1.0, 'F_L_AS': -1.0,
        'F_H_NY1': 1.0, 'F_L_NY1': -1.0,
        'F_H_NY2': 1.0, 'F_L_NY2': -1.0,
        'SETUP_Resist': 2.0, 'SETUP_Support': -2.0, # Дальше от цены, чтобы не перекрывать
        'UNKNOWN_SETUP': 1.0
    }


    mc = mpf.make_marketcolors(up='g', down='r', inherit=True)
    s  = mpf.make_mpf_style(marketcolors=mc, gridstyle=':', y_on_right=False)

    price_range = df['high'].max() - df['low'].min()
    if price_range == 0: 
        y_offset_factor = 0.01 * df['close'].mean() if not df['close'].empty else 0.01
    else:
        y_offset_factor = price_range * 0.020 # Уменьшил немного базовый отступ

    fig = None 
    try:
        print("plot_market_structure: Попытка вызова mpf.plot()...")
        fig, axlist = mpf.plot(df,
                               type='candle',
                               style=s,
                               title=f'\n{symbol} - {timeframe} - Анализ структуры и сессионных фракталов',
                               ylabel='Цена',
                               volume='volume' in df.columns and not df['volume'].empty,
                               figratio=(18,10), # Увеличил немного для лучшей читаемости
                               returnfig=True,
                               figsize=(16, 8), # Размер фигуры
                               show_nontrading=False 
                              )
        print("plot_market_structure: mpf.plot() выполнен успешно.")
    except Exception as e:
        print(f"plot_market_structure: КРИТИЧЕСКАЯ ОШИБКА при вызове mpf.plot: {e}")
        # Попытка нарисовать без объема, если проблема в нем
        if 'volume' in str(e).lower():
            try:
                print("plot_market_structure: Повторная попытка mpf.plot() без объема...")
                fig, axlist = mpf.plot(df, type='candle', style=s, title=f'\n{symbol} - {timeframe} - Анализ (без объема)',
                                       ylabel='Цена', volume=False, figratio=(18,10), returnfig=True, figsize=(16,8), show_nontrading=False)
                print("plot_market_structure: mpf.plot() без объема выполнен успешно.")
            except Exception as e2:
                print(f"plot_market_structure: Вторая попытка mpf.plot() также не удалась: {e2}")
                return
        else:
            return # Если ошибка не связана с объемом, выходим
        
    if fig is None or not axlist:
        print("plot_market_structure: Ошибка: mpf.plot() не вернул фигуру или оси. График не будет построен.")
        return
        
    ax = axlist[0] # Основная панель цен
    
    xlims = ax.get_xlim()
    is_ordinal_xaxis = (xlims[1] - xlims[0]) < (len(df) + 50) # Эвристика, может потребовать подстройки

    if is_ordinal_xaxis:
        print("plot_market_structure: Обнаружена порядковая ось X. Аннотации по индексам.")
    else:
        print("plot_market_structure: Обнаружена ось X на основе дат matplotlib. Аннотации по date2num.")

    print(f"plot_market_structure: Добавление {len(structure_points)} точек на график...")
    valid_points_plotted = 0
    for i, point in enumerate(structure_points):
        point_time = point.get('time')
        point_price = point.get('price')
        point_type = point.get('type') # Например, 'HH', 'F_H_AS', 'SETUP_Resist'
        point_session_info = point.get('session', '') # Дополнительная инфо о сессии

        if point_time is None or point_price is None or point_type is None:
            print(f"plot_market_structure: Пропуск некорректной точки: {point}")
            continue

        # Поиск ближайшего времени в индексе DataFrame
        point_time_for_plot = point_time
        if point_time not in df.index:
            nearest_time_on_chart = df.index.asof(point_time)
            if pd.isna(nearest_time_on_chart): # pd.NaT is deprecated, use pd.isna
                future_times = df.index[df.index > point_time]
                if not future_times.empty:
                    nearest_time_on_chart = future_times[0]
                else: # Если и будущих нет, пробуем найти ближайшую из прошлых (если точка очень старая)
                    past_times = df.index[df.index < point_time]
                    if not past_times.empty:
                        nearest_time_on_chart = past_times[-1]
                    else:
                        print(f"plot_market_structure: Предупреждение: Время точки {point_time} (тип {point_type}) вне диапазона данных DataFrame. Пропуск.")
                        continue
            point_time_for_plot = nearest_time_on_chart
        
        try:
            if is_ordinal_xaxis:
                loc = df.index.get_loc(point_time_for_plot)
                time_num = float(loc)
            else:
                # Убедимся, что point_time_for_plot это datetime объект, а не Timestamp с tz для date2num
                # date2num ожидает datetime.datetime без таймзоны, либо нужно обрабатывать tz отдельно
                # mplfinance обычно сам разбирается с таймзонами, если они консистентны в df.index
                if isinstance(point_time_for_plot, pd.Timestamp):
                     dt_to_convert = point_time_for_plot.to_pydatetime()
                     # Если есть таймзона, date2num может работать некорректно или требовать ее удаления
                     # Однако, mplfinance версии >0.12.8 обрабатывают таймзоны лучше.
                     # Попробуем передать как есть, если df.index имеет таймзону.
                     if df.index.tzinfo is not None and dt_to_convert.tzinfo is None:
                         dt_to_convert = dt_to_convert.replace(tzinfo=df.index.tzinfo) # Присваиваем таймзону данных
                     elif df.index.tzinfo is None and dt_to_convert.tzinfo is not None:
                         dt_to_convert = dt_to_convert.replace(tzinfo=None) # Удаляем, если данные без tz

                else: # если это уже datetime.datetime
                    dt_to_convert = point_time_for_plot

                time_num = date2num(dt_to_convert) 
            
            current_marker_color = colors.get(point_type, 'grey')
            current_marker_shape = markers.get(point_type, '.')
            current_marker_size = marker_sizes.get(point_type, 50)

            ax.scatter(time_num, point_price, 
                       color=current_marker_color, 
                       marker=current_marker_shape, 
                       s=current_marker_size, zorder=5)

            # Текстовая аннотация - выводим тип точки
            text_label = point_type
            # Для сетапов можно добавить больше деталей из point['details'] если есть
            if 'SETUP' in point_type and 'details' in point:
                # text_label += f"\n({point['details'][:30]}...)" # Сокращаем детали для графика
                pass # Пока оставим только тип, чтобы не перегружать

            y_text_offset_multiplier = text_y_offsets_factors.get(point_type, 1.0 if 'H' in point_type or 'Resist' in point_type else -1.0)
            final_y_text_offset = y_offset_factor * y_text_offset_multiplier
            
            # Убедимся, что текст не выходит за пределы графика по Y
            plot_min_y, plot_max_y = ax.get_ylim()
            text_y_pos = point_price + final_y_text_offset
            if text_y_pos > plot_max_y: text_y_pos = plot_max_y - y_offset_factor * 0.5
            if text_y_pos < plot_min_y: text_y_pos = plot_min_y + y_offset_factor * 0.5


            ax.text(time_num, text_y_pos, text_label, 
                    color=current_marker_color,
                    fontsize=8, # Уменьшил шрифт для компактности
                    fontweight='bold' if 'SETUP' in point_type else 'normal',
                    ha='center', 
                    va='bottom' if final_y_text_offset >= 0 else 'top', # va зависит от направления смещения
                    bbox=dict(boxstyle='round,pad=0.2', fc='yellow', alpha=0.3 if 'SETUP' not in point_type else 0.5))
            valid_points_plotted +=1
        except KeyError:
             print(f"plot_market_structure: Ключ времени {point_time_for_plot} (исходный {point_time}) не найден в индексе df при get_loc. Пропуск точки {point_type}.")
        except Exception as e:
            print(f"plot_market_structure: Ошибка при нанесении точки {point_type} ({point_time_for_plot}, исходный {point_time}) на график: {e}")
    
    print(f"plot_market_structure: Успешно нанесено {valid_points_plotted} точек.")

    if not is_ordinal_xaxis:
        try:
            fig.autofmt_xdate(rotation=30)
        except Exception as e_fmt:
            print(f"plot_market_structure: Ошибка при autofmt_xdate: {e_fmt}")
    else: 
        step = max(1, len(df) // 10) # Показывать примерно 10 меток
        tick_indices = range(0, len(df), step)
        ax.set_xticks(tick_indices)
        try:
            ax.set_xticklabels([df.index[i].strftime('%m-%d %H:%M') for i in tick_indices], rotation=30, ha='right', fontsize=8)
        except IndexError:
             print(f"plot_market_structure: Ошибка IndexError при установке xticklabels. Возможно, len(df)={len(df)}, tick_indices={list(tick_indices)}")
        except Exception as e_xtick:
            print(f"plot_market_structure: Ошибка при установке xticklabels для порядковой оси: {e_xtick}")


    filepath = os.path.join(charts_directory, filename)
    try:
        fig.savefig(filepath, bbox_inches='tight', dpi=150) # Увеличил dpi для лучшего качества
        print(f"plot_market_structure: График УСПЕШНО сохранен в: {filepath}")
    except Exception as e:
        print(f"plot_market_structure: КРИТИЧЕСКАЯ ОШИБКА при сохранении графика в {filepath}: {e}")
    
    plt.close(fig) # Закрываем фигуру, чтобы освободить память
    print(f"--- plot_market_structure: Завершение для {symbol} ---")

