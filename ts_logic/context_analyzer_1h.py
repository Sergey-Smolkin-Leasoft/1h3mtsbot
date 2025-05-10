# ts_logic/context_analyzer_1h.py
import pandas as pd
from configs import settings # Для доступа к SWING_POINT_N
from datetime import time, timedelta # Импортируем для анализа сессий

# Соответствие стилей линий числовым значениям Lightweight Charts
LINE_STYLE_SOLID = 0
LINE_STYLE_DOTTED = 1
LINE_STYLE_DASHED = 2
LINE_STYLE_LARGE_DASHED = 3

def find_swing_points(df: pd.DataFrame, n: int = settings.SWING_POINT_N):
    """
    Находит поворотные максимумы (Swing Highs) и минимумы (Swing Lows) на DataFrame.
    n - количество свечей с каждой стороны для определения свинга.

    Args:
        df (pd.DataFrame): DataFrame с данными OHLC (индекс должен быть DatetimeIndex).
        n (int): Количество свечей с каждой стороны для определения свинга.

    Returns:
        tuple: (list_of_swing_highs, list_of_swing_lows)
               Каждый элемент списка - словарь {'time': datetime, 'price': float}
    """
    swing_highs = []
    swing_lows = []

    if not isinstance(df, pd.DataFrame) or df.empty:
        return swing_highs, swing_lows

    # Убедимся, что данных достаточно для определения свингов
    if len(df) < (2 * n + 1):
        # print(f"find_swing_points: Недостаточно данных для определения свингов (требуется минимум {2*n + 1}, получено {len(df)}).")
        return swing_highs, swing_lows

    required_cols = ['high', 'low']
    if not all(col in df.columns for col in required_cols):
        print(f"context_analyzer: DataFrame должен содержать колонки {required_cols}.")
        return swing_highs, swing_lows

    high_prices = df['high'].values
    low_prices = df['low'].values
    datetimes = df.index

    for i in range(n, len(df) - n):
        is_swing_high = True
        current_high = high_prices[i]
        # Проверяем, является ли текущий максимум самым высоким в окне 2*n + 1
        for j in range(1, n + 1):
            if current_high <= high_prices[i-j] or current_high <= high_prices[i+j]:
                is_swing_high = False
                break
        if is_swing_high:
            swing_highs.append({'time': datetimes[i], 'price': current_high})

        is_swing_low = True
        current_low = low_prices[i]
        # Проверяем, является ли текущий минимум самым низким в окне 2*n + 1
        for j in range(1, n + 1):
            if current_low >= low_prices[i-j] or current_low >= low_prices[i+j]:
                is_swing_low = False
                break
        if is_swing_low:
            swing_lows.append({'time': datetimes[i], 'price': current_low})

    # print(f"find_swing_points: Найдено Swing Highs: {len(swing_highs)}, Swing Lows: {len(swing_lows)}")
    return swing_highs, swing_lows

