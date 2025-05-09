# bot/strategy/context_analyzer_1h.py
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
    
    print(f"context_analyzer: Поиск свингов с n={n} на {len(df)} свечах.")
    if not isinstance(df, pd.DataFrame) or df.empty:
        print(f"context_analyzer: Входной DataFrame пуст или не является DataFrame.")
        return swing_highs, swing_lows
        
    if len(df) < (2 * n + 1):
        print(f"context_analyzer: Недостаточно данных ({len(df)} свечей) для определения свингов с n={n}. Требуется как минимум {2*n+1}.")
        return swing_highs, swing_lows

    # Проверка наличия необходимых колонок
    required_cols = ['high', 'low']
    if not all(col in df.columns for col in required_cols):
        print(f"context_analyzer: DataFrame должен содержать колонки {required_cols}.")
        return swing_highs, swing_lows

    # Используем .values для потенциального ускорения доступа к данным pandas Series
    high_prices = df['high'].values
    low_prices = df['low'].values
    datetimes = df.index 

    for i in range(n, len(df) - n):
        # Проверка на Swing High
        is_swing_high = True
        current_high = high_prices[i]
        for j in range(1, n + 1):
            if current_high <= high_prices[i-j] or current_high <= high_prices[i+j]:
                is_swing_high = False
                break
        if is_swing_high:
            swing_highs.append({'time': datetimes[i], 'price': current_high})

        # Проверка на Swing Low
        is_swing_low = True
        current_low = low_prices[i]
        for j in range(1, n + 1):
            if current_low >= low_prices[i-j] or current_low >= low_prices[i+j]:
                is_swing_low = False
                break
        if is_swing_low:
            swing_lows.append({'time': datetimes[i], 'price': current_low})
            
    print(f"context_analyzer: Найдено Swing Highs: {len(swing_highs)}, Swing Lows: {len(swing_lows)}")
    return swing_highs, swing_lows

def analyze_market_structure_points(swing_highs: list, swing_lows: list):
    """
    Анализирует последовательность свингов для определения HH, HL, LH, LL.
    Это упрощенная версия, которая помечает свинги относительно предыдущих подтвержденных свингов того же типа.

    Args:
        swing_highs (list): Список словарей swing high.
        swing_lows (list): Список словарей swing low.

    Returns:
        list: Список точек структуры: [{'time': datetime, 'price': float, 'type': str ('HH', 'HL', 'LH', 'LL', 'H', 'L')}]
              Отсортированный по времени.
    """
    structure_points = []
    if not swing_highs and not swing_lows:
        print("context_analyzer: Нет свингов для анализа структуры (swing_highs и swing_lows пусты).")
        return structure_points

    # Объединяем и сортируем все свинги по времени
    all_swings = []
    for sh in swing_highs:
        all_swings.append({'time': sh['time'], 'price': sh['price'], 'swing_type': 'high'})
    for sl in swing_lows:
        all_swings.append({'time': sl['time'], 'price': sl['price'], 'swing_type': 'low'})
    
    if not all_swings:
        print("context_analyzer: Список all_swings пуст после объединения.")
        return structure_points

    all_swings.sort(key=lambda x: x['time'])

    # Инициализация переменных для отслеживания последних подтвержденных экстремумов
    # Эти переменные будут хранить цены последних H, L, HH, HL, LH, LL
    # Для определения HH/HL/LH/LL нам нужно сравнивать текущий свинг с предыдущим *значимым* свингом того же типа или противоположного.
    
    # Упрощенный подход: помечаем каждый свинг как H или L,
    # а затем пытаемся классифицировать их как HH, HL, LH, LL на основе предыдущего H или L.
    
    last_h = None # {'time': ..., 'price': ...}
    last_l = None # {'time': ..., 'price': ...}

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
                else: # Равный максимум
                    point_type_determined = "H" # Можно пометить как "EqualH" для большей детализации
            else: # Первый максимум в последовательности
                point_type_determined = "H"
            last_h = {'time': current_time, 'price': current_price} # Обновляем последний H
            
        elif current_swing_type == 'low':
            if last_l:
                if current_price < last_l['price']:
                    point_type_determined = "LL"
                elif current_price > last_l['price']:
                    point_type_determined = "HL"
                else: # Равный минимум
                    point_type_determined = "L" # Можно пометить как "EqualL"
            else: # Первый минимум
                point_type_determined = "L"
            last_l = {'time': current_time, 'price': current_price} # Обновляем последний L

        if point_type_determined:
            structure_points.append({
                'time': current_time, 
                'price': current_price, 
                'type': point_type_determined
            })

    # Дополнительная логика для уточнения HL и LH может быть нужна.
    # Например, HL должен формироваться после H и быть выше предыдущего L.
    # LH должен формироваться после L и быть ниже предыдущего H.
    # Текущий алгоритм более прямолинеен.

    # Фильтрация для удаления последовательных одинаковых базовых свингов (H, H или L, L),
    # если они не являются частью структуры HH/HL/LH/LL.
    # Например, если есть H, а за ним HH, это нормально. Но если H, а за ним еще один H (не LH, не HH), это может быть избыточно.
    if not structure_points:
        return []

    final_structure_points = []
    if structure_points:
        final_structure_points.append(structure_points[0])
        for i in range(1, len(structure_points)):
            current_sp = structure_points[i]
            prev_sp = final_structure_points[-1]

            # Не добавляем, если это тот же тип точки (H/L) с той же ценой (или очень близкой)
            # и предыдущая точка не была противоположным базовым свингом.
            is_same_basic_type = current_sp['type'] in ['H', 'L'] and current_sp['type'] == prev_sp['type']
            is_same_price = abs(current_sp['price'] - prev_sp['price']) < 1e-9 # Допуск на сравнение float

            if is_same_basic_type and is_same_price:
                # Если цены и базовые типы одинаковы, пропускаем дубликат
                # Это может случиться, если, например, n в find_swing_points маловат
                # и два соседних бара помечаются как H с одинаковой ценой.
                continue
            
            # Логика для замены H на HH/LH или L на LL/HL если они следуют сразу и цена соответствует
            if prev_sp['type'] == 'H' and current_sp['type'] in ['HH', 'LH'] and current_sp['time'] == prev_sp['time']: # Маловероятно, но на всякий случай
                final_structure_points[-1] = current_sp # Заменяем
                continue
            if prev_sp['type'] == 'L' and current_sp['type'] in ['LL', 'HL'] and current_sp['time'] == prev_sp['time']:
                final_structure_points[-1] = current_sp # Заменяем
                continue

            final_structure_points.append(current_sp)
            
    print(f"context_analyzer: Определено точек структуры (после фильтрации): {len(final_structure_points)}")
    return final_structure_points


