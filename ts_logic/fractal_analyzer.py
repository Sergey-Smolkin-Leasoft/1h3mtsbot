# ts_logic/fractal_analyzer.py
import pandas as pd
from datetime import time, timedelta, datetime as dt_datetime, timezone
from configs import settings
from ts_logic.context_analyzer_1h import find_swing_points # find_swing_points теперь будет вызываться с разным N

def get_candles_for_session(df: pd.DataFrame, target_date: pd.Timestamp,
                            session_start_time: time, session_end_time: time) -> pd.DataFrame:
    """
    Фильтрует DataFrame для получения свечей, попадающих в указанную сессию на указанную дату.
    Принимает target_date как pd.Timestamp (может быть tz-aware или naive).
    """
    if df.empty:
        return pd.DataFrame()

    if not isinstance(df.index, pd.DatetimeIndex):
        return pd.DataFrame()

    # Ensure target_date is timezone-aware for comparison, using the DataFrame's timezone
    # or UTC as a fallback. Create a timezone-naive Timestamp from the date first.
    current_tz = df.index.tz if hasattr(df.index, 'tz') and df.index.tz is not None else timezone.utc
    # Create a timezone-naive Timestamp from the date part before localizing
    target_date_localized = pd.Timestamp(target_date.date()).tz_localize(current_tz)


    start_datetime = pd.Timestamp.combine(target_date_localized.date(), session_start_time).tz_localize(current_tz)
    end_datetime = pd.Timestamp.combine(target_date_localized.date(), session_end_time).tz_localize(current_tz)


    # Обработка сессий, которые пересекают полночь (например, с 22:00 до 02:00 UTC)
    # between_time in Pandas works correctly for DatetimeIndex with timezone,
    # even if the end time is less than the start time, it correctly handles the next day transition.
    # MODIFIED: Removed include_start and include_end arguments
    session_candles = df.between_time(session_start_time, session_end_time)

    # Additional filtering by date to ensure we only take candles for the target_date
    # (or crossing midnight within the correct date range)
    # For sessions crossing midnight (start_time > end_time), we need to consider candles from target_date and target_date + 1 day
    if session_start_time > session_end_time:
         next_day_date_localized = target_date_localized + timedelta(days=1)
         # Candles at the end of target_date (after start_time) AND candles at the start of next_day_date (before end_time)
         candles_end_of_day = df.loc[pd.Timestamp.combine(target_date_localized.date(), session_start_time).tz_localize(current_tz): pd.Timestamp.combine(target_date_localized.date(), time(23, 59, 59)).tz_localize(current_tz)]
         candles_start_of_next_day = df.loc[pd.Timestamp.combine(next_day_date_localized.date(), time(0, 0, 0)).tz_localize(current_tz) : pd.Timestamp.combine(next_day_date_localized.date(), session_end_time).tz_localize(current_tz)]
         session_candles = pd.concat([candles_end_of_day, candles_start_of_next_day]).sort_index()
         # Ensure we only take candles that fall within the date range covered by target_date and next_day_date
         # Adjusting the filter range to correctly capture the cross-midnight session
         filter_start = pd.Timestamp.combine(target_date_localized.date(), session_start_time).tz_localize(current_tz)
         filter_end = pd.Timestamp.combine(next_day_date_localized.date(), session_end_time).tz_localize(current_tz)
         session_candles = session_candles[(session_candles.index >= filter_start) & (session_candles.index <= filter_end)]

    else:
         # For sessions within a single day, filter by date
         session_candles = session_candles[session_candles.index.date == target_date_localized.date()]


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

    # Use the correct variable names with _UTC suffix
    asian_start_time = time(settings.ASIAN_SESSION_START_HOUR_UTC, settings.ASIAN_SESSION_START_MINUTE_UTC)
    asian_end_time = time(settings.ASIAN_SESSION_END_HOUR_UTC, settings.ASIAN_SESSION_END_MINUTE_UTC)
    ny_start_time = time(settings.NY_SESSION_START_HOUR_UTC, settings.NY_SESSION_START_MINUTE_UTC)
    ny_end_time = time(settings.NY_SESSION_END_HOUR_UTC, settings.NY_SESSION_END_MINUTE_UTC)


    # Determine the timezone to use, prioritizing DataFrame index tz, then UTC
    current_tz = full_df.index.tz if hasattr(full_df.index, 'tz') and full_df.index.tz is not None else timezone.utc

    # The date relative to which we search for sessions.
    # If current_processing_dt is the last candle, "today" is the day of that candle.
    today_date = pd.Timestamp(current_processing_dt.date(), tz=current_tz)

    # The Asian session might start at the end of the previous day in UTC
    # So for the Asian session starting at 22:00 UTC (01:00 UTC+3),
    # we look for candles starting from 22:00 UTC of the previous day until 06:00 UTC of the current day.
    asian_session_target_date = today_date
    if asian_start_time > asian_end_time: # If the Asian session crosses midnight UTC
         asian_session_target_date = today_date - timedelta(days=1) # Start searching from the previous day


    asian_candles_today = get_candles_for_session(full_df, asian_session_target_date, asian_start_time, asian_end_time)


    if not asian_candles_today.empty:
        # Use settings.SESSION_FRACTAL_N for Asian fractals
        todays_asian_fractals = get_session_fractals(asian_candles_today, settings.SESSION_FRACTAL_N, "Asia", "_AS")
        all_identified_fractals.extend(todays_asian_fractals)
    else:
        todays_asian_fractals = []

    past_ny_fractals = []
    for i in range(1, settings.NY_SESSIONS_TO_CHECK_PREVIOUS_DAYS + 1):
        prev_date = today_date - timedelta(days=i)
        ny_candles_past = get_candles_for_session(full_df, prev_date, ny_start_time, ny_end_time)
        if not ny_candles_past.empty:
            # Use settings.SESSION_FRACTAL_N for New York fractals
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

                    if setup_type != "UNKNOWN_SETUP": # Only add if it's Resist or Support
                        setup_point = {
                            'time': asian_f['time'],
                            'price': asian_f['price'], # The setup price is the Asian fractal price
                            'type': setup_type,
                            'session': 'Setup',
                            'details': f"Asian {asian_f['type']} at {asian_f['price']:.5f} ({asian_f['time'].strftime('%H:%M')}) "
                                       f"near NY {ny_f['type']} at {ny_f['price']:.5f} ({ny_f['time'].strftime('%Y-%m-%d %H:%M')}), "
                                       f"Diff: {price_diff:.5f}"
                        }
                        setup_points.append(setup_point)
                        all_identified_fractals.append(setup_point)
                        print(f"fractal_analyzer: SETUP FOUND! {setup_type} at {asian_f['time'].strftime('%Y-%m-%d %H:%M')} price {asian_f['price']:.5f}")

    all_identified_fractals.sort(key=lambda x: x['time'])
    return all_identified_fractals