def analyze_market_structure_points(swing_highs: list, swing_lows: list):
    """
    Анализирует последовательность свингов для определения HH, HL, LH, LL.
    """
    structure_points = []
    if not swing_highs and not swing_lows:
        # print("analyze_market_structure_points: Нет свингов для анализа.")
        return structure_points

    all_swings = []
    for sh in swing_highs:
        all_swings.append({'time': sh['time'], 'price': sh['price'], 'swing_type': 'high'})
    for sl in swing_lows:
        all_swings.append({'time': sl['time'], 'price': sl['price'], 'swing_type': 'low'})

    if not all_swings:
        # print("analyze_market_structure_points: Список всех свингов пуст.")
        return structure_points

    all_swings.sort(key=lambda x: x['time'])

    last_h = None
    last_l = None
    temp_structure_points = [] # Временный список для определения последовательности

    for swing in all_swings:
        current_time = swing['time']
        current_price = swing['price']
        current_swing_type = swing['swing_type']
        point_type_determined = None

        if current_swing_type == 'high':
            if last_h:
                if current_price > last_h['price']:
                    point_type_determined = "HH"
                elif current_price < last_h['price']:
                    point_type_determined = "LH"
                else:
                    point_type_determined = "H" # Равные максимумы
            else:
                point_type_determined = "H" # Первый максимум
            last_h = {'time': current_time, 'price': current_price}

        elif current_swing_type == 'low':
            if last_l:
                if current_price < last_l['price']:
                    point_type_determined = "LL"
                elif current_price > last_l['price']:
                    point_type_determined = "HL"
                else:
                    point_type_determined = "L" # Равные минимумы
            else:
                point_type_determined = "L" # Первый минимум
            last_l = {'time': current_time, 'price': current_price}

        if point_type_determined:
            temp_structure_points.append({
                'time': current_time,
                'price': current_price,
                'type': point_type_determined
            })

    # Фильтрация последовательности: удаляем точки одного типа подряд (кроме H/L, если цена не меняется)
    if not temp_structure_points:
        return []

    final_structure_points = [temp_structure_points[0]]
    for i in range(1, len(temp_structure_points)):
        current_sp = temp_structure_points[i]
        prev_sp = final_structure_points[-1]

        # Пропускаем, если текущая точка того же типа (HH, HL, LH, LL) и время совпадает (редко, но возможно)
        if current_sp['type'] in ['HH', 'HL', 'LH', 'LL'] and current_sp['type'] == prev_sp['type'] and current_sp['time'] == prev_sp['time']:
             continue

        # Пропускаем, если текущая точка H/L того же типа, что и предыдущая H/L, и цена не изменилась
        is_same_basic_type_hl = current_sp['type'] in ['H', 'L'] and prev_sp['type'] in ['H', 'L'] and current_sp['type'] == prev_sp['type']
        is_same_price = abs(current_sp['price'] - prev_sp['price']) < 1e-9 # Использовать небольшую дельту для сравнения float

        if is_same_basic_type_hl and is_same_price:
             continue

        # Если текущая точка является более специфичным типом (HH, LH, LL, HL)
        # и совпадает по времени с предыдущей точкой (H или L), заменяем предыдущую
        if prev_sp['type'] == 'H' and current_sp['type'] in ['HH', 'LH'] and current_sp['time'] == prev_sp['time']:
            final_structure_points[-1] = current_sp
            continue
        if prev_sp['type'] == 'L' and current_sp['type'] in ['LL', 'HL'] and current_sp['time'] == prev_sp['time']:
            final_structure_points[-1] = current_sp
            continue

        # Добавляем точку, если она не дублирует предыдущую по типу/времени/цене
        final_structure_points.append(current_sp)

    # print(f"analyze_market_structure_points: Определено {len(final_structure_points)} уникальных точек структуры.")
    return final_structure_points


