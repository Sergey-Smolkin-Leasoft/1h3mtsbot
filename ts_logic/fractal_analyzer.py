# ts_logic/fractal_analyzer.py
import pandas as pd
from datetime import time, timedelta, datetime as dt_datetime
from configs import settings
from ts_logic.context_analyzer_1h import find_swing_points # find_swing_points теперь будет вызываться с разным N

def get_candles_for_session(df: pd.DataFrame, target_date: pd.Timestamp, 
                            session_start_time: time, session_end_time: time) -> pd.DataFrame:
    """
    Фильтрует DataFrame для получения свечей, попадающих в указанную сессию на указанную дату.
    """
    if df.empty:
        return pd.DataFrame()

    if not isinstance(df.index, pd.DatetimeIndex):
        return pd.DataFrame()
        
    start_datetime = pd.Timestamp.combine(target_date.date(), session_start_time).tz_localize(df.index.tz)
    end_datetime = pd.Timestamp.combine(target_date.date(), session_end_time).tz_localize(df.index.tz)

    # Обработка сессий, которые пересекают полночь (например, с 22:00 до 02:00)
    # В данном случае азиатская (00-09) и НЙ (13-22) не пересекают, но общая логика полезна
    if session_end_time < session_start_time: 
        # Это означает, что сессия переходит на следующий день (относительно start_datetime)
        # Однако, для get_candles_for_session мы всегда работаем в рамках ОДНОЙ target_date.
        # Поэтому, если session_end_time < session_start_time, это обычно ошибка в определении сессии
        # или требует более сложной логики, если сессия действительно так определена.
        # Для стандартных Азии/НЙ это не актуально.
        # Оставим текущую логику, которая предполагает, что сессия в рамках одного дня
        # или between_time корректно обработает это для одного дня.
        day_candles = df[df.index.date == target_date.date()]
        if day_candles.empty:
            return pd.DataFrame()
        # between_time хорошо работает для случаев внутри одного дня
        session_candles = day_candles.between_time(session_start_time, session_end_time, include_start=True, include_end=True)
    else: 
        session_candles = df.loc[start_datetime:end_datetime]
    return session_candles


def get_session_fractals(candles: pd.DataFrame, n_swing_for_session: int, session_tag: str, point_type_suffix: str) -> list:
    """
    Находит фракталы (свинги) на предоставленных свечах и помечает их тегом сессии.
    Использует n_swing_for_session для определения чувствительности фрактала.
    """
    fractals = []
    # Для определения свинга нужно как минимум (2 * n + 1) свечей
    if candles.empty or len(candles) < (2 * n_swing_for_session + 1) :
        # print(f"get_session_fractals: Недостаточно свечей ({len(candles)}) в сессии {session_tag} для n={n_swing_for_session}. Требуется {2*n_swing_for_session+1}.")
        return fractals

    # ВАЖНО: передаем n_swing_for_session в find_swing_points
    swing_highs, swing_lows = find_swing_points(candles, n=n_swing_for_session)

    for sh in swing_highs:
        fractals.append({'time': sh['time'], 'price': sh['price'], 'type': f'F_H{point_type_suffix}', 'session': session_tag})
    for sl in swing_lows:
        fractals.append({'time': sl['time'], 'price': sl['price'], 'type': f'F_L{point_type_suffix}', 'session': session_tag})
    return fractals

