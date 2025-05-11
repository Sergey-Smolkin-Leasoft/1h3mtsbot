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
            swing_highs.append({'time': datetimes[i], 'price': current_high, 'type': 'H_SWING'}) # Добавляем тип для ясности

        is_swing_low = True
        current_low = low_prices[i]
        for j in range(1, n + 1):
            if current_low >= low_prices[i-j] or current_low >= low_prices[i+j]:
                is_swing_low = False
                break
        if is_swing_low:
            swing_lows.append({'time': datetimes[i], 'price': current_low, 'type': 'L_SWING'}) # Добавляем тип для ясности
    return swing_highs, swing_lows

def analyze_market_structure_points(swing_highs: list, swing_lows: list):
    """
    Анализирует последовательность свингов для определения HH, HL, LH, LL.
    Эта функция теперь будет работать с более "мажорными" свингами, если SWING_POINT_N увеличено.
    Эта функция используется для определения маркеров на графике и для текстовой сводки,
    но НЕ для рисования линий тренда в новой логике.
    """
    structure_points = []
    if not swing_highs and not swing_lows:
        return structure_points

    all_swings_raw = []
    # Используем тип, присвоенный в find_swing_points, но для логики HH/HL нужен 'high'/'low'
    for sh in swing_highs:
        all_swings_raw.append({'time': sh['time'], 'price': sh['price'], 'swing_type': 'high'}) # swing_type для этой функции
    for sl in swing_lows:
        all_swings_raw.append({'time': sl['time'], 'price': sl['price'], 'swing_type': 'low'}) # swing_type для этой функции

    if not all_swings_raw:
        return structure_points

    all_swings_raw.sort(key=lambda x: x['time'])

    temp_structure_points = []
    last_h_info = None
    last_l_info = None

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
                else:
                    point_type_determined = "H"
            else:
                point_type_determined = "H"
            last_h_info = {'time': current_time, 'price': current_price, 'type': point_type_determined}
            if point_type_determined:
                 temp_structure_points.append(last_h_info)
        elif current_swing_type == 'low':
            if last_l_info:
                if current_price < last_l_info['price']:
                    point_type_determined = "LL"
                elif current_price > last_l_info['price']:
                    point_type_determined = "HL"
                else:
                    point_type_determined = "L"
            else:
                point_type_determined = "L"
            last_l_info = {'time': current_time, 'price': current_price, 'type': point_type_determined}
            if point_type_determined:
                temp_structure_points.append(last_l_info)

    if not temp_structure_points:
        return []

    temp_structure_points.sort(key=lambda x: x['time'])
    if not temp_structure_points:
        return []

    structure_points.append(temp_structure_points[0])
    for i in range(1, len(temp_structure_points)):
        current_sp = temp_structure_points[i]
        prev_sp = structure_points[-1]
        is_prev_high_type = 'H' in prev_sp['type']
        is_curr_high_type = 'H' in current_sp['type']
        is_prev_low_type = 'L' in prev_sp['type']
        is_curr_low_type = 'L' in current_sp['type']

        if (is_prev_high_type and is_curr_high_type) or \
           (is_prev_low_type and is_curr_low_type):
            if prev_sp['type'] == current_sp['type']:
                if abs(prev_sp['price'] - current_sp['price']) > 1e-9 or prev_sp['time'] != current_sp['time']:
                    structure_points.append(current_sp)
            else:
                 structure_points.append(current_sp)
        else:
            structure_points.append(current_sp)
    return structure_points