def determine_overall_market_context(structure_points: list):
    """
    Определяет общий рыночный контекст (LONG, SHORT, NEUTRAL)
    на основе последних нескольких точек структуры, с учетом BOS для подтверждения тренда.
    """
    if not structure_points:
        return "NEUTRAL/RANGING (нет данных о структуре)"

    # Используем только трендовые точки для определения основного контекста
    trend_defining_points = [p for p in structure_points if p['type'] in ['HH', 'HL', 'LH', 'LL']]

    if len(trend_defining_points) < 2: # Нужно хотя бы две точки для определения направления
         if len(trend_defining_points) == 1:
             last_tdp_single = trend_defining_points[0]
             if last_tdp_single['type'] == 'HH':
                 return "NEUTRAL (Первый BOS вверх, ожидание HL)"
             elif last_tdp_single['type'] == 'LL':
                 return "NEUTRAL (Первый BOS вниз, ожидание LH)"
             # H/L сами по себе не определяют тренд без предыдущей точки
             return "NEUTRAL/RANGING (недостаточно трендовых точек)"
         return "NEUTRAL/RANGING (недостаточно трендовых точек)"


    # Анализируем последние две трендовые точки
    last_p = trend_defining_points[-1]
    second_last_p = trend_defining_points[-2]

    context = "NEUTRAL/RANGING (неопределенная структура)" # Значение по умолчанию

    # Проверка на восходящий тренд (HL -> HH) или BOS вверх (LL/LH -> HH)
    if last_p['type'] == 'HH':
        if second_last_p['type'] == 'HL':
            context = "LONG (Тренд вверх: HH после HL)"
        elif second_last_p['type'] in ['LL', 'LH']:
             # Проверяем, пробил ли HH предыдущий LH
             prior_lhs = [p for p in trend_defining_points[:-1] if p['type'] == 'LH']
             if prior_lhs and last_p['price'] > prior_lhs[-1]['price']:
                  context = "LONG (BOS: HH пробил предыдущий LH)"
             else:
                  context = "NEUTRAL (HH не пробил ключевой LH, ожидание HL/дальнейшего BOS)"
        else:
             context = "NEUTRAL (HH сформирован, но последовательность неясна)"

    # Проверка на коррекцию в восходящем тренде (HH -> HL)
    elif last_p['type'] == 'HL':
        if second_last_p['type'] == 'HH':
            context = "LONG (Тренд вверх: коррекция HL после HH)"
        else:
            context = "NEUTRAL/RANGING (Формируется HL без предшествующего HH для подтверждения тренда)"

    # Проверка на нисходящий тренд (LH -> LL) или BOS вниз (HH/HL -> LL)
    elif last_p['type'] == 'LL':
        if second_last_p['type'] == 'LH':
            context = "SHORT (Тренд вниз: LL после LH)"
        elif second_last_p['type'] in ['HH', 'HL']:
             # Проверяем, пробил ли LL предыдущий HL
             prior_hls = [p for p in trend_defining_points[:-1] if p['type'] == 'HL']
             if prior_hls and last_p['price'] < prior_hls[-1]['price']:
                    context = "SHORT (BOS: LL пробил предыдущий HL)"
             else:
                    context = "NEUTRAL (LL не пробил ключевой HL, ожидание LH/дальнейшего BOS)"
        else:
             context = "NEUTRAL (LL сформирован, но последовательность неясна)"

    # Проверка на коррекцию в нисходящем тренде (LL -> LH)
    elif last_p['type'] == 'LH':
        if second_last_p['type'] == 'LL':
            context = "SHORT (Тренд вниз: коррекция LH после LL)"
        else:
            context = "NEUTRAL/RANGING (Формируется LH без предшествующего LL для подтверждения тренда)"

    # Дополнительная проверка на явные признаки консолидации, если контекст все еще не ясен
    if "NEUTRAL" in context or "RANGING" in context:
         if len(trend_defining_points) >= 2 :
            p1 = trend_defining_points[-1]
            p0 = trend_defining_points[-2]
            # Проверяем на сужение диапазона (HL после LH или LH после HL)
            if (p1['type'] == 'LH' and p0['type'] == 'HL') or \
               (p1['type'] == 'HL' and p0['type'] == 'LH'):
                context = "NEUTRAL/RANGING (Сужение/консолидация)"
            # Проверяем на расширение диапазона (HH после LL или LL после HH)
            elif (p1['type'] == 'HH' and p0['type'] == 'LL') or \
                 (p1['type'] == 'LL' and p0['type'] == 'HH'):
                 context = "NEUTRAL/RANGING (Расширение диапазона)"

    return context