def analyze_fractal_setups(full_df: pd.DataFrame, current_processing_dt: dt_datetime):
    """
    Основная функция для анализа фракталов сессий и поиска сетапов.
    """
    all_identified_fractals = [] 
    setup_points = []            

    asian_start_time = time(settings.ASIAN_SESSION_START_HOUR_UTC, settings.ASIAN_SESSION_START_MINUTE)
    asian_end_time = time(settings.ASIAN_SESSION_END_HOUR_UTC, settings.ASIAN_SESSION_END_MINUTE)
    ny_start_time = time(settings.NY_SESSION_START_HOUR_UTC, settings.NY_SESSION_START_MINUTE)
    ny_end_time = time(settings.NY_SESSION_END_HOUR_UTC, settings.NY_SESSION_END_MINUTE)

    # Используем UTC, если в DataFrame нет таймзоны, иначе используем таймзону DataFrame
    current_tz = full_df.index.tz if hasattr(full_df.index, 'tz') and full_df.index.tz is not None else dt_datetime.now(timedelta(0)).astimezone().tzinfo # Fallback to local system's UTC offset if no tz
    if current_tz is None: # Если все еще None (маловероятно с fallback, но для безопасности)
        current_tz = timezone.utc


    today_date = pd.Timestamp(current_processing_dt.date(), tz=current_tz)

    asian_candles_today = get_candles_for_session(full_df, today_date, asian_start_time, asian_end_time)
    
    if not asian_candles_today.empty:
        # Используем settings.SESSION_FRACTAL_N для азиатских фракталов
        todays_asian_fractals = get_session_fractals(asian_candles_today, settings.SESSION_FRACTAL_N, "Asia", "_AS")
        all_identified_fractals.extend(todays_asian_fractals)
    else:
        todays_asian_fractals = []

    past_ny_fractals = []
    for i in range(1, settings.NY_SESSIONS_TO_CHECK_PREVIOUS_DAYS + 1):
        prev_date = today_date - timedelta(days=i)
        ny_candles_past = get_candles_for_session(full_df, prev_date, ny_start_time, ny_end_time)
        if not ny_candles_past.empty:
            # Используем settings.SESSION_FRACTAL_N для Нью-Йоркских фракталов
            ny_fractals_on_date = get_session_fractals(ny_candles_past, settings.SESSION_FRACTAL_N, f"NY (Day -{i})", f"_NY{i}")
            past_ny_fractals.extend(ny_fractals_on_date)
            all_identified_fractals.extend(ny_fractals_on_date)
            
    if todays_asian_fractals and past_ny_fractals:
        price_threshold = settings.FRACTAL_PROXIMITY_THRESHOLD_PIPS * settings.PIP_VALUE_DEFAULT

        for asian_f in todays_asian_fractals:
            for ny_f in past_ny_fractals:
                price_diff = abs(asian_f['price'] - ny_f['price'])

                if price_diff <= price_threshold:
                    setup_type = "UNKNOWN_SETUP"
                    asian_is_high = "F_H" in asian_f['type']
                    ny_is_high = "F_H" in ny_f['type']

                    if asian_is_high and ny_is_high:
                        setup_type = "SETUP_Resist" 
                    elif not asian_is_high and not ny_is_high: 
                        setup_type = "SETUP_Support" 
                    
                    if setup_type != "UNKNOWN_SETUP": # Добавляем только если это Resist или Support
                        setup_point = {
                            'time': asian_f['time'],
                            'price': asian_f['price'], # Цена сетапа - это цена азиатского фрактала
                            'type': setup_type,
                            'session': 'Setup', 
                            'details': f"Asian {asian_f['type']} at {asian_f['price']:.5f} ({asian_f['time'].strftime('%H:%M')}) "
                                       f"near NY {ny_f['type']} at {ny_f['price']:.5f} ({ny_f['time'].strftime('%Y-%m-%d %H:%M')}), "
                                       f"Diff: {price_diff:.5f}"
                        }
                        setup_points.append(setup_point)
                        all_identified_fractals.append(setup_point) 
                        print(f"fractal_analyzer: НАЙДЕН СЕТАП! {setup_type} в {asian_f['time'].strftime('%Y-%m-%d %H:%M')} цена {asian_f['price']:.5f}")
    
    all_identified_fractals.sort(key=lambda x: x['time'])
    return all_identified_fractals

