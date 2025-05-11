# ts_logic/context_analyzer_1h.py
import pandas as pd
from configs import settings # Для доступа к SWING_POINT_N
from datetime import time, timedelta, datetime as dt_datetime # Импортируем для анализа сессий и времени

# Соответствие стилей линий числовым значениям Lightweight Charts
LINE_STYLE_SOLID = 0
LINE_STYLE_DOTTED = 1
LINE_STYLE_DASHED = 2
LINE_STYLE_LARGE_DASHED = 3

def find_swing_points(df: pd.DataFrame, n: int = settings.SWING_POINT_N):
    """
    Находит поворотные максимумы (Swing Highs) и минимумы (Swing Lows) на DataFrame.
    n - количество свечей с каждой стороны для определения свинга.
    """
    swing_highs = []
    swing_lows = []

    if not isinstance(df, pd.DataFrame) or df.empty:
        return swing_highs, swing_lows

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
        for j in range(1, n + 1):
            if current_high <= high_prices[i-j] or current_high <= high_prices[i+j]:
                is_swing_high = False
                break
        if is_swing_high:
            swing_highs.append({'time': datetimes[i], 'price': current_high})

        is_swing_low = True
        current_low = low_prices[i]
        for j in range(1, n + 1):
            if current_low >= low_prices[i-j] or current_low >= low_prices[i+j]:
                is_swing_low = False
                break
        if is_swing_low:
            swing_lows.append({'time': datetimes[i], 'price': current_low})
    return swing_highs, swing_lows