def determine_overall_market_context(structure_points: list):
    """
    Определяет общий рыночный контекст (LONG, SHORT, NEUTRAL)
    на основе последних нескольких точек структуры.

    Args:
        structure_points (list): Список точек структуры, отсортированный по времени.

    Returns:
        str: "LONG", "SHORT", или "NEUTRAL/RANGING"
    """
    if not structure_points or len(structure_points) < 2:
        print("context_analyzer: Недостаточно точек структуры для определения контекста.")
        return "NEUTRAL/RANGING (мало данных)"

    # Анализируем последние 2-4 значащие точки (HH, HL, LH, LL)
    # Сначала отфильтруем только HH, HL, LH, LL для основного анализа тренда
    trend_defining_points = [p for p in structure_points if p['type'] in ['HH', 'HL', 'LH', 'LL']]
    
    if len(trend_defining_points) < 2:
        # Если нет хотя бы двух трендовых точек, смотрим на последние H и L
        last_h = next((p for p in reversed(structure_points) if p['type'] == 'H'), None)
        last_l = next((p for p in reversed(structure_points) if p['type'] == 'L'), None)
        if last_h and last_l:
            if last_h['time'] > last_l['time'] and last_h['price'] > last_l['price']: # H после L и выше
                return "NEUTRAL/RANGING (возможно начало восходящего движения)"
            if last_l['time'] > last_h['time'] and last_l['price'] < last_h['price']: # L после H и ниже
                return "NEUTRAL/RANGING (возможно начало нисходящего движения)"
        return "NEUTRAL/RANGING (нет явной структуры HH/HL/LH/LL)"

    relevant_points = trend_defining_points[-4:] # Берем до 4 последних трендовых точек
    
    last_point = relevant_points[-1]
    second_last_point = relevant_points[-2] if len(relevant_points) >= 2 else None

    context = "NEUTRAL/RANGING"

    # Классический восходящий тренд: HL за которым следует HH
    if last_point['type'] == 'HH' and second_last_point and second_last_point['type'] == 'HL':
        # Убедимся, что HH действительно выше предыдущего H (если он есть в структуре)
        # и HL выше предыдущего L. Это уже должно быть заложено в определении HH/HL.
        context = "LONG"
    # Классический нисходящий тренд: LH за которым следует LL
    elif last_point['type'] == 'LL' and second_last_point and second_last_point['type'] == 'LH':
        context = "SHORT"
    # Случаи продолжения тренда или начала коррекции
    elif last_point['type'] == 'HL': # Последняя точка - Higher Low
        # Если перед HL был HH, это подтверждение восходящего тренда
        if second_last_point and second_last_point['type'] == 'HH':
            context = "LONG (HL после HH)"
        else: # HL без недавнего HH, возможно, формируется база
            context = "NEUTRAL/RANGING (HL формируется, ожидание HH)"
    elif last_point['type'] == 'LH': # Последняя точка - Lower High
        # Если перед LH был LL, это подтверждение нисходящего тренда
        if second_last_point and second_last_point['type'] == 'LL':
            context = "SHORT (LH после LL)"
        else: # LH без недавнего LL
            context = "NEUTRAL/RANGING (LH формируется, ожидание LL)"
    # Если последние точки HH без HL или LL без LH (начало импульса)
    elif last_point['type'] == 'HH' and (not second_last_point or second_last_point['type'] not in ['HL']):
        context = "LONG (импульс вверх, ожидание HL)"
    elif last_point['type'] == 'LL' and (not second_last_point or second_last_point['type'] not in ['LH']):
        context = "SHORT (импульс вниз, ожидание LH)"

    # Дополнительная проверка на смешанные сигналы
    if context == "NEUTRAL/RANGING" and len(relevant_points) >= 2:
        # Пример: HH, а затем LL (пробой структуры)
        if (relevant_points[-1]['type'] == 'LL' and relevant_points[-2]['type'] == 'HH') or \
           (relevant_points[-1]['type'] == 'HH' and relevant_points[-2]['type'] == 'LL'):
            context = "NEUTRAL/RANGING (пробой структуры/неопределенность)"
        # Пример: HL, а затем LH
        elif (relevant_points[-1]['type'] == 'LH' and relevant_points[-2]['type'] == 'HL') or \
             (relevant_points[-1]['type'] == 'HL' and relevant_points[-2]['type'] == 'LH'):
            context = "NEUTRAL/RANGING (сужение/консолидация)"


    print(f"context_analyzer: Определен общий рыночный контекст: {context}")
    return context