if __name__ == '__main__':
    print("Тестирование fractal_analyzer.py (с SESSION_FRACTAL_N)...")
    
    # Устанавливаем тестовые значения для settings, если они отличаются от основных
    original_swing_n = settings.SWING_POINT_N
    original_session_n = settings.SESSION_FRACTAL_N
    settings.SWING_POINT_N = 5 # Для общего контекста (не используется напрямую в этом тесте)
    settings.SESSION_FRACTAL_N = 1 # Для сессионных фракталов в этом тесте

    rng = pd.date_range(start='2023-10-01 00:00', end='2023-10-03 23:59', freq='1H', tz='UTC')
    data = { # Данные, чтобы гарантированно были фракталы при n=1
        'open': [1.0500, 1.0510, 1.0490, 1.0520, 1.0480] * (len(rng)//5 + 1) [:len(rng)],
        'high': [1.0505, 1.0515, 1.0530, 1.0525, 1.0540] * (len(rng)//5 + 1) [:len(rng)], # Явный максимум на 3-й свече
        'low':  [1.0495, 1.0485, 1.0490, 1.0470, 1.0480] * (len(rng)//5 + 1) [:len(rng)], # Явный минимум на 4-й свече
        'close':[1.0503, 1.0500, 1.0510, 1.0490, 1.0500] * (len(rng)//5 + 1) [:len(rng)],
        'volume':[100 + i*10 for i in range(len(rng))]
    }
    test_df_full = pd.DataFrame(data, index=rng)
    
    # Убедимся, что current_processing_dt имеет таймзону
    current_time_for_test = dt_datetime(2023, 10, 3, 22, 0, 0, tzinfo=timezone.utc)
    if test_df_full.index.tz:
        current_time_for_test = current_time_for_test.astimezone(test_df_full.index.tz)


    print(f"\nТестовый DataFrame создан, свечей: {len(test_df_full)}")
    print(f"Тестирование с settings.SESSION_FRACTAL_N = {settings.SESSION_FRACTAL_N}")


    print("\nТестирование get_candles_for_session (Азия, 2023-10-03):")
    asian_s_time = time(settings.ASIAN_SESSION_START_HOUR_UTC, settings.ASIAN_SESSION_START_MINUTE)
    asian_e_time = time(settings.ASIAN_SESSION_END_HOUR_UTC, settings.ASIAN_SESSION_END_MINUTE)
    target_d_asia = pd.Timestamp(dt_datetime(2023,10,3).date(), tz=test_df_full.index.tz) # Дата для азиатской сессии
    
    asian_test_candles = get_candles_for_session(test_df_full, target_d_asia, asian_s_time, asian_e_time)
    if not asian_test_candles.empty:
        print(f"Найдено азиатских свечей для {target_d_asia.date()}: {len(asian_test_candles)}")
        # print(asian_test_candles.head(2))
        # print(asian_test_candles.tail(2))
        
        print("\nТестирование get_session_fractals (Азия, 2023-10-03):")
        asian_test_fractals = get_session_fractals(asian_test_candles, settings.SESSION_FRACTAL_N, "AsiaTest", "_AST")
        print(f"Найдено азиатских фракталов: {len(asian_test_fractals)}")
        for f_idx, f_val in enumerate(asian_test_fractals): print(f"  {f_idx}: {f_val}")
    else:
        print(f"Азиатские свечи не найдены для {target_d_asia.date()}.")


    print("\nТестирование analyze_fractal_setups...")
    # Увеличим порог для теста, чтобы точно найти сетапы, если фракталы близки
    original_threshold = settings.FRACTAL_PROXIMITY_THRESHOLD_PIPS
    settings.FRACTAL_PROXIMITY_THRESHOLD_PIPS = 50 # 50 пипсов
    
    all_fractals_and_setups = analyze_fractal_setups(test_df_full, current_time_for_test)
    
    print("\nВсе идентифицированные фракталы и сетапы для графика:")
    if all_fractals_and_setups:
        for p_idx, p_val in enumerate(all_fractals_and_setups):
            details_str = f" - {p_val['details']}" if 'details' in p_val else ""
            print(f"  {p_idx}: Время: {p_val['time']}, Цена: {p_val['price']:.5f}, Тип: {p_val['type']}, Сессия: {p_val['session']}{details_str}")
    else:
        print("  Ничего не найдено.")
        
    # Возвращаем оригинальные значения
    settings.SWING_POINT_N = original_swing_n
    settings.SESSION_FRACTAL_N = original_session_n
    settings.FRACTAL_PROXIMITY_THRESHOLD_PIPS = original_threshold