def analyze_market_structure_points(swing_highs: list, swing_lows: list):
    """
    Анализирует последовательность свингов для определения HH, HL, LH, LL.
    Эта функция теперь будет работать с более "мажорными" свингами, если SWING_POINT_N увеличено.
    """
    structure_points = []
    if not swing_highs and not swing_lows:
        return structure_points

    all_swings_raw = []
    for sh in swing_highs:
        all_swings_raw.append({'time': sh['time'], 'price': sh['price'], 'swing_type': 'high'})
    for sl in swing_lows:
        all_swings_raw.append({'time': sl['time'], 'price': sl['price'], 'swing_type': 'low'})

    if not all_swings_raw:
        return structure_points

    all_swings_raw.sort(key=lambda x: x['time'])

    # Этап 1: Предварительное определение типов HH, HL, LH, LL, H, L
    # на основе сравнения с непосредственно предыдущим свингом того же типа (high или low).
    temp_structure_points = []
    last_h_info = None # Сохраняем {'time': ..., 'price': ..., 'type': ...}
    last_l_info = None # Сохраняем {'time': ..., 'price': ..., 'type': ...}

    for swing in all_swings_raw:
        current_time = swing['time']
        current_price = swing['price']
        current_swing_type = swing['swing_type']
        point_type_determined = None

        if current_swing_type == 'high':
            if last_h_info:
                if current_price > last_h_info['price']:
                    point_type_determined = "HH"
                elif current_price < last_h_info['price']:
                    point_type_determined = "LH"
                else: # Равные максимумы
                    point_type_determined = "H" # Или можно назвать "EqualH"
            else: # Первый максимум
                point_type_determined = "H"
            # Обновляем информацию о последнем максимуме, включая его тип
            last_h_info = {'time': current_time, 'price': current_price, 'type': point_type_determined}
            # Добавляем в временный список только если тип определен
            if point_type_determined:
                 temp_structure_points.append(last_h_info)


        elif current_swing_type == 'low':
            if last_l_info:
                if current_price < last_l_info['price']:
                    point_type_determined = "LL"
                elif current_price > last_l_info['price']:
                    point_type_determined = "HL"
                else: # Равные минимумы
                    point_type_determined = "L" # Или "EqualL"
            else: # Первый минимум
                point_type_determined = "L"
            # Обновляем информацию о последнем минимуме, включая его тип
            last_l_info = {'time': current_time, 'price': current_price, 'type': point_type_determined}
            if point_type_determined:
                temp_structure_points.append(last_l_info)


    if not temp_structure_points:
        return []

    # Важно: сортируем temp_structure_points по времени, так как максимумы и минимумы добавлялись
    # вперемешку в зависимости от их следования в all_swings_raw.
    temp_structure_points.sort(key=lambda x: x['time'])


    # Этап 2: Фильтрация последовательности для удаления избыточных точек
    # и уточнения типов. Эта логика похожа на оригинальную, но адаптирована.
    if not temp_structure_points:
        return []

    # Начинаем с первой точки из временного списка
    structure_points.append(temp_structure_points[0])

    for i in range(1, len(temp_structure_points)):
        current_sp = temp_structure_points[i]
        prev_sp = structure_points[-1] # Последняя добавленная подтвержденная точка

        # Логика для предотвращения дублирования или нелогичных последовательностей.
        # Пример: если текущая точка того же типа и цены, что и предыдущая, пропускаем.
        # (Это маловероятно, если find_swing_points возвращает уникальные свинги)
        if current_sp['type'] == prev_sp['type'] and \
           abs(current_sp['price'] - prev_sp['price']) < 1e-9 and \
           current_sp['time'] == prev_sp['time']: # Добавил проверку времени для строгости
            continue

        # Если предыдущая точка была просто 'H', а текущая на том же времени/свече
        # оказывается 'HH' или 'LH' (это может случиться, если логика определения
        # типов в Этапе 1 не идеальна или если несколько правил сработало),
        # то обновляем предыдущую точку.
        # Однако, при текущей логике Этапа 1, last_h_info и last_l_info уже содержат
        # более конкретный тип (HH, LH, LL, HL), так что H/L будут только для первых точек.
        # Эта часть фильтрации может быть не так важна сейчас.

        # Основное правило: добавляем точку, если она отличается от предыдущей
        # (либо по типу, либо по цене, либо по времени).
        # Если тип тот же, но цена или время другие - это новый свинг того же типа.
        # Если тип другой - это смена характера свинга.
        
        # Простая логика: если текущая точка не является точным дубликатом предыдущей по всем параметрам,
        # и не является "слабее" (например, H после HH на той же свече), добавляем.
        # Наиболее частый случай - просто добавляем следующую точку из отсортированного списка.
        # Фильтрация от "слишком частых" точек теперь в основном зависит от SWING_POINT_N.

        # Если последняя добавленная точка того же "направления" (high/low),
        # и текущая точка того же направления, но "сильнее" (например, HH после H)
        # или просто другая цена/время - это может быть развитие структуры.
        # Если же текущая точка слабее (например, H после HH на той же свече), это ошибка.

        # Упрощенная фильтрация для данного этапа:
        # Мы уже отсортировали temp_structure_points.
        # Основная задача - не добавлять точки, которые являются частью одного и того же "макро-свинга",
        # но это должно быть решено высоким SWING_POINT_N.
        # Данная фильтрация больше для устранения логических артефактов Этапа 1.

        is_prev_high_type = 'H' in prev_sp['type']
        is_curr_high_type = 'H' in current_sp['type']
        is_prev_low_type = 'L' in prev_sp['type']
        is_curr_low_type = 'L' in current_sp['type']

        # Если предыдущая и текущая точки - это максимумы (или минимумы)
        if (is_prev_high_type and is_curr_high_type) or \
           (is_prev_low_type and is_curr_low_type):
            # Если текущая точка "переписывает" предыдущую (например, цена выше для максимума)
            # или является более сильным определением (HH вместо H).
            # В нашей текущей логике Этапа 1, это уже должно быть учтено в last_h_info/last_l_info.
            # Поэтому, если типы разные (H -> HH), это нормально.
            # Если типы одинаковые (HH -> HH), то это новый свинг, если цена/время другие.
            if prev_sp['type'] == current_sp['type']:
                if abs(prev_sp['price'] - current_sp['price']) > 1e-9 or prev_sp['time'] != current_sp['time']:
                    structure_points.append(current_sp)
                # else: это дубликат по типу, цене и времени - пропускаем (уже сделано выше)
            else: # Типы разные (например, H, потом HH или LH)
                 # Если prev_sp был H, а current_sp стал HH/LH, и это тот же свинг (то же время)
                 # Этого не должно быть, если find_swing_points дает уникальные свинги.
                 # Каждый элемент из all_swings_raw - это отдельный свинг.
                 structure_points.append(current_sp)
        else:
            # Смена направления (например, после максимума идет минимум) - всегда добавляем.
            structure_points.append(current_sp)


    # print(f"analyze_market_structure_points: Определено {len(structure_points)} точек структуры.")
    return structure_points


