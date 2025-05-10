# ts_logic/context_analyzer_1h.py
import pandas as pd
from configs import settings # Для доступа к SWING_POINT_N

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
        
    if len(df) < (2 * n + 1):
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
    """
    structure_points = []
    if not swing_highs and not swing_lows:
        return structure_points

    all_swings = []
    for sh in swing_highs:
        all_swings.append({'time': sh['time'], 'price': sh['price'], 'swing_type': 'high'})
    for sl in swing_lows:
        all_swings.append({'time': sl['time'], 'price': sl['price'], 'swing_type': 'low'})
    
    if not all_swings:
        return structure_points

    all_swings.sort(key=lambda x: x['time'])
    
    last_h = None 
    last_l = None 

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
                    point_type_determined = "H" 
            else: 
                point_type_determined = "H" 
            last_h = {'time': current_time, 'price': current_price} 
            
        elif current_swing_type == 'low':
            if last_l:
                if current_price < last_l['price']:
                    point_type_determined = "LL" 
                elif current_price > last_l['price']:
                    point_type_determined = "HL" 
                else: 
                    point_type_determined = "L" 
            else: 
                point_type_determined = "L" 
            last_l = {'time': current_time, 'price': current_price} 

        if point_type_determined:
            structure_points.append({
                'time': current_time, 
                'price': current_price, 
                'type': point_type_determined
            })

    if not structure_points:
        return []

    final_structure_points = []
    if structure_points:
        final_structure_points.append(structure_points[0])
        for i in range(1, len(structure_points)):
            current_sp = structure_points[i]
            prev_sp = final_structure_points[-1]

            is_same_basic_type = current_sp['type'] in ['H', 'L'] and current_sp['type'] == prev_sp['type']
            is_same_price = abs(current_sp['price'] - prev_sp['price']) < 1e-9 

            if is_same_basic_type and is_same_price:
                continue
            
            if prev_sp['type'] == 'H' and current_sp['type'] in ['HH', 'LH'] and current_sp['time'] == prev_sp['time']: 
                final_structure_points[-1] = current_sp 
                continue
            if prev_sp['type'] == 'L' and current_sp['type'] in ['LL', 'HL'] and current_sp['time'] == prev_sp['time']:
                final_structure_points[-1] = current_sp 
                continue
            final_structure_points.append(current_sp)
            
    return final_structure_points

def determine_overall_market_context(structure_points: list):
    """
    Определяет общий рыночный контекст (LONG, SHORT, NEUTRAL)
    на основе последних нескольких точек структуры, с учетом BOS для подтверждения тренда.
    """
    if not structure_points:
        return "NEUTRAL/RANGING (нет данных о структуре)"

    trend_defining_points = [p for p in structure_points if p['type'] in ['HH', 'HL', 'LH', 'LL']]
    
    if not trend_defining_points: # Если нет HH, HL, LH, LL
         return "NEUTRAL/RANGING (нет трендовых точек HH/HL/LH/LL)"

    if len(trend_defining_points) == 1:
        last_tdp_single = trend_defining_points[0]
        if last_tdp_single['type'] == 'HH':
            return "NEUTRAL (BOS вверх: HH первый в трендовой структуре, ожидание HL)"
        elif last_tdp_single['type'] == 'LL':
            return "NEUTRAL (BOS вниз: LL первый в трендовой структуре, ожидание LH)"
        elif last_tdp_single['type'] == 'HL':
            return "NEUTRAL/RANGING (Начальная трендовая точка: HL)"
        elif last_tdp_single['type'] == 'LH':
            return "NEUTRAL/RANGING (Начальная трендовая точка: LH)"

    last_p = trend_defining_points[-1]
    second_last_p = trend_defining_points[-2] if len(trend_defining_points) >= 2 else None

    context = "NEUTRAL/RANGING (неопределенная структура)" # Значение по умолчанию

    if last_p['type'] == 'HH':
        if second_last_p and second_last_p['type'] == 'HL':
            context = "LONG (Тренд вверх: HH после HL)"
        else:
            # Ищем предыдущий LH, который был пробит текущим HH
            # Рассматриваем все точки LH до текущего HH
            prior_lhs = [p for p in trend_defining_points[:-1] if p['type'] == 'LH']
            if prior_lhs:
                most_recent_prior_lh = prior_lhs[-1] # Самый последний LH перед текущим HH
                if last_p['price'] > most_recent_prior_lh['price']:
                    context = "LONG (BOS: HH пробил предыдущий LH)"
                else:
                    # HH сформирован, но не пробил последний значимый LH
                    context = "NEUTRAL (HH не пробил ключевой LH, ожидание HL/дальнейшего BOS)"
            else:
                # Нет предыдущих LH в трендовой структуре, это первый HH или HH после LL
                context = "NEUTRAL (BOS вверх: HH без пробития предшествующего LH в структуре, ожидание HL)"
    
    elif last_p['type'] == 'HL':
        if second_last_p and second_last_p['type'] == 'HH':
            context = "LONG (Тренд вверх: коррекция HL после HH)"
        else:
            # HL сформирован, но не после HH.
            context = "NEUTRAL/RANGING (Формируется HL без предшествующего HH для подтверждения тренда)"

    elif last_p['type'] == 'LL':
        if second_last_p and second_last_p['type'] == 'LH':
            context = "SHORT (Тренд вниз: LL после LH)"
        else:
            # Ищем предыдущий HL, который был пробит текущим LL
            prior_hls = [p for p in trend_defining_points[:-1] if p['type'] == 'HL']
            if prior_hls:
                most_recent_prior_hl = prior_hls[-1] # Самый последний HL перед текущим LL
                if last_p['price'] < most_recent_prior_hl['price']:
                    context = "SHORT (BOS: LL пробил предыдущий HL)"
                else:
                    # LL сформирован, но не пробил последний значимый HL
                    context = "NEUTRAL (LL не пробил ключевой HL, ожидание LH/дальнейшего BOS)"
            else:
                # Нет предыдущих HL в трендовой структуре
                context = "NEUTRAL (BOS вниз: LL без пробития предшествующего HL в структуре, ожидание LH)"

    elif last_p['type'] == 'LH':
        if second_last_p and second_last_p['type'] == 'LL':
            context = "SHORT (Тренд вниз: коррекция LH после LL)"
        else:
            context = "NEUTRAL/RANGING (Формируется LH без предшествующего LL для подтверждения тренда)"

    # Дополнительная проверка на явные признаки консолидации, если контекст все еще не ясен
    if "NEUTRAL/RANGING" in context and len(trend_defining_points) >= 2 :
        p1 = trend_defining_points[-1] 
        p0 = trend_defining_points[-2]
        if (p1['type'] == 'LH' and p0['type'] == 'HL') or \
           (p1['type'] == 'HL' and p0['type'] == 'LH'):
            context = "NEUTRAL/RANGING (Сужение/консолидация)"
            
    if context == "NEUTRAL/RANGING (неопределенная структура)":
        if len(structure_points) >= 2: # Используем все точки структуры для общей оценки
            last_h_overall = next((p for p in reversed(structure_points) if p['type'] in ['H', 'HH']), None)
            last_l_overall = next((p for p in reversed(structure_points) if p['type'] in ['L', 'LL']), None)

            if last_h_overall and last_l_overall:
                if last_h_overall['time'] > last_l_overall['time'] and last_h_overall['price'] > last_l_overall['price']:
                    context = "NEUTRAL/RANGING (Общее движение вверх)"
                elif last_l_overall['time'] > last_h_overall['time'] and last_l_overall['price'] < last_h_overall['price']:
                    context = "NEUTRAL/RANGING (Общее движение вниз)"
            elif last_h_overall:
                 context = "NEUTRAL/RANGING (Преобладают максимумы)"
            elif last_l_overall:
                 context = "NEUTRAL/RANGING (Преобладают минимумы)"
        else:
            context = "NEUTRAL/RANGING (крайне мало данных о структуре)"
            
    return context

if __name__ == '__main__':
    print("Тестирование context_analyzer_1h.py...")
    
    # Пример 1: Восходящий тренд (HL -> HH)
    print("\n--- Пример 1: Восходящий тренд (HL -> HH) ---")
    structure_up = [
        # {'time': pd.Timestamp('2023-01-01 10:00'), 'price': 100, 'type': 'L'}, # Не входит в trend_defining_points
        # {'time': pd.Timestamp('2023-01-01 11:00'), 'price': 110, 'type': 'H'}, # Не входит в trend_defining_points
        {'time': pd.Timestamp('2023-01-01 12:00'), 'price': 105, 'type': 'HL'}, 
        {'time': pd.Timestamp('2023-01-01 13:00'), 'price': 115, 'type': 'HH'}
    ]
    print(f"Точки (trend_defining): {[p['type'] for p in structure_up]}")
    print(f"Контекст: {determine_overall_market_context(structure_up)}") 
    # Ожидаем: LONG (Тренд вверх: HH после HL)

    # Пример 2: Восходящий тренд (HH -> HL) - коррекция
    print("\n--- Пример 2: Восходящий тренд (HH -> HL) ---")
    structure_up_corr = [
        {'time': pd.Timestamp('2023-01-01 12:00'), 'price': 105, 'type': 'HL'}, 
        {'time': pd.Timestamp('2023-01-01 13:00'), 'price': 115, 'type': 'HH'}, 
        {'time': pd.Timestamp('2023-01-01 14:00'), 'price': 110, 'type': 'HL'}
    ]
    print(f"Точки (trend_defining): {[p['type'] for p in structure_up_corr]}")
    print(f"Контекст: {determine_overall_market_context(structure_up_corr)}")
    # Ожидаем: LONG (Тренд вверх: коррекция HL после HH)

    # Пример 3: BOS вверх - HH пробивает предыдущий LH (случай пользователя)
    print("\n--- Пример 3: BOS вверх - HH пробивает предыдущий LH (случай пользователя) ---")
    user_case_structure = [
        {'time': pd.Timestamp('2025-05-09 05:00:00+00:00'), 'price': 1.12116, 'type': 'LL'},
        {'time': pd.Timestamp('2025-05-09 08:00:00+00:00'), 'price': 1.12336, 'type': 'LH'}, 
        {'time': pd.Timestamp('2025-05-10 00:00:00+00:00'), 'price': 1.12933, 'type': 'HH'} 
    ]
    print(f"Точки (trend_defining): {[p['type'] for p in user_case_structure]}")
    print(f"Контекст: {determine_overall_market_context(user_case_structure)}")
    # Ожидаем: LONG (BOS: HH пробил предыдущий LH)

    # Пример 4: Нисходящий тренд (LH -> LL)
    print("\n--- Пример 4: Нисходящий тренд (LH -> LL) ---")
    structure_down = [
        {'time': pd.Timestamp('2023-01-02 12:00'), 'price': 110, 'type': 'LH'}, 
        {'time': pd.Timestamp('2023-01-02 13:00'), 'price': 100, 'type': 'LL'}
    ]
    print(f"Точки (trend_defining): {[p['type'] for p in structure_down]}")
    print(f"Контекст: {determine_overall_market_context(structure_down)}")
    # Ожидаем: SHORT (Тренд вниз: LL после LH)

    # Пример 5: BOS вниз - LL пробивает предыдущий HL
    print("\n--- Пример 5: BOS вниз - LL пробивает предыдущий HL ---")
    structure_bos_down_hl_break = [
        {'time': pd.Timestamp('2023-01-02 11:00'), 'price': 115, 'type': 'HH'},
        {'time': pd.Timestamp('2023-01-02 12:00'), 'price': 112, 'type': 'HL'}, 
        {'time': pd.Timestamp('2023-01-02 13:00'), 'price': 100, 'type': 'LL'}
    ]
    print(f"Точки (trend_defining): {[p['type'] for p in structure_bos_down_hl_break]}")
    print(f"Контекст: {determine_overall_market_context(structure_bos_down_hl_break)}")
    # Ожидаем: SHORT (BOS: LL пробил предыдущий HL)

    # Пример 6: Консолидация (HL -> LH)
    print("\n--- Пример 6: Консолидация (HL -> LH) ---")
    structure_range_hl_lh = [
        {'time': pd.Timestamp('2023-01-03 10:00'), 'price': 100, 'type': 'LL'},
        {'time': pd.Timestamp('2023-01-03 11:00'), 'price': 105, 'type': 'HL'}, 
        {'time': pd.Timestamp('2023-01-03 12:00'), 'price': 102, 'type': 'LH'}
    ]
    print(f"Точки (trend_defining): {[p['type'] for p in structure_range_hl_lh]}")
    print(f"Контекст: {determine_overall_market_context(structure_range_hl_lh)}") 
    # Ожидаем: NEUTRAL/RANGING (Сужение/консолидация)

    # Пример 7: Только один HH в трендовой структуре
    print("\n--- Пример 7: Только один HH в трендовой структуре ---")
    structure_one_hh = [
        {'time': pd.Timestamp('2023-01-04 10:00'), 'price': 120, 'type': 'HH'}
    ]
    print(f"Точки (trend_defining): {[p['type'] for p in structure_one_hh]}")
    print(f"Контекст: {determine_overall_market_context(structure_one_hh)}")
    # Ожидаем: NEUTRAL (BOS вверх: HH первый в трендовой структуре, ожидание HL)

    # Пример 8: HH, но не пробивает предыдущий LH
    print("\n--- Пример 8: HH, но не пробивает предыдущий LH ---")
    structure_hh_no_break_lh = [
        {'time': pd.Timestamp('2023-01-05 10:00'), 'price': 120, 'type': 'LH'},
        {'time': pd.Timestamp('2023-01-05 11:00'), 'price': 110, 'type': 'LL'},
        {'time': pd.Timestamp('2023-01-05 12:00'), 'price': 118, 'type': 'HH'} # HH ниже предыдущего LH
    ]
    print(f"Точки (trend_defining): {[p['type'] for p in structure_hh_no_break_lh]}")
    print(f"Контекст: {determine_overall_market_context(structure_hh_no_break_lh)}")
    # Ожидаем: NEUTRAL (HH не пробил ключевой LH, ожидание HL/дальнейшего BOS)

    # Пример 9: HH без предшествующих LH (например, после LL)
    print("\n--- Пример 9: HH без предшествующих LH (например, после LL) ---")
    structure_hh_after_ll = [
        {'time': pd.Timestamp('2023-01-06 10:00'), 'price': 110, 'type': 'LL'},
        {'time': pd.Timestamp('2023-01-06 11:00'), 'price': 115, 'type': 'HH'}
    ]
    print(f"Точки (trend_defining): {[p['type'] for p in structure_hh_after_ll]}")
    print(f"Контекст: {determine_overall_market_context(structure_hh_after_ll)}")
    # Ожидаем: NEUTRAL (BOS вверх: HH без пробития предшествующего LH в структуре, ожидание HL)
    
    # Пример 10: Нет трендовых точек
    print("\n--- Пример 10: Нет трендовых точек ---")
    structure_no_trend_points = [
        {'time': pd.Timestamp('2023-01-07 10:00'), 'price': 100, 'type': 'L'},
        {'time': pd.Timestamp('2023-01-07 11:00'), 'price': 101, 'type': 'H'}
    ]
    print(f"Точки (все): {[p['type'] for p in structure_no_trend_points]}")
    print(f"Контекст: {determine_overall_market_context(structure_no_trend_points)}")
    # Ожидаем: NEUTRAL/RANGING (нет трендовых точек HH/HL/LH/LL)