def determine_trend_lines(structure_points: list, context: str):
    """
    Определяет координаты линий тренда на основе точек структуры и контекста.

    Args:
        structure_points (list): Список точек структуры (HH, HL, LH, LL, H, L).
        context (str): Определенный рыночный контекст (LONG, SHORT, NEUTRAL/RANGING).

    Returns:
        list: Список словарей, описывающих линии тренда.
              Каждый словарь: {'start_time': datetime, 'start_price': float,
                               'end_time': datetime, 'end_price': float,
                               'color': str, 'lineStyle': int}
    """
    trend_lines = []
    # Используем только трендовые точки для построения линий
    trend_defining_points = [p for p in structure_points if p['type'] in ['HH', 'HL', 'LH', 'LL']]

    if len(trend_defining_points) < 2:
        return trend_lines # Недостаточно точек для построения линии

    # Определяем, какие точки использовать в зависимости от контекста
    if "LONG" in context:
        # В восходящем тренде соединяем последние HL
        hl_points = [p for p in trend_defining_points if p['type'] == 'HL']
        if len(hl_points) >= 2:
            # Соединяем последние два или три HL для линии поддержки
            points_to_connect = hl_points[-2:] # Последние 2 HL
            # Можно соединить и больше, если нужно
            # points_to_connect = hl_points[-3:] if len(hl_points) >= 3 else hl_points[-2:]

            # Сортируем на всякий случай по времени
            points_to_connect.sort(key=lambda x: x['time'])

            # Создаем линию, соединяющую первую и последнюю точку в selected_points
            if len(points_to_connect) >= 2:
                 trend_lines.append({
                    'start_time': points_to_connect[0]['time'],
                    'start_price': points_to_connect[0]['price'],
                    'end_time': points_to_connect[-1]['time'],
                    'end_price': points_to_connect[-1]['price'],
                    'color': '#26A69A', # Зеленая линия для восходящего тренда/поддержки
                    'lineStyle': LINE_STYLE_SOLID
                 })

        # Опционально: можно добавить линию сопротивления, соединяющую HH
        hh_points = [p for p in trend_defining_points if p['type'] == 'HH']
        if len(hh_points) >= 2:
             points_to_connect_hh = hh_points[-2:]
             points_to_connect_hh.sort(key=lambda x: x['time'])
             if len(points_to_connect_hh) >= 2:
                  trend_lines.append({
                     'start_time': points_to_connect_hh[0]['time'],
                     'start_price': points_to_connect_hh[0]['price'],
                     'end_time': points_to_connect_hh[-1]['time'],
                     'end_price': points_to_connect_hh[-1]['price'],
                     'color': '#2962FF', # Синяя линия для восходящего тренда/сопротивления
                     'lineStyle': LINE_STYLE_SOLID
                  })


    elif "SHORT" in context:
        # В нисходящем тренде соединяем последние LH
        lh_points = [p for p in trend_defining_points if p['type'] == 'LH']
        if len(lh_points) >= 2:
            # Соединяем последние два или три LH для линии сопротивления
            points_to_connect = lh_points[-2:] # Последние 2 LH
            # points_to_connect = lh_points[-3:] if len(lh_points) >= 3 else lh_points[-2:]

            points_to_connect.sort(key=lambda x: x['time'])

            if len(points_to_connect) >= 2:
                 trend_lines.append({
                    'start_time': points_to_connect[0]['time'],
                    'start_price': points_to_connect[0]['price'],
                    'end_time': points_to_connect[-1]['time'],
                    'end_price': points_to_connect[-1]['price'],
                    'color': '#EF5350', # Красная линия для нисходящего тренда/сопротивления
                    'lineStyle': LINE_STYLE_SOLID
                 })

        # Опционально: можно добавить линию поддержки, соединяющую LL
        ll_points = [p for p in trend_defining_points if p['type'] == 'LL']
        if len(ll_points) >= 2:
             points_to_connect_ll = ll_points[-2:]
             points_to_connect_ll.sort(key=lambda x: x['time'])
             if len(points_to_connect_ll) >= 2:
                  trend_lines.append({
                     'start_time': points_to_connect_ll[0]['time'],
                     'start_price': points_to_connect_ll[0]['price'],
                     'end_time': points_to_connect_ll[-1]['time'],
                     'end_price': points_to_connect_ll[-1]['price'],
                     'color': '#26A69A', # Зеленая линия для нисходящего тренда/поддержки
                     'lineStyle': LINE_STYLE_SOLID
                  })


    # Для NEUTRAL/RANGING контекста можно добавить горизонтальные линии
    # например, по последним HH/LL или H/L для обозначения диапазона
    elif "NEUTRAL" in context or "RANGING" in context:
        last_hh = next((p for p in reversed(trend_defining_points) if p['type'] == 'HH'), None)
        last_ll = next((p for p in reversed(trend_defining_points) if p['type'] == 'LL'), None)
        last_h = next((p for p in reversed(structure_points) if p['type'] in ['H', 'HH']), None) # Используем все точки для H/L диапазона
        last_l = next((p for p in reversed(structure_points) if p['type'] in ['L', 'LL']), None)

        # Можно нарисовать горизонтальные линии по последним значимым уровням
        if last_hh and last_ll:
             # Линия сопротивления по последнему HH
             trend_lines.append({
                'start_time': trend_defining_points[0]['time'], # Начинаем от первой трендовой точки
                'start_price': last_hh['price'],
                'end_time': trend_defining_points[-1]['time'], # Заканчиваем у последней трендовой точки
                'end_price': last_hh['price'],
                'color': '#808080', # Серый цвет для диапазона
                'lineStyle': LINE_STYLE_DOTTED # Пунктирная линия
             })
             # Линия поддержки по последнему LL
             trend_lines.append({
                'start_time': trend_defining_points[0]['time'],
                'start_price': last_ll['price'],
                'end_time': trend_defining_points[-1]['time'],
                'end_price': last_ll['price'],
                'color': '#808080',
                'lineStyle': LINE_STYLE_DOTTED
             })
        elif last_h and last_l: # Если нет HH/LL, используем H/L
              trend_lines.append({
                'start_time': structure_points[0]['time'], # Начинаем от первой точки структуры
                'start_price': last_h['price'],
                'end_time': structure_points[-1]['time'], # Заканчиваем у последней точки структуры
                'end_price': last_h['price'],
                'color': '#A9A9A9', # Темно-серый
                'lineStyle': LINE_STYLE_DOTTED
             })
              trend_lines.append({
                'start_time': structure_points[0]['time'],
                'start_price': last_l['price'],
                'end_time': structure_points[-1]['time'],
                'end_price': last_l['price'],
                'color': '#A9A9A9',
                'lineStyle': LINE_STYLE_DOTTED
             })


    # print(f"determine_trend_lines: Определено {len(trend_lines)} линий тренда.")
    return trend_lines