def determine_overall_market_context(structure_points: list):
    """
    Определяет общий рыночный контекст (LONG, SHORT, NEUTRAL)
    на основе последних нескольких точек структуры, с учетом BOS для подтверждения тренда.
    """
    if not structure_points:
        return "NEUTRAL/RANGING (нет данных о структуре)"

    trend_defining_points = [p for p in structure_points if p['type'] in ['HH', 'HL', 'LH', 'LL']]

    if len(trend_defining_points) < 2:
         if len(trend_defining_points) == 1:
             last_tdp_single = trend_defining_points[0]
             if last_tdp_single['type'] == 'HH': return "NEUTRAL (Первый BOS вверх, ожидание HL)"
             elif last_tdp_single['type'] == 'LL': return "NEUTRAL (Первый BOS вниз, ожидание LH)"
             return "NEUTRAL/RANGING (недостаточно трендовых точек)"
         # Если есть только H/L точки, но нет трендовых HH/HL/LH/LL
         if len(structure_points) >=2:
             # Проверим последние две точки H/L
             p1 = structure_points[-1]
             p0 = structure_points[-2]
             if p1['type'] == 'H' and p0['type'] == 'L' and p1['price'] > p0['price']: return "NEUTRAL (L -> H)"
             if p1['type'] == 'L' and p0['type'] == 'H' and p1['price'] < p0['price']: return "NEUTRAL (H -> L)"
         return "NEUTRAL/RANGING (недостаточно трендовых точек)"


    last_p = trend_defining_points[-1]
    second_last_p = trend_defining_points[-2]
    context = "NEUTRAL/RANGING (неопределенная структура)"

    if last_p['type'] == 'HH':
        if second_last_p['type'] == 'HL':
            context = "LONG (Тренд вверх: HH после HL)"
        elif second_last_p['type'] in ['LL', 'LH', 'L']: # Добавил L для случая L -> HH (BOS)
             prior_lhs_or_hs = [p for p in structure_points[:-1] if p['type'] in ['LH', 'H']] # Ищем предыдущий LH или H
             if prior_lhs_or_hs and last_p['price'] > prior_lhs_or_hs[-1]['price']:
                  context = "LONG (BOS: HH пробил предыдущий LH/H)"
             else:
                  context = "NEUTRAL (HH не пробил ключевой LH/H, ожидание HL/дальнейшего BOS)"
        else: context = "NEUTRAL (HH сформирован, но последовательность неясна)"

    elif last_p['type'] == 'HL':
        if second_last_p['type'] == 'HH':
            context = "LONG (Тренд вверх: коррекция HL после HH)"
        else: context = "NEUTRAL/RANGING (Формируется HL без предшествующего HH)"

    elif last_p['type'] == 'LL':
        if second_last_p['type'] == 'LH':
            context = "SHORT (Тренд вниз: LL после LH)"
        elif second_last_p['type'] in ['HH', 'HL', 'H']: # Добавил H для случая H -> LL (BOS)
             prior_hls_or_ls = [p for p in structure_points[:-1] if p['type'] in ['HL', 'L']] # Ищем предыдущий HL или L
             if prior_hls_or_ls and last_p['price'] < prior_hls_or_ls[-1]['price']:
                    context = "SHORT (BOS: LL пробил предыдущий HL/L)"
             else:
                    context = "NEUTRAL (LL не пробил ключевой HL/L, ожидание LH/дальнейшего BOS)"
        else: context = "NEUTRAL (LL сформирован, но последовательность неясна)"

    elif last_p['type'] == 'LH':
        if second_last_p['type'] == 'LL':
            context = "SHORT (Тренд вниз: коррекция LH после LL)"
        else: context = "NEUTRAL/RANGING (Формируется LH без предшествующего LL)"

    if "NEUTRAL" in context or "RANGING" in context: # Дополнительная проверка на консолидацию
         if len(trend_defining_points) >= 2 :
            p1 = trend_defining_points[-1]; p0 = trend_defining_points[-2]
            if (p1['type'] == 'LH' and p0['type'] == 'HL') or \
               (p1['type'] == 'HL' and p0['type'] == 'LH'):
                context = "NEUTRAL/RANGING (Сужение/консолидация)"
            elif (p1['type'] == 'HH' and p0['type'] == 'LL') or \
                 (p1['type'] == 'LL' and p0['type'] == 'HH'):
                 context = "NEUTRAL/RANGING (Расширение диапазона)"
    return context

