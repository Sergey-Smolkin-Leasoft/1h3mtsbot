# ts_logic/context_analyzer_1h.py
import pandas as pd
from configs import settings 
from datetime import time, timedelta, datetime as dt_datetime 
import numpy as np 

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
            swing_highs.append({'time': datetimes[i], 'price': current_high, 'type': 'H_SWING'})

        is_swing_low = True
        current_low = low_prices[i]
        for j in range(1, n + 1):
            if current_low >= low_prices[i-j] or current_low >= low_prices[i+j]:
                is_swing_low = False
                break
        if is_swing_low:
            swing_lows.append({'time': datetimes[i], 'price': current_low, 'type': 'L_SWING'})
    return swing_highs, swing_lows

def analyze_market_structure_points(swing_highs: list, swing_lows: list):
    """
    Анализирует последовательность свингов для определения HH, HL, LH, LL.
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
                if current_price > last_h_info['price']: point_type_determined = "HH"
                elif current_price < last_h_info['price']: point_type_determined = "LH"
                else: point_type_determined = "H" 
            else:
                point_type_determined = "H" 
            last_h_info = {'time': current_time, 'price': current_price, 'type': point_type_determined}
            if point_type_determined: temp_structure_points.append(last_h_info)
        
        elif current_swing_type == 'low':
            if last_l_info:
                if current_price < last_l_info['price']: point_type_determined = "LL"
                elif current_price > last_l_info['price']: point_type_determined = "HL"
                else: point_type_determined = "L" 
            else:
                point_type_determined = "L" 
            last_l_info = {'time': current_time, 'price': current_price, 'type': point_type_determined}
            if point_type_determined: temp_structure_points.append(last_l_info)

    if not temp_structure_points: return []
    temp_structure_points.sort(key=lambda x: x['time'])
    
    if not temp_structure_points: return []

    structure_points.append(temp_structure_points[0])
    for i in range(1, len(temp_structure_points)):
        current_sp = temp_structure_points[i]
        prev_sp = structure_points[-1]
        
        is_prev_high_type = 'H' in prev_sp['type']
        is_curr_high_type = 'H' in current_sp['type']
        is_prev_low_type = 'L' in prev_sp['type'] and not is_prev_high_type 
        is_curr_low_type = 'L' in current_sp['type'] and not is_curr_high_type

        if (is_prev_high_type and is_curr_high_type) or \
           (is_prev_low_type and is_curr_low_type):
            if (is_curr_high_type and current_sp['price'] >= prev_sp['price']) or \
               (is_curr_low_type and current_sp['price'] <= prev_sp['price']):
                structure_points[-1] = current_sp 
            elif current_sp['time'] > prev_sp['time'] and prev_sp['type'] != current_sp['type']: 
                structure_points.append(current_sp)
        else: 
            structure_points.append(current_sp)
            
    return structure_points


def determine_overall_market_context(structure_points: list):
    """
    Определяет общий рыночный контекст (LONG, SHORT, NEUTRAL)
    на основе последних нескольких точек структуры (HH, HL, LH, LL).
    """
    if not structure_points:
        return "NEUTRAL (нет данных о структуре)"

    trend_defining_points = [p for p in structure_points if p['type'] in ['HH', 'HL', 'LH', 'LL']]

    if len(trend_defining_points) < 2:
        if len(trend_defining_points) == 1:
            last_tdp_single = trend_defining_points[0]
            if last_tdp_single['type'] == 'HH': return "Потенциальный LONG (Первый HH, ожидание HL)"
            elif last_tdp_single['type'] == 'LL': return "Потенциальный SHORT (Первый LL, ожидание LH)"
        elif len(structure_points) >=2:
             p1 = structure_points[-1]
             p0 = structure_points[-2]
             if p1['type'] == 'H' and p0['type'] == 'L' and p1['price'] > p0['price']: return "NEUTRAL (L -> H)"
             if p1['type'] == 'L' and p0['type'] == 'H' and p1['price'] < p0['price']: return "NEUTRAL (H -> L)"
        return "NEUTRAL (недостаточно трендовых точек)"

    last_p = trend_defining_points[-1]
    second_last_p = trend_defining_points[-2]
    context = "NEUTRAL (неопределенная структура)"

    if last_p['type'] == 'HH' and second_last_p['type'] == 'HL':
        context = "LONG (HH после HL)"
    elif last_p['type'] == 'LL' and second_last_p['type'] == 'LH':
        context = "SHORT (LL после LH)"
    elif last_p['type'] == 'HL' and second_last_p['type'] == 'HH':
        context = "LONG (Коррекция HL после HH)"
    elif last_p['type'] == 'LH' and second_last_p['type'] == 'LL':
        context = "SHORT (Коррекция LH после LL)"
    elif last_p['type'] == 'HH': 
        prev_highs = [p for p in trend_defining_points[:-1] if p['type'] in ['LH', 'H']]
        if prev_highs and last_p['price'] > prev_highs[-1]['price']:
            context = "LONG (BOS: HH пробил LH/H)"
        else:
            context = "NEUTRAL (HH без ясного BOS)"
    elif last_p['type'] == 'LL': 
        prev_lows = [p for p in trend_defining_points[:-1] if p['type'] in ['HL', 'L']]
        if prev_lows and last_p['price'] < prev_lows[-1]['price']:
            context = "SHORT (BOS: LL пробил HL/L)"
        else:
            context = "NEUTRAL (LL без ясного BOS)"
    elif (last_p['type'] == 'LH' and second_last_p['type'] == 'HL') or \
         (last_p['type'] == 'HL' and second_last_p['type'] == 'LH'):
        context = "NEUTRAL (Рендж/Консолидация)"
        
    return context


def get_line_slope(p_start_time, p_start_price, p_end_time, p_end_price):
    """Рассчитывает наклон линии."""
    if not isinstance(p_start_time, pd.Timestamp) or not isinstance(p_end_time, pd.Timestamp):
        # print(f"DEBUG: Invalid timestamp types in get_line_slope: start={type(p_start_time)}, end={type(p_end_time)}")
        return 0 

    if p_start_time < p_end_time:
        time_delta_seconds = (p_end_time - p_start_time).total_seconds()
        price_delta = p_end_price - p_start_price
        if time_delta_seconds > 0:
            return price_delta / time_delta_seconds
        # else:
            # print(f"DEBUG: time_delta_seconds is not positive: {time_delta_seconds}")
    elif p_start_time == p_end_time: 
        # print(f"DEBUG: Timestamps are equal in get_line_slope: {p_start_time}")
        return np.inf if p_end_price > p_start_price else (-np.inf if p_end_price < p_start_price else 0) 
    # else:
        # print(f"DEBUG: p_start_time > p_end_time in get_line_slope: start={p_start_time}, end={p_end_time}")
    return 0 


def determine_trend_channel_context(trend_lines_data: list):
    """
    Определяет контекст канала на основе наклонов линий тренда.
    Возвращает строку с описанием.
    """
    if not trend_lines_data or len(trend_lines_data) < 2:
        # print(f"DEBUG determine_trend_channel_context: Not enough lines: {len(trend_lines_data)}")
        return "Неопределенный (недостаточно линий)"

    support_line = next((line for line in trend_lines_data if line.get('color') == '#26A69A'), None)
    resistance_line = next((line for line in trend_lines_data if line.get('color') == '#EF5350'), None)

    if not support_line or not resistance_line:
        # print(f"DEBUG determine_trend_channel_context: Missing support or resistance line. Support: {support_line is not None}, Resistance: {resistance_line is not None}")
        return "Неопределенный (нет линии поддержки/сопротивления)"
    
    try:
        s_start_time = pd.Timestamp(support_line['start_time'])
        s_end_time = pd.Timestamp(support_line['end_time'])
        r_start_time = pd.Timestamp(resistance_line['start_time'])
        r_end_time = pd.Timestamp(resistance_line['end_time'])
    except Exception as e:
        print(f"Ошибка конвертации времени для линий тренда: {e}")
        return "Ошибка времени в линиях"

    slope_support = get_line_slope(s_start_time, support_line['start_price'], 
                                   s_end_time, support_line['end_price'])
    slope_resistance = get_line_slope(r_start_time, resistance_line['start_price'], 
                                      r_end_time, resistance_line['end_price'])
    
    # ИЗМЕНЕНИЕ: Значительно уменьшаем slope_tolerance по умолчанию.
    # Это значение должно быть очень маленьким, чтобы линии считались плоскими.
    # Например, изменение менее чем на 0.1 пипса за 1 день.
    # 0.00001 (1 pip) / (24*3600 секунд) ~ 1e-10
    # Установим более реалистичный, но все же маленький порог.
    slope_tolerance = settings.TRENDLINE_SLOPE_TOLERANCE if hasattr(settings, 'TRENDLINE_SLOPE_TOLERANCE') else 1e-9 
    
    # print(f"DEBUG determine_trend_channel_context: slope_support={slope_support:.10f}, slope_resistance={slope_resistance:.10f}, slope_tolerance={slope_tolerance:.10f}")

    is_support_up = slope_support > slope_tolerance
    is_support_down = slope_support < -slope_tolerance
    is_support_flat = np.isclose(slope_support, 0, atol=slope_tolerance)

    is_resistance_up = slope_resistance > slope_tolerance
    is_resistance_down = slope_resistance < -slope_tolerance
    is_resistance_flat = np.isclose(slope_resistance, 0, atol=slope_tolerance)
    
    # print(f"DEBUG determine_trend_channel_context: is_support_up={is_support_up}, is_support_down={is_support_down}, is_support_flat={is_support_flat}")
    # print(f"DEBUG determine_trend_channel_context: is_resistance_up={is_resistance_up}, is_resistance_down={is_resistance_down}, is_resistance_flat={is_resistance_flat}")


    if is_support_up and is_resistance_up: return "Восходящий" 
    elif is_support_down and is_resistance_down: return "Нисходящий" 
    elif is_support_flat and is_resistance_flat: return "Горизонтальный" 
    elif is_support_up and is_resistance_flat: return "Восходящий треугольник" 
    elif is_support_flat and is_resistance_down: return "Нисходящий треугольник" 
    elif is_support_up and is_resistance_down: return "Сужающийся клин" 
    elif is_support_down and is_resistance_up: return "Расширяющаяся формация" 
    
    # print(f"DEBUG determine_trend_channel_context: Defaulting to Смешанный")
    return f"Смешанный (S:{slope_support:.2e}, R:{slope_resistance:.2e})"


def determine_trend_lines_v2(swing_highs: list, swing_lows: list, 
                             last_data_timestamp: pd.Timestamp = None, 
                             price_data_for_offset: pd.DataFrame = None, 
                             points_window_size: int = 5):
    """
    Определяет линии тренда. Линия поддержки будет параллельна линии сопротивления, если возможно.
    """
    trend_lines = []
    offset_percentage = settings.TRENDLINE_OFFSET_PERCENTAGE if hasattr(settings, 'TRENDLINE_OFFSET_PERCENTAGE') else 0.001 
    channel_height_factor = settings.CHANNEL_HEIGHT_FACTOR if hasattr(settings, 'CHANNEL_HEIGHT_FACTOR') else 2.0 
    
    avg_price_for_offset_calc = 0
    if price_data_for_offset is not None and not price_data_for_offset.empty:
        if 'high' in price_data_for_offset.columns and 'low' in price_data_for_offset.columns: 
             avg_price_for_offset_calc = (price_data_for_offset['high'].mean() + price_data_for_offset['low'].mean()) / 2
        elif 'close' in price_data_for_offset.columns:
            avg_price_for_offset_calc = price_data_for_offset['close'].mean()
        
    base_offset_amount = 0
    if avg_price_for_offset_calc > 0: 
        base_offset_amount = avg_price_for_offset_calc * offset_percentage


    if not last_data_timestamp: 
        all_swing_times = [p['time'] for p in swing_highs] + [p['time'] for p in swing_lows]
        if not all_swing_times: return trend_lines 
        last_data_timestamp = max(all_swing_times)
    
    p_start_h_resistance = None 
    slope_h_resistance = None   
    resistance_line_calculated = False
    resistance_start_price_with_offset = None 

    if len(swing_highs) >= 2:
        all_time_sorted_highs = sorted(swing_highs, key=lambda x: x['time'], reverse=True)
        recent_highs_by_time = all_time_sorted_highs[:points_window_size]
        
        if len(recent_highs_by_time) >= 2:
            recent_highs_by_time.sort(key=lambda x: x['price'], reverse=True) 
            points_for_line_high = sorted(recent_highs_by_time[:2], key=lambda x: x['time']) 
            
            p_start_h_resistance = points_for_line_high[0] 
            p_end_h_resistance = points_for_line_high[1]

            start_price_orig_h = p_start_h_resistance['price']
            end_price_orig_h = p_end_h_resistance['price']
            
            final_projected_price_h = end_price_orig_h 
            if p_start_h_resistance['time'] < p_end_h_resistance['time']: 
                slope_h_resistance = get_line_slope(p_start_h_resistance['time'], start_price_orig_h, p_end_h_resistance['time'], end_price_orig_h)
                if slope_h_resistance is not None: 
                    time_delta_to_project_h = (last_data_timestamp - p_start_h_resistance['time']).total_seconds()
                    final_projected_price_h = start_price_orig_h + slope_h_resistance * time_delta_to_project_h
            
            resistance_start_price_with_offset = start_price_orig_h + base_offset_amount 
            final_projected_price_offset_h = final_projected_price_h + base_offset_amount

            if p_start_h_resistance['time'] < last_data_timestamp: 
                trend_lines.append({
                    'start_time': p_start_h_resistance['time'], 'start_price': resistance_start_price_with_offset,
                    'end_time': last_data_timestamp, 'end_price': final_projected_price_offset_h,
                    'color': '#EF5350', 'lineStyle': LINE_STYLE_SOLID 
                })
                resistance_line_calculated = True

    support_line_calculated_parallel = False 
    
    if resistance_line_calculated and slope_h_resistance is not None and p_start_h_resistance is not None and resistance_start_price_with_offset is not None:
        parallel_support_start_price = resistance_start_price_with_offset - (channel_height_factor * base_offset_amount)
        p_start_l_parallel_time = p_start_h_resistance['time']
        
        time_delta_to_project_l_parallel = (last_data_timestamp - p_start_l_parallel_time).total_seconds()
        final_projected_price_l_parallel = parallel_support_start_price + slope_h_resistance * time_delta_to_project_l_parallel
        
        actual_low_near_start = None
        if swing_lows:
            candidate_lows = [sl for sl in swing_lows if sl['time'] <= p_start_l_parallel_time]
            if candidate_lows:
                candidate_lows.sort(key=lambda x: (x['time'], x['price']), reverse=True) 
                actual_low_near_start = candidate_lows[0]['price'] 

        if p_start_l_parallel_time < last_data_timestamp:
            trend_lines.append({
                'start_time': p_start_l_parallel_time, 'start_price': parallel_support_start_price,
                'end_time': last_data_timestamp, 'end_price': final_projected_price_l_parallel,
                'color': '#26A69A', 'lineStyle': LINE_STYLE_SOLID 
            })
            support_line_calculated_parallel = True
            
    if not support_line_calculated_parallel and len(swing_lows) >= 2: 
        all_time_sorted_lows_fallback = sorted(swing_lows, key=lambda x: x['time'], reverse=True)
        recent_lows_by_time_fallback = all_time_sorted_lows_fallback[:points_window_size]
        
        if len(recent_lows_by_time_fallback) >= 2:
            recent_lows_by_time_fallback.sort(key=lambda x: x['price']) 
            points_for_line_low_fallback = sorted(recent_lows_by_time_fallback[:2], key=lambda x: x['time'])
            
            p_start_l_fb = points_for_line_low_fallback[0]
            p_end_l_fb = points_for_line_low_fallback[1]

            start_price_orig_l_fb = p_start_l_fb['price']
            end_price_orig_l_fb = p_end_l_fb['price']

            final_projected_price_l_fb = end_price_orig_l_fb
            if p_start_l_fb['time'] < p_end_l_fb['time']:
                slope_l_fb = get_line_slope(p_start_l_fb['time'], start_price_orig_l_fb, p_end_l_fb['time'], end_price_orig_l_fb)
                if slope_l_fb is not None:
                    time_delta_to_project_l_fb = (last_data_timestamp - p_start_l_fb['time']).total_seconds()
                    final_projected_price_l_fb = start_price_orig_l_fb + slope_l_fb * time_delta_to_project_l_fb
            
            start_price_offset_l_fb = start_price_orig_l_fb - base_offset_amount 
            final_projected_price_offset_l_fb = final_projected_price_l_fb - base_offset_amount

            if p_start_l_fb['time'] < last_data_timestamp:
                trend_lines.append({
                    'start_time': p_start_l_fb['time'], 'start_price': start_price_offset_l_fb,
                    'end_time': last_data_timestamp, 'end_price': final_projected_price_offset_l_fb,
                    'color': '#26A69A', 'lineStyle': LINE_STYLE_SOLID 
                })

    return trend_lines


def summarize_analysis(market_data_df: pd.DataFrame, structure_points: list, 
                       session_fractal_and_setup_points: list, overall_context: str, 
                       trend_lines_data: list = None):
    """
    Формирует текстовую сводку анализа, содержащую Market Structure и Trend Lines.
    Возвращает список словарей для отображения на фронтенде.
    """
    context_items = []

    # 1. Market Structure
    market_structure_description = f"Market Structure: {overall_context if overall_context else 'Не определена'}"
    market_structure_status = True 
    if not overall_context or "NEUTRAL" in overall_context or "нет данных" in overall_context or "недостаточно" in overall_context or "неопределенная" in overall_context :
        market_structure_status = False
        if not overall_context or "нет данных" in overall_context:
             market_structure_description = "Market Structure: Не определена (нет данных)"


    context_items.append({
        'description': market_structure_description, 
        'status': market_structure_status 
    })

    # 2. Trend Lines
    trend_lines_description = "Trend Lines: "
    trend_lines_status = False 
    
    if trend_lines_data and len(trend_lines_data) >= 2: 
        channel_context_text = determine_trend_channel_context(trend_lines_data)
        trend_lines_description += channel_context_text
        if channel_context_text and \
           "Неопределенный" not in channel_context_text and \
           "Смешанный" not in channel_context_text and \
           "Ошибка" not in channel_context_text:
            trend_lines_status = True
    elif trend_lines_data and len(trend_lines_data) == 1:
        trend_lines_description += "Построена одна линия тренда" 
    else:
        trend_lines_description += "Линии не построены или не определены"
    
    context_items.append({
        'description': trend_lines_description,
        'status': trend_lines_status
    })
    
    return context_items


if __name__ == '__main__':
    print("Тестирование context_analyzer_1h.py...")
    settings.SWING_POINT_N = 2 
    settings.TRENDLINE_POINTS_WINDOW_SIZE = 5 
    settings.TRENDLINE_OFFSET_PERCENTAGE = 0.0005 
    settings.CHANNEL_HEIGHT_FACTOR = 1.5 
    # ИЗМЕНЕНИЕ: Устанавливаем очень маленький TRENDLINE_SLOPE_TOLERANCE для теста
    settings.TRENDLINE_SLOPE_TOLERANCE = 1e-9 

    times = pd.to_datetime([
        '2023-01-01 00:00', '2023-01-01 01:00', '2023-01-01 02:00', '2023-01-01 03:00', '2023-01-01 04:00', 
        '2023-01-01 05:00', '2023-01-01 06:00', '2023-01-01 07:00', '2023-01-01 08:00', '2023-01-01 09:00',
        '2023-01-01 10:00', '2023-01-01 11:00', '2023-01-01 12:00', '2023-01-01 13:00', '2023-01-01 14:00'
    ], utc=True)
    
    data_dict = { # Данные для нисходящего тренда
        'high':  [1.1050, 1.1045, 1.1040, 1.1030, 1.1025, 1.1020, 1.1010, 1.1000, 1.0995, 1.0985, 1.0980, 1.0970, 1.0960, 1.0950, 1.0940],
        'low':   [1.1020, 1.1015, 1.1010, 1.1000, 1.0995, 1.0990, 1.0980, 1.0970, 1.0965, 1.0955, 1.0950, 1.0940, 1.0930, 1.0920, 1.0910],
        'close': [1.1030, 1.1025, 1.1020, 1.1010, 1.1005, 1.1000, 1.0990, 1.0980, 1.0975, 1.0965, 1.0960, 1.0950, 1.0940, 1.0930, 1.0920],
        'open':  [1.1040, 1.1035, 1.1030, 1.1020, 1.1015, 1.1010, 1.1000, 1.0990, 1.0985, 1.0975, 1.0970, 1.0960, 1.0950, 1.0940, 1.0930],
    }
    test_df = pd.DataFrame(data_dict, index=times)
    test_df['volume'] = 100 

    print(f"\nТестирование с SWING_POINT_N = {settings.SWING_POINT_N}")
    sw_h, sw_l = find_swing_points(test_df, n=settings.SWING_POINT_N)
    print(f"Найдено свингов: Highs={len(sw_h)}, Lows={len(sw_l)}")

    struct_pts = analyze_market_structure_points(sw_h, sw_l) 
    overall_ctx = determine_overall_market_context(struct_pts) 
    print(f"\nОбщий контекст структуры: {overall_ctx}")

    last_ts_for_lines = test_df.index[-1] if not test_df.empty else None
    trend_lines_for_summary = []
    if last_ts_for_lines:
        trend_lines_for_summary = determine_trend_lines_v2(
            sw_h, sw_l, 
            last_ts_for_lines, 
            test_df[['high', 'low', 'close']], 
            points_window_size=settings.TRENDLINE_POINTS_WINDOW_SIZE
        ) 
        print(f"\nЛинии тренда (v2, окно={settings.TRENDLINE_POINTS_WINDOW_SIZE}): {len(trend_lines_for_summary)}")
        for tl_idx, tl_val in enumerate(trend_lines_for_summary):
            print(f"  Линия {tl_idx+1}: {pd.Timestamp(tl_val['start_time']).strftime('%Y-%m-%d %H:%M')} ({tl_val['start_price']:.5f}) -> {pd.Timestamp(tl_val['end_time']).strftime('%Y-%m-%d %H:%M')} ({tl_val['end_price']:.5f}) Цвет: {tl_val['color']}")
    else:
        print("\nНе удалось определить last_ts_for_lines для теста determine_trend_lines_v2.")

    summary_items = summarize_analysis(test_df, struct_pts, [], overall_ctx, trend_lines_for_summary) 
    print("\nСводка анализа (только Context items):")
    if summary_items:
        for item_idx, item_val in enumerate(summary_items):
            print(f"  {item_idx}: {item_val['description']} (Статус: {'✓' if item_val.get('status') else '✗'})")
    else:
        print("  Нет данных для сводки.")