if __name__ == '__main__':
    # Пример использования для тестирования этого модуля
    # python -m bot.strategy.context_analyzer_1h
    # (потребуется создать тестовый DataFrame)
    print("Тестирование context_analyzer_1h.py...")
    
    # Создание тестового DataFrame
    data = {
        'datetime': pd.to_datetime([
            '2023-01-01 10:00', '2023-01-01 11:00', '2023-01-01 12:00', '2023-01-01 13:00', 
            '2023-01-01 14:00', '2023-01-01 15:00', '2023-01-01 16:00', '2023-01-01 17:00',
            '2023-01-01 18:00', '2023-01-01 19:00', '2023-01-01 20:00', '2023-01-01 21:00'
        ]),
        'open':  [10, 12, 11, 13, 15, 14, 16, 18, 17, 19, 21, 20],
        'high':  [12, 13, 13, 15, 16, 16, 18, 19, 19, 21, 22, 22],
        'low':   [9,  10, 10, 12, 14, 13, 15, 16, 16, 18, 20, 19],
        'close': [11, 11, 12, 14, 14, 15, 17, 17, 18, 20, 20, 21]
    }
    test_df = pd.DataFrame(data).set_index('datetime')
    print("\nТестовый DataFrame:")
    print(test_df)

    # Тестирование find_swing_points
    # settings.SWING_POINT_N должен быть доступен, если configs.settings загружен
    # Для автономного теста можно задать n напрямую:
    n_test = 2 # Используем n=2 для 5-свечного паттерна, как в настройках
    print(f"\nТестирование find_swing_points с n={n_test}...")
    sw_highs, sw_lows = find_swing_points(test_df, n=n_test)
    print("Swing Highs:")
    for sh in sw_highs: print(sh)
    print("Swing Lows:")
    for sl in sw_lows: print(sl)

    # Тестирование analyze_market_structure_points
    print("\nТестирование analyze_market_structure_points...")
    structure = analyze_market_structure_points(sw_highs, sw_lows)
    print("Точки структуры:")
    for sp in structure: print(sp)

    # Тестирование determine_overall_market_context
    print("\nТестирование determine_overall_market_context...")
    context = determine_overall_market_context(structure)
    print(f"Общий контекст: {context}")

    # Пример нисходящего тренда
    data_down = {
        'datetime': pd.to_datetime([
            '2023-01-02 10:00', '2023-01-02 11:00', '2023-01-02 12:00', '2023-01-02 13:00', 
            '2023-01-02 14:00', '2023-01-02 15:00', '2023-01-02 16:00', '2023-01-02 17:00',
            '2023-01-02 18:00', '2023-01-02 19:00', '2023-01-02 20:00', '2023-01-02 21:00'
        ]),
        'open':  [20, 18, 19, 17, 15, 16, 14, 12, 13, 11, 9, 10],
        'high':  [21, 20, 20, 18, 17, 17, 15, 14, 14, 12, 11, 11],
        'low':   [18, 17, 17, 15, 14, 14, 12, 11, 11, 9,  8, 7 ],
        'close': [19, 19, 18, 16, 16, 15, 13, 13, 12, 10, 10, 9 ]
    }
    test_df_down = pd.DataFrame(data_down).set_index('datetime')
    print("\nТестовый DataFrame (нисходящий):")
    print(test_df_down)
    sw_highs_d, sw_lows_d = find_swing_points(test_df_down, n=n_test)
    structure_d = analyze_market_structure_points(sw_highs_d, sw_lows_d)
    print("Точки структуры (нисходящий):")
    for sp in structure_d: print(sp)
    context_d = determine_overall_market_context(structure_d)
    print(f"Общий контекст (нисходящий): {context_d}")