def determine_trend_lines(structure_points: list, context: str):
    """
    Определяет координаты линий тренда на основе точек структуры и контекста.
    """
    trend_lines = []
    trend_defining_points = [p for p in structure_points if p['type'] in ['HH', 'HL', 'LH', 'LL']]

    if len(trend_defining_points) < 2: return trend_lines

    if "LONG" in context:
        hl_points = [p for p in trend_defining_points if p['type'] == 'HL']
        if len(hl_points) >= 2:
            points_to_connect = sorted(hl_points[-2:], key=lambda x: x['time'])
            if len(points_to_connect) >= 2:
                 trend_lines.append({
                    'start_time': points_to_connect[0]['time'], 'start_price': points_to_connect[0]['price'],
                    'end_time': points_to_connect[-1]['time'], 'end_price': points_to_connect[-1]['price'],
                    'color': '#26A69A', 'lineStyle': LINE_STYLE_SOLID })
        hh_points = [p for p in trend_defining_points if p['type'] == 'HH']
        if len(hh_points) >= 2:
             points_to_connect_hh = sorted(hh_points[-2:], key=lambda x: x['time'])
             if len(points_to_connect_hh) >= 2:
                  trend_lines.append({
                     'start_time': points_to_connect_hh[0]['time'], 'start_price': points_to_connect_hh[0]['price'],
                     'end_time': points_to_connect_hh[-1]['time'], 'end_price': points_to_connect_hh[-1]['price'],
                     'color': '#2962FF', 'lineStyle': LINE_STYLE_SOLID })
    elif "SHORT" in context:
        lh_points = [p for p in trend_defining_points if p['type'] == 'LH']
        if len(lh_points) >= 2:
            points_to_connect = sorted(lh_points[-2:], key=lambda x: x['time'])
            if len(points_to_connect) >= 2:
                 trend_lines.append({
                    'start_time': points_to_connect[0]['time'], 'start_price': points_to_connect[0]['price'],
                    'end_time': points_to_connect[-1]['time'], 'end_price': points_to_connect[-1]['price'],
                    'color': '#EF5350', 'lineStyle': LINE_STYLE_SOLID })
        ll_points = [p for p in trend_defining_points if p['type'] == 'LL']
        if len(ll_points) >= 2:
             points_to_connect_ll = sorted(ll_points[-2:], key=lambda x: x['time'])
             if len(points_to_connect_ll) >= 2:
                  trend_lines.append({
                     'start_time': points_to_connect_ll[0]['time'], 'start_price': points_to_connect_ll[0]['price'],
                     'end_time': points_to_connect_ll[-1]['time'], 'end_price': points_to_connect_ll[-1]['price'],
                     'color': '#26A69A', 'lineStyle': LINE_STYLE_SOLID })
    elif "NEUTRAL" in context or "RANGING" in context:
        # Используем все точки структуры для определения границ диапазона, если трендовых мало
        points_for_range = trend_defining_points if len(trend_defining_points) >=2 else structure_points
        if len(points_for_range) >=1: # Нужно хотя бы одна точка для отрисовки горизонтальной линии
            last_relevant_high = next((p for p in reversed(points_for_range) if 'H' in p['type']), None)
            last_relevant_low = next((p for p in reversed(points_for_range) if 'L' in p['type']), None)

            first_point_time = points_for_range[0]['time']
            last_point_time = points_for_range[-1]['time']

            if last_relevant_high:
                 trend_lines.append({
                    'start_time': first_point_time, 'start_price': last_relevant_high['price'],
                    'end_time': last_point_time, 'end_price': last_relevant_high['price'],
                    'color': '#808080', 'lineStyle': LINE_STYLE_DOTTED })
            if last_relevant_low:
                 trend_lines.append({
                    'start_time': first_point_time, 'start_price': last_relevant_low['price'],
                    'end_time': last_point_time, 'end_price': last_relevant_low['price'],
                    'color': '#808080', 'lineStyle': LINE_STYLE_DOTTED })
    return trend_lines