# --- НОВАЯ ФУНКЦИЯ: СБОР СВОДКИ АНАЛИЗА ---
def summarize_analysis(market_data_df: pd.DataFrame, structure_points: list, session_fractal_and_setup_points: list, overall_context: str):
    """
    Собирает сводку ключевой информации анализа для отображения на фронтенде.

    Args:
        market_data_df (pd.DataFrame): DataFrame с данными OHLC.
        structure_points (list): Список точек структуры.
        session_fractal_and_setup_points (list): Список сессионных фракталов и сетапов.
        overall_context (str): Общий рыночный контекст.

    Returns:
        dict: Словарь с разделами "general" и "detailed", содержащими списки пунктов анализа.
              Каждый пункт: {'description': str, 'status': bool}
    """
    analysis_summary = {
        "general": [],
        "detailed": []
    }

    # --- Общая информация ---
    analysis_summary["general"].append({
        'description': f"Общий контекст: {overall_context}",
        'status': True # Контекст всегда определен (даже как нейтральный)
    })

    # Пример: Наличие точек входа (сетапов)
    setup_points = [p for p in session_fractal_and_setup_points if 'SETUP' in p.get('type', '')]
    analysis_summary["general"].append({
        'description': f"Найдено сетапов: {len(setup_points)}",
        'status': len(setup_points) > 0
    })

    # Пример: Цели (здесь нужна ваша логика определения целей)
    # Пока заглушка
    has_targets = False # Ваша логика определения целей
    analysis_summary["general"].append({
        'description': "Цели определены",
        'status': has_targets
    })

    # Пример: Точка инвалидации (здесь нужна ваша логика определения точки инвалидации)
    # Пока заглушка
    has_invalidation = False # Ваша логика определения точки инвалидации
    analysis_summary["general"].append({
        'description': "Точка инвалидации определена",
        'status': has_invalidation
    })


    # --- Подробная информация ---

    # Пример: Снятие PDH/PDL (нужна более точная логика, пока заглушка)
    # Для этого нужен доступ к данным предыдущего дня
    pdh_swept = False # Ваша логика проверки снятия PDH
    pdl_swept = False # Ваша логика проверки снятия PDL

    analysis_summary["detailed"].append({
        'description': f"Снятие PDH: {'Да' if pdh_swept else 'Нет'}",
        'status': pdh_swept
    })
    analysis_summary["detailed"].append({
        'description': f"Снятие PDL: {'Да' if pdl_swept else 'Нет'}",
        'status': pdl_swept
    })

    # Пример: Направление Азии и синхронизация (нужна логика)
    # Для этого нужен доступ к данным азиатской сессии и текущему движению
    asian_direction = "Не определено" # Ваша логика определения направления Азии
    is_synchronized = False # Ваша логика проверки синхронизации

    analysis_summary["detailed"].append({
        'description': f"Направление Азии: {asian_direction}",
        'status': asian_direction != "Не определено" # Считаем успешным, если направление определено
    })
    analysis_summary["detailed"].append({
        'description': f"Синхронизация с Азией: {'Да' if is_synchronized else 'Нет'}",
        'status': is_synchronized
    })

    # Добавьте сюда другие пункты подробного анализа по вашей торговой системе

    return analysis_summary