if __name__ == '__main__':
    print("Тестирование fractal_analyzer.py (с SESSION_FRACTAL_N)...")

    # Set test values for settings if they differ from the main ones
    original_swing_n = settings.SWING_POINT_N
    original_session_n = settings.SESSION_FRACTAL_N
    original_asia_start_h = settings.ASIAN_SESSION_START_HOUR_UTC
    original_asia_start_m = settings.ASIAN_SESSION_START_MINUTE_UTC
    original_asia_end_h = settings.ASIAN_SESSION_END_HOUR_UTC
    original_asia_end_m = settings.ASIAN_SESSION_END_MINUTE_UTC
    original_ny_start_h = settings.NY_SESSION_START_HOUR_UTC
    original_ny_start_m = settings.NY_SESSION_START_MINUTE_UTC
    original_ny_end_h = settings.NY_SESSION_END_HOUR_UTC
    original_ny_end_m = settings.NY_SESSION_END_MINUTE_UTC


    settings.SWING_POINT_N = 5 # For general context (not used directly in this test)
    settings.SESSION_FRACTAL_N = 1 # For session fractals in this test

    # Set test session times in UTC for the test
    settings.ASIAN_SESSION_START_HOUR_UTC = 22 # 01:00 UTC+3
    settings.ASIAN_SESSION_START_MINUTE_UTC = 0
    settings.ASIAN_SESSION_END_HOUR_UTC = 6 # 09:00 UTC+3
    settings.ASIAN_SESSION_END_MINUTE_UTC = 0

    settings.NY_SESSION_START_HOUR_UTC = 12 # 15:00 UTC+3
    settings.NY_SESSION_START_MINUTE_UTC = 0
    settings.NY_SESSION_END_HOUR_UTC = 19 # 22:00 UTC+3
    settings.NY_SESSION_END_MINUTE_UTC = 0


    # Create data to cover multiple days and sessions
    rng = pd.date_range(start='2023-10-01 00:00', end='2023-10-04 23:59', freq='1H', tz='UTC')
    data = { # Data to guarantee fractals at n=1
        'open': [1.0500, 1.0510, 1.0490, 1.0520, 1.0480] * (len(rng)//5 + 1) [:len(rng)],
        'high': [1.0505, 1.0515, 1.0530, 1.0525, 1.0540] * (len(rng)//5 + 1) [:len(rng)], # Clear high on the 3rd candle
        'low':  [1.0495, 1.0485, 1.0490, 1.0470, 1.0480] * (len(rng)//5 + 1) [:len(rng)], # Clear low on the 4th candle
        'close':[1.0503, 1.0500, 1.0510, 1.0490, 1.0500] * (len(rng)//5 + 1) [:len(rng)],
        'volume':[100 + i*10 for i in range(len(rng))]
    }
    test_df_full = pd.DataFrame(data, index=rng)

    # Ensure current_processing_dt has a timezone
    # Test analysis on 2023-10-04
    current_time_for_test = dt_datetime(2023, 10, 4, 10, 0, 0, tzinfo=timezone.utc) # Set time in the middle of Asian session on Oct 4th UTC
    if test_df_full.index.tz:
        current_time_for_test = current_time_for_test.astimezone(test_df_full.index.tz)


    print(f"\nТестовый DataFrame создан, свечей: {len(test_df_full)}")
    print(f"Тестирование с settings.SESSION_FRACTAL_N = {settings.SESSION_FRACTAL_N}")
    print(f"Тестирование сессий (UTC): Азия {settings.ASIAN_SESSION_START_HOUR_UTC}:{settings.ASIAN_SESSION_START_MINUTE_UTC}-{settings.ASIAN_SESSION_END_HOUR_UTC}:{settings.ASIAN_SESSION_END_MINUTE_UTC}, NY {settings.NY_SESSION_START_HOUR_UTC}:{settings.NY_SESSION_START_MINUTE_UTC}-{settings.NY_SESSION_END_HOUR_UTC}:{settings.NY_SESSION_END_MINUTE_UTC}")


    print("\nТестирование get_candles_for_session (Азия, 2023-10-04):")
    asian_s_time = time(settings.ASIAN_SESSION_START_HOUR_UTC, settings.ASIAN_SESSION_START_MINUTE_UTC)
    asian_e_time = time(settings.ASIAN_SESSION_END_HOUR_UTC, settings.ASIAN_SESSION_END_MINUTE_UTC)
    target_d_asia = pd.Timestamp(current_time_for_test.date(), tz=test_df_full.index.tz) # Date for Asian session - day of current_processing_dt

    asian_test_candles = get_candles_for_session(test_df_full, target_d_asia, asian_s_time, asian_e_time)
    if not asian_test_candles.empty:
        print(f"Найдено азиатских свечей для {target_d_asia.date()}: {len(asian_test_candles)}")
        # print(asian_test_candles.head(2))
        # print(asian_test_candles.tail(2))

        print("\nТестирование get_session_fractals (Азия, 2023-10-04):")
        asian_test_fractals = get_session_fractals(asian_test_candles, settings.SESSION_FRACTAL_N, "AsiaTest", "_AST")
        print(f"Найдено азиатских фракталов: {len(asian_test_fractals)}")
        for f_idx, f_val in enumerate(asian_test_fractals): print(f"  {f_idx}: {f_val}")
    else:
        print(f"Азиатские свечи не найдены для {target_d_asia.date()}.")

    print("\nТестирование get_candles_for_session (NY, 2023-10-03):")
    ny_s_time = time(settings.NY_SESSION_START_HOUR_UTC, settings.NY_SESSION_START_MINUTE_UTC)
    ny_e_time = time(settings.NY_SESSION_END_HOUR_UTC, settings.NY_SESSION_END_MINUTE_UTC)
    target_d_ny = pd.Timestamp((current_time_for_test - timedelta(days=1)).date(), tz=test_df_full.index.tz) # Date for NY session - previous day

    ny_test_candles = get_candles_for_session(test_df_full, target_d_ny, ny_s_time, ny_e_time)
    if not ny_test_candles.empty:
        print(f"Найдено NY свечей для {target_d_ny.date()}: {len(ny_test_candles)}")
        # print(ny_test_candles.head(2))
        # print(ny_test_candles.tail(2))

        print("\nТестирование get_session_fractals (NY, 2023-10-03):")
        ny_test_fractals = get_session_fractals(ny_test_candles, settings.SESSION_FRACTAL_N, "NYTest", "_NYT")
        print(f"Найдено NY фракталов: {len(ny_test_fractals)}")
        for f_idx, f_val in enumerate(ny_test_fractals): print(f"  {f_idx}: {f_val}")
    else:
        print(f"NY свечи не найдены для {target_d_ny.date()}.")


    print("\nТестирование analyze_fractal_setups...")
    # Increase threshold for the test to ensure setups are found if fractals are close
    original_threshold = settings.FRACTAL_PROXIMITY_THRESHOLD_PIPS
    settings.FRACTAL_PROXIMITY_THRESHOLD_PIPS = 50 # 50 pips

    all_fractals_and_setups = analyze_fractal_setups(test_df_full, current_time_for_test)

    print("\nВсе идентифицированные фракталы и сетапы для графика:")
    if all_fractals_and_setups:
        for p_idx, p_val in enumerate(all_fractals_and_setups):
            details_str = f" - {p_val['details']}" if 'details' in p_val else ""
            print(f"  {p_idx}: Время: {p_val['time']}, Цена: {p_val['price']:.5f}, Тип: {p_val['type']}, Сессия: {p_val['session']}{details_str}")
    else:
        print("  Ничего не найдено.")

    # Restore original values
    settings.SWING_POINT_N = original_swing_n
    settings.SESSION_FRACTAL_N = original_session_n
    settings.FRACTAL_PROXIMITY_THRESHOLD_PIPS = original_threshold
    settings.ASIAN_SESSION_START_HOUR_UTC = original_asia_start_h
    settings.ASIAN_SESSION_START_MINUTE_UTC = original_asia_start_m
    settings.ASIAN_SESSION_END_HOUR_UTC = original_asia_end_h
    settings.ASIAN_SESSION_END_MINUTE_UTC = original_asia_end_m
    settings.NY_SESSION_START_HOUR_UTC = original_ny_start_h
    settings.NY_SESSION_START_MINUTE_UTC = original_ny_start_m
    settings.NY_SESSION_END_HOUR_UTC = original_ny_end_h
    settings.NY_SESSION_END_MINUTE_UTC = original_ny_end_m