def summarize_analysis(market_data_df: pd.DataFrame, structure_points: list, session_fractal_and_setup_points: list, overall_context: str):
    analysis_summary = {
        "Общая информация": [], "Подробная информация": [], "Цели": [],
        "Точки набора": [], "Другое": []
    }
    analysis_summary["Общая информация"].append({
        'description': f"Общий контекст: {overall_context}", 'status': True })

    trend_defining_points = [p for p in structure_points if p['type'] in ['HH', 'HL', 'LH', 'LL']]
    if len(trend_defining_points) >= 2:
        last_two_types = f"{trend_defining_points[-2]['type']} -> {trend_defining_points[-1]['type']}"
        analysis_summary["Общая информация"].append({'description': f"Структура: {last_two_types}", 'status': True})
    elif len(trend_defining_points) == 1:
         analysis_summary["Общая информация"].append({'description': f"Структура: {trend_defining_points[0]['type']} (начало)", 'status': True})
    elif len(structure_points) >=1 : # Если есть только H/L
        analysis_summary["Общая информация"].append({'description': f"Структура: Последняя точка {structure_points[-1]['type']}", 'status': True})
    else:
         analysis_summary["Общая информация"].append({'description': "Структура: Недостаточно точек", 'status': False})

    setup_points = [p for p in session_fractal_and_setup_points if 'SETUP' in p.get('type', '')]
    analysis_summary["Общая информация"].append({'description': f"Найдено сетапов: {len(setup_points)}", 'status': len(setup_points) > 0})

    # --- Заглушки для остальных пунктов сводки (логика не менялась) ---
    swiped_liquidity_status = False; swiped_liquidity_desc = "Не проверено"
    if "LONG" in overall_context: swiped_liquidity_desc = "Свип PDH / Биг пула вверх"
    elif "SHORT" in overall_context: swiped_liquidity_desc = "Свип PDL / Биг пула вниз"
    else: swiped_liquidity_desc = "Свип ликвидности (нейтральный контекст)"
    analysis_summary["Подробная информация"].append({'description': swiped_liquidity_desc, 'status': swiped_liquidity_status})

    order_flow_status = False
    analysis_summary["Подробная информация"].append({'description': "Ордер флоу работа (снятия + тесты блоков)",'status': order_flow_status})
    asia_sync_status = False; asia_direction_desc = "Не определено"
    analysis_summary["Подробная информация"].append({'description': f"Азия синхронна ({asia_direction_desc})", 'status': asia_sync_status})
    range_sweep_status = True; range_sweep_desc = "Нет явного ренджа/свипов по обе стороны"
    analysis_summary["Подробная информация"].append({'description': range_sweep_desc, 'status': range_sweep_status})
    htf_sweep_asia_against_trend_status = False
    analysis_summary["Подробная информация"].append({'description': "Свип HTF Азией против тренда", 'status': not htf_sweep_asia_against_trend_status})
    frankfurt_london_manipulation_status = False
    analysis_summary["Подробная информация"].append({'description': "Манипуляции Франкфурт/Лондон", 'status': not frankfurt_london_manipulation_status})

    targets_exist = False; target_distance_met = False; rr_acceptable = False
    analysis_summary["Цели"].append({'description': f"Цели определены: {'Да' if targets_exist else 'Нет'}", 'status': targets_exist})
    analysis_summary["Цели"].append({'description': "Расстояние до целей (250/400 пипсов)", 'status': target_distance_met})
    analysis_summary["Цели"].append({'description': "Допустимый RR", 'status': rr_acceptable})

    has_entry_fractals = len(setup_points) > 0
    analysis_summary["Точки набора"].append({'description': "Есть фракталы для работы (сетапы)", 'status': has_entry_fractals})
    invalidation_breached = False
    analysis_summary["Точки набора"].append({'description': "Идея не инвалидирована (нет закрепления)", 'status': not invalidation_breached})

    is_ott = False
    analysis_summary["Другое"].append({'description': f"OTT: {'Да' if is_ott else 'Нет'}", 'status': is_ott})
    has_news = False
    analysis_summary["Другое"].append({'description': "Нет важных новостей", 'status': not has_news})
    return analysis_summary