# Пример использования (для тестирования этого модуля)
if __name__ == '__main__':
    print("Тестирование context_analyzer_1h.py (логика линий тренда и сводки)...")

    # Пример данных структуры (восходящий тренд)
    structure_up = [
        {'time': pd.Timestamp('2023-01-01 10:00', tz='UTC'), 'price': 100, 'type': 'L'},
        {'time': pd.Timestamp('2023-01-01 11:00', tz='UTC'), 'price': 110, 'type': 'H'},
        {'time': pd.Timestamp('2023-01-01 12:00', tz='UTC'), 'price': 105, 'type': 'HL'},
        {'time': pd.Timestamp('2023-01-01 13:00', tz='UTC'), 'price': 115, 'type': 'HH'},
        {'time': pd.Timestamp('2023-01-01 14:00', tz='UTC'), 'price': 112, 'type': 'HL'},
        {'time': pd.Timestamp('2023-01-01 15:00', tz='UTC'), 'price': 120, 'type': 'HH'}
    ]
    context_up = determine_overall_market_context(structure_up)
    print(f"\nПример 1: Восходящий тренд. Контекст: {context_up}")
    trend_lines_up = determine_trend_lines(structure_up, context_up)
    print("Определенные линии тренда:")
    for line in trend_lines_up:
        print(f"  Start: {line['start_time']}, End: {line['end_time']}, Color: {line['color']}, Style: {line.get('lineStyle', 'Solid')}")

    # Пример данных для сводки анализа (для теста)
    test_df = pd.DataFrame({'close': [118, 119, 120]}, index=pd.to_datetime(['2023-01-01 14:58', '2023-01-01 14:59', '2023-01-01 15:00'], utc=True))
    test_session_fractals = [{'time': pd.Timestamp('2023-01-01 10:30', tz='UTC'), 'price': 102, 'type': 'F_L_AS', 'session': 'Asia'},
                             {'time': pd.Timestamp('2023-01-01 13:30', tz='UTC'), 'price': 118, 'type': 'SETUP_Resist', 'session': 'Setup'}]

    analysis_summary_up = summarize_analysis(test_df, structure_up, test_session_fractals, context_up)
    print("\nСводка анализа (Пример 1):")
    print("Общая информация:")
    for item in analysis_summary_up["general"]:
        print(f"  - {item['description']} ({'✓' if item['status'] else '✗'})")
    print("Подробная информация:")
    for item in analysis_summary_up["detailed"]:
         print(f"  - {item['description']} ({'✓' if item['status'] else '✗'})")


    # Пример данных структуры (консолидация)
    structure_range = [
        {'time': pd.Timestamp('2023-01-03 10:00', tz='UTC'), 'price': 100, 'type': 'LL'},
        {'time': pd.Timestamp('2023-01-03 11:00', tz='UTC'), 'price': 105, 'type': 'HL'},
        {'time': pd.Timestamp('2023-01-03 12:00', tz='UTC'), 'price': 102, 'type': 'LH'},
        {'time': pd.Timestamp('2023-01-03 13:00', tz='UTC'), 'price': 107, 'type': 'HH'}
    ]
    context_range = determine_overall_market_context(structure_range)
    print(f"\nПример 2: Консолидация/Диапазон. Контекст: {context_range}")
    trend_lines_range = determine_trend_lines(structure_range, context_range)
    print("Определенные линии тренда:")
    for line in trend_lines_range:
        print(f"  Start: {line['start_time']}, End: {line['end_time']}, Color: {line['color']}, Style: {line.get('lineStyle', 'Solid')}")

    analysis_summary_range = summarize_analysis(test_df, structure_range, [], context_range) # Пустой список сетапов для примера
    print("\nСводка анализа (Пример 2):")
    print("Общая информация:")
    for item in analysis_summary_range["general"]:
        print(f"  - {item['description']} ({'✓' if item['status'] else '✗'})")
    print("Подробная информация:")
    for item in analysis_summary_range["detailed"]:
         print(f"  - {item['description']} ({'✓' if item['status'] else '✗'})")