def determine_overall_market_context(structure_points: list):
    """
    Определяет общий рыночный контекст (LONG, SHORT, NEUTRAL)
    на основе последних нескольких точек структуры (HH, HL, LH, LL).
    Используется для текстовой сводки.
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
         if len(structure_points) >=2:
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
        elif second_last_p['type'] in ['LL', 'LH', 'L']:
             prior_lhs_or_hs = [p for p in structure_points[:-1] if p['type'] in ['LH', 'H']]
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
        elif second_last_p['type'] in ['HH', 'HL', 'H']:
             prior_hls_or_ls = [p for p in structure_points[:-1] if p['type'] in ['HL', 'L']]
             if prior_hls_or_ls and last_p['price'] < prior_hls_or_ls[-1]['price']:
                    context = "SHORT (BOS: LL пробил предыдущий HL/L)"
             else:
                    context = "NEUTRAL (LL не пробил ключевой HL/L, ожидание LH/дальнейшего BOS)"
        else: context = "NEUTRAL (LL сформирован, но последовательность неясна)"
    elif last_p['type'] == 'LH':
        if second_last_p['type'] == 'LL':
            context = "SHORT (Тренд вниз: коррекция LH после LL)"
        else: context = "NEUTRAL/RANGING (Формируется LH без предшествующего LL)"

    if "NEUTRAL" in context or "RANGING" in context:
         if len(trend_defining_points) >= 2 :
            p1 = trend_defining_points[-1]; p0 = trend_defining_points[-2]
            if (p1['type'] == 'LH' and p0['type'] == 'HL') or \
               (p1['type'] == 'HL' and p0['type'] == 'LH'):
                context = "NEUTRAL/RANGING (Сужение/консолидация)"
            elif (p1['type'] == 'HH' and p0['type'] == 'LL') or \
                 (p1['type'] == 'LL' and p0['type'] == 'HH'):
                 context = "NEUTRAL/RANGING (Расширение диапазона)"
    return context


def determine_trend_lines_v2(swing_highs: list, swing_lows: list, last_data_timestamp: pd.Timestamp = None):
    """
    Определяет линии тренда на основе последних двух свингов (максимумов и минимумов).
    Линии продлеваются до last_data_timestamp.
    Эта функция НЕ зависит от HH/HL/LH/LL.
    """
    trend_lines = []

    if not last_data_timestamp:
        all_swing_times = [p['time'] for p in swing_highs] + [p['time'] for p in swing_lows]
        if not all_swing_times:
            print("determine_trend_lines_v2: Нет данных о времени свингов, невозможно определить last_data_timestamp.")
            return trend_lines
        last_data_timestamp = max(all_swing_times)
        print(f"determine_trend_lines_v2: last_data_timestamp не передан, используется максимальное время свинга: {last_data_timestamp}")


    # --- ЛИНИЯ ПОДДЕРЖКИ ПО ПОСЛЕДНИМ ДВУМ МИНИМУМАМ ---
    sorted_lows = sorted(swing_lows, key=lambda x: x['time'])
    if len(sorted_lows) >= 2:
        p_start_low = sorted_lows[-2]
        p_end_for_slope_low = sorted_lows[-1]

        final_end_time_low = last_data_timestamp
        final_end_price_low = p_end_for_slope_low['price'] 

        # Проверяем, что p_start_low['time'] действительно является Timestamp
        if not isinstance(p_start_low['time'], pd.Timestamp) or not isinstance(p_end_for_slope_low['time'], pd.Timestamp):
            print("determine_trend_lines_v2: Время в точках минимума не является Timestamp. Пропуск линии поддержки.")
        elif p_start_low['time'] < p_end_for_slope_low['time']:
            time_delta_original_seconds = (p_end_for_slope_low['time'] - p_start_low['time']).total_seconds()
            price_delta_original = p_end_for_slope_low['price'] - p_start_low['price']

            if time_delta_original_seconds > 0:
                slope = price_delta_original / time_delta_original_seconds
                time_delta_to_projected_end_seconds = (last_data_timestamp - p_start_low['time']).total_seconds()
                final_end_price_low = p_start_low['price'] + slope * time_delta_to_projected_end_seconds
        elif p_start_low['time'] == p_end_for_slope_low['time']:
             final_end_price_low = p_end_for_slope_low['price']
        
        # Добавляем линию, только если начальная точка раньше конечной точки проекции
        if isinstance(p_start_low['time'], pd.Timestamp) and p_start_low['time'] < final_end_time_low :
            trend_lines.append({
                'start_time': p_start_low['time'], 'start_price': p_start_low['price'],
                'end_time': final_end_time_low, 'end_price': final_end_price_low,
                'color': '#26A69A',
                'lineStyle': LINE_STYLE_SOLID
            })
            # print(f"determine_trend_lines_v2: Добавлена линия поддержки: {p_start_low['time']} ({p_start_low['price']}) -> {final_end_time_low} ({final_end_price_low})")

    # --- ЛИНИЯ СОПРОТИВЛЕНИЯ ПО ПОСЛЕДНИМ ДВУМ МАКСИМУМАМ ---
    sorted_highs = sorted(swing_highs, key=lambda x: x['time'])
    if len(sorted_highs) >= 2:
        p_start_high = sorted_highs[-2]
        p_end_for_slope_high = sorted_highs[-1]

        final_end_time_high = last_data_timestamp
        final_end_price_high = p_end_for_slope_high['price']

        if not isinstance(p_start_high['time'], pd.Timestamp) or not isinstance(p_end_for_slope_high['time'], pd.Timestamp):
            print("determine_trend_lines_v2: Время в точках максимума не является Timestamp. Пропуск линии сопротивления.")
        elif p_start_high['time'] < p_end_for_slope_high['time']:
            time_delta_original_seconds = (p_end_for_slope_high['time'] - p_start_high['time']).total_seconds()
            price_delta_original = p_end_for_slope_high['price'] - p_start_high['price']

            if time_delta_original_seconds > 0:
                slope = price_delta_original / time_delta_original_seconds
                time_delta_to_projected_end_seconds = (last_data_timestamp - p_start_high['time']).total_seconds()
                final_end_price_high = p_start_high['price'] + slope * time_delta_to_projected_end_seconds
        elif p_start_high['time'] == p_end_for_slope_high['time']:
             final_end_price_high = p_end_for_slope_high['price']
        
        if isinstance(p_start_high['time'], pd.Timestamp) and p_start_high['time'] < final_end_time_high:
            trend_lines.append({
                'start_time': p_start_high['time'], 'start_price': p_start_high['price'],
                'end_time': final_end_time_high, 'end_price': final_end_price_high,
                'color': '#EF5350',
                'lineStyle': LINE_STYLE_SOLID
            })
            # print(f"determine_trend_lines_v2: Добавлена линия сопротивления: {p_start_high['time']} ({p_start_high['price']}) -> {final_end_time_high} ({final_end_price_high})")
            
    # print(f"determine_trend_lines_v2: Всего линий тренда: {len(trend_lines)}")
    return trend_lines


def summarize_analysis(market_data_df: pd.DataFrame, structure_points: list, session_fractal_and_setup_points: list, overall_context: str):
    """
    Формирует текстовую сводку анализа.
    """
    analysis_summary = {
        "Общая информация": [], "Подробная информация": [], "Цели": [],
        "Точки набора": [], "Другое": []
    }
    analysis_summary["Общая информация"].append({
        'description': f"Общий контекст: {overall_context}", 'status': True })

    trend_defining_points = [p for p in structure_points if p['type'] in ['HH', 'HL', 'LH', 'LL']]
    if len(trend_defining_points) >= 2:
        last_two_types = f"{trend_defining_points[-2]['type']} -> {trend_defining_points[-1]['type']}"
        analysis_summary["Общая информация"].append({'description': f"Структура (HH/HL): {last_two_types}", 'status': True})
    elif len(trend_defining_points) == 1:
         analysis_summary["Общая информация"].append({'description': f"Структура (HH/HL): {trend_defining_points[0]['type']} (начало)", 'status': True})
    elif len(structure_points) >=1 : 
        # Показываем последний общий свинг, если нет HH/HL точек
        non_hh_hl_structure_points = [p for p in structure_points if p['type'] in ['H', 'L']]
        if non_hh_hl_structure_points:
            analysis_summary["Общая информация"].append({'description': f"Структура (Общая): Последняя точка {non_hh_hl_structure_points[-1]['type']}", 'status': True})
        else: # Если есть только H_SWING или L_SWING (не прошедшие классификацию HH/HL)
            # Этого случая быть не должно, т.к. structure_points это результат analyze_market_structure_points
            analysis_summary["Общая информация"].append({'description': "Структура (HH/HL): Недостаточно точек", 'status': False})
    else:
         analysis_summary["Общая информация"].append({'description': "Структура (HH/HL): Недостаточно точек", 'status': False})


    setup_points = [p for p in session_fractal_and_setup_points if 'SETUP' in p.get('type', '')]
    analysis_summary["Общая информация"].append({'description': f"Найдено сетапов: {len(setup_points)}", 'status': len(setup_points) > 0})

    # --- Заглушки для остальных пунктов сводки ---
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
    if sw_h: print(f"  Пример Swing High: {sw_h[0]}")
    if sw_l: print(f"  Пример Swing Low: {sw_l[0]}")


    struct_pts = analyze_market_structure_points(sw_h, sw_l) # Для маркеров HH/HL и контекста
    print("\nТочки структуры (HH/HL и т.д.):")
    for pt in struct_pts[-5:]:
        print(f"  Время: {pt['time']}, Цена: {pt['price']:.2f}, Тип: {pt['type']}")

    context = determine_overall_market_context(struct_pts) # Для сводки
    print(f"\nОбщий контекст (из HH/HL): {context}")

    # Тестирование новой функции линий тренда
    last_ts_for_lines = test_df.index[-1] if not test_df.empty else None
    if last_ts_for_lines:
        trend_lines_new = determine_trend_lines_v2(sw_h, sw_l, last_ts_for_lines)
        print(f"\nЛинии тренда (новая логика, v2): {len(trend_lines_new)}")
        for tl_idx, tl_val in enumerate(trend_lines_new):
            print(f"  Линия {tl_idx+1}: {tl_val['start_time']} ({tl_val['start_price']:.2f}) -> {tl_val['end_time']} ({tl_val['end_price']:.2f}) Color: {tl_val['color']}")
    else:
        print("\nНе удалось определить last_ts_for_lines для теста determine_trend_lines_v2.")


    summary = summarize_analysis(test_df, struct_pts, [], context)
    print("\nСводка анализа:")
    for section, items in summary.items():
        print(f"--- {section} ---")
        if items:
            for item in items:
                print(f"  - {item['description']} ({'✓' if item.get('status', False) else '✗'})")
        else:
            print("  Нет данных.")