if __name__ == '__main__':
    print("Тестирование context_analyzer_1h.py...")
    # Создаем тестовый DataFrame
    rng = pd.date_range(start='2023-01-01 00:00', end='2023-01-03 23:59', freq='1H', tz='UTC')
    data = {
        'open': [100, 102, 101, 103, 102, 105, 104, 106, 105, 107, 106, 108, 107, 105, 106, 104, 102, 103, 101, 100] * (len(rng)//20 +1) [:len(rng)],
        'high': [101, 103, 102, 104, 103, 106, 105, 107, 106, 108, 107, 109, 108, 106, 107, 105, 103, 104, 102, 101] * (len(rng)//20 +1) [:len(rng)],
        'low':  [99,  101, 100, 102, 101, 104, 103, 105, 104, 106, 105, 107, 106, 104, 105, 103, 101, 102, 100, 99]  * (len(rng)//20 +1) [:len(rng)],
        'close':[100.5,102.5,101.5,103.5,102.5,105.5,104.5,106.5,105.5,107.5,106.5,108.5,107.5,105.5,106.5,104.5,102.5,103.5,101.5,100.5] * (len(rng)//20+1)[:len(rng)],
        'volume':[100]*len(rng)
    }
    test_df = pd.DataFrame(data, index=rng)

    print(f"\nТестирование с SWING_POINT_N = {settings.SWING_POINT_N}")
    sw_h, sw_l = find_swing_points(test_df, n=settings.SWING_POINT_N)
    print(f"Найдено свингов: Highs={len(sw_h)}, Lows={len(sw_l)}")

    struct_pts = analyze_market_structure_points(sw_h, sw_l)
    print("\nТочки структуры:")
    for pt in struct_pts[-10:]: # Показываем последние 10 для краткости
        print(f"  Время: {pt['time']}, Цена: {pt['price']:.2f}, Тип: {pt['type']}")

    context = determine_overall_market_context(struct_pts)
    print(f"\nОбщий контекст: {context}")

    trend_lines = determine_trend_lines(struct_pts, context)
    print(f"\nЛинии тренда: {len(trend_lines)}")
    for tl in trend_lines:
        print(f"  {tl['start_time']} ({tl['start_price']}) -> {tl['end_time']} ({tl['end_price']}) Color: {tl['color']}")

    # Для тестирования summarize_analysis
    summary = summarize_analysis(test_df, struct_pts, [], context) # Пустой список сессионных фракталов для теста
    print("\nСводка анализа:")
    for section, items in summary.items():
        print(f"--- {section} ---")
        if items: # Проверка, что список не пустой
            for item in items:
                print(f"  - {item['description']} ({'✓' if item.get('status', False) else '✗'})") # Добавил .get для status
        else:
            print("  Нет данных.")
