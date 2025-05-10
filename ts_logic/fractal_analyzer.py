# ts_logic/fractal_analyzer.py
import pandas as pd
from datetime import time, timedelta, datetime as dt_datetime
from configs import settings
from ts_logic.context_analyzer_1h import find_swing_points

def get_candles_for_session(df: pd.DataFrame, target_date: pd.Timestamp, 
                            session_start_time: time, session_end_time: time) -> pd.DataFrame:
    """
    Фильтрует DataFrame для получения свечей, попадающих в указанную сессию на указанную дату.
    """
    if df.empty:
        return pd.DataFrame()

    if not isinstance(df.index, pd.DatetimeIndex):
        # print("fractal_analyzer: ОШИБКА: Индекс DataFrame должен быть DatetimeIndex.") # Оставим критические ошибки
        return pd.DataFrame()
        
    start_datetime = pd.Timestamp.combine(target_date.date(), session_start_time).tz_localize(df.index.tz)
    end_datetime = pd.Timestamp.combine(target_date.date(), session_end_time).tz_localize(df.index.tz)

    if session_end_time < session_start_time: 
        day_candles = df[df.index.date == target_date.date()]
        if day_candles.empty:
            return pd.DataFrame()
        session_candles = day_candles.between_time(session_start_time, session_end_time, include_start=True, include_end=True)
    else: 
        session_candles = df.loc[start_datetime:end_datetime]
    return session_candles


def get_session_fractals(candles: pd.DataFrame, n_swing: int, session_tag: str, point_type_suffix: str) -> list:
    """
    Находит фракталы (свинги) на предоставленных свечах и помечает их тегом сессии.
    """
    fractals = []
    if candles.empty or len(candles) < (2 * n_swing + 1) :
        return fractals

    swing_highs, swing_lows = find_swing_points(candles, n=n_swing) # Внутренние print в find_swing_points уже закомментированы

    for sh in swing_highs:
        fractals.append({'time': sh['time'], 'price': sh['price'], 'type': f'F_H{point_type_suffix}', 'session': session_tag})
    for sl in swing_lows:
        fractals.append({'time': sl['time'], 'price': sl['price'], 'type': f'F_L{point_type_suffix}', 'session': session_tag})
    return fractals

def analyze_fractal_setups(full_df: pd.DataFrame, current_processing_dt: dt_datetime):
    """
    Основная функция для анализа фракталов сессий и поиска сетапов.
    """
    # print(f"\n--- fractal_analyzer: Начало анализа сессионных фракталов ({current_processing_dt.strftime('%Y-%m-%d %H:%M')}) ---")
    
    all_identified_fractals = [] 
    setup_points = []            

    asian_start_time = time(settings.ASIAN_SESSION_START_HOUR_UTC, settings.ASIAN_SESSION_START_MINUTE)
    asian_end_time = time(settings.ASIAN_SESSION_END_HOUR_UTC, settings.ASIAN_SESSION_END_MINUTE)
    ny_start_time = time(settings.NY_SESSION_START_HOUR_UTC, settings.NY_SESSION_START_MINUTE)
    ny_end_time = time(settings.NY_SESSION_END_HOUR_UTC, settings.NY_SESSION_END_MINUTE)

    today_date = pd.Timestamp(current_processing_dt.date(), tz=full_df.index.tz if full_df.index.tz else 'UTC') 

    # print(f"fractal_analyzer: Анализ Азиатской сессии для даты: {today_date.date()}")
    asian_candles_today = get_candles_for_session(full_df, today_date, asian_start_time, asian_end_time)
    
    if not asian_candles_today.empty:
        todays_asian_fractals = get_session_fractals(asian_candles_today, settings.SWING_POINT_N, "Asia", "_AS")
        all_identified_fractals.extend(todays_asian_fractals)
        # print(f"fractal_analyzer: Найдено азиатских фракталов сегодня: {len(todays_asian_fractals)}")
    else:
        todays_asian_fractals = []
        # print(f"fractal_analyzer: Нет свечей для Азиатской сессии сегодня ({today_date.date()}).")

    past_ny_fractals = []
    for i in range(1, settings.NY_SESSIONS_TO_CHECK_PREVIOUS_DAYS + 1):
        prev_date = today_date - timedelta(days=i)
        # print(f"fractal_analyzer: Анализ Нью-Йоркской сессии для предыдущей даты: {prev_date.date()}")
        
        ny_candles_past = get_candles_for_session(full_df, prev_date, ny_start_time, ny_end_time)
        if not ny_candles_past.empty:
            ny_fractals_on_date = get_session_fractals(ny_candles_past, settings.SWING_POINT_N, f"NY (Day -{i})", f"_NY{i}")
            past_ny_fractals.extend(ny_fractals_on_date)
            all_identified_fractals.extend(ny_fractals_on_date)
            # print(f"fractal_analyzer: Найдено НЙ фракталов для {prev_date.date()}: {len(ny_fractals_on_date)}")
        else:
            # print(f"fractal_analyzer: Нет свечей для Нью-Йоркской сессии ({prev_date.date()}).")
            pass
            
    # if not past_ny_fractals:
        # print("fractal_analyzer: Не найдено Нью-Йоркских фракталов в указанных прошлых сессиях.")
    
    if todays_asian_fractals and past_ny_fractals:
        price_threshold = settings.FRACTAL_PROXIMITY_THRESHOLD_PIPS * settings.PIP_VALUE_DEFAULT
        # print(f"fractal_analyzer: Поиск сетапов. Порог ценовой близости: {price_threshold:.5f}")

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
                    
                    setup_point = {
                        'time': asian_f['time'],
                        'price': asian_f['price'],
                        'type': setup_type,
                        'session': 'Setup', 
                        'details': f"Asian {asian_f['type']} at {asian_f['price']:.5f} ({asian_f['time'].strftime('%H:%M')}) "
                                   f"near NY {ny_f['type']} at {ny_f['price']:.5f} ({ny_f['time'].strftime('%Y-%m-%d %H:%M')}), "
                                   f"Diff: {price_diff:.5f}"
                    }
                    setup_points.append(setup_point)
                    all_identified_fractals.append(setup_point) 
                    # Эти print-ы можно оставить, если они важны для индикации найденного сетапа, либо тоже закомментировать
                    print(f"fractal_analyzer: НАЙДЕН СЕТАП! {setup_type} в {asian_f['time'].strftime('%Y-%m-%d %H:%M')} цена {asian_f['price']:.5f}")
                    # print(f"                   Детали: {setup_point['details']}")
    # else:
        # if not todays_asian_fractals:
            # print("fractal_analyzer: Нет сегодняшних азиатских фракталов для поиска сетапов.")
        # if not past_ny_fractals:
            # print("fractal_analyzer: Нет прошлых нью-йоркских фракталов для поиска сетапов.")

    # print(f"--- fractal_analyzer: Анализ сессионных фракталов завершен. Найдено сетапов: {len(setup_points)} ---")
    
    all_identified_fractals.sort(key=lambda x: x['time'])
    return all_identified_fractals

if __name__ == '__main__':
    print("Тестирование fractal_analyzer.py...")
    rng = pd.date_range(start='2023-10-01 00:00', end='2023-10-03 23:59', freq='1H', tz='UTC')
    data = {
        'open': [1.0500 + i*0.0001 for i in range(len(rng))],
        'high': [1.0505 + i*0.00015 + ( (i%5) *0.0003 if i%2==0 else -(i%3)*0.0002) for i in range(len(rng))],
        'low':  [1.0495 - i*0.00005 - ( (i%4) *0.0002 if i%2!=0 else -(i%2)*0.0001) for i in range(len(rng))],
        'close':[1.0503 + i*0.00007 for i in range(len(rng))],
        'volume':[100 + i*10 for i in range(len(rng))]
    }
    test_df_full = pd.DataFrame(data, index=rng)
    current_time_for_test = dt_datetime(2023, 10, 3, 22, 0, 0, tzinfo=test_df_full.index.tz)

    # print(f"\nТестовый DataFrame создан, свечей: {len(test_df_full)}")
    # print("Первые 3 строки:")
    # print(test_df_full.head(3))
    # print("Последние 3 строки:")
    # print(test_df_full.tail(3))

    # print("\nТестирование get_candles_for_session (Азия, 2023-10-03):")
    asian_s_time = time(settings.ASIAN_SESSION_START_HOUR_UTC, settings.ASIAN_SESSION_START_MINUTE)
    asian_e_time = time(settings.ASIAN_SESSION_END_HOUR_UTC, settings.ASIAN_SESSION_END_MINUTE)
    target_d = pd.Timestamp(current_time_for_test.date(), tz=test_df_full.index.tz)
    
    asian_test_candles = get_candles_for_session(test_df_full, target_d, asian_s_time, asian_e_time)
    # if not asian_test_candles.empty:
        # print(f"Найдено азиатских свечей: {len(asian_test_candles)}")
        # print(asian_test_candles.head(2))
        # print(asian_test_candles.tail(2))
    # else:
        # print("Азиатские свечи не найдены для теста.")

    # print("\nТестирование get_session_fractals (Азия, 2023-10-03):")
    # if not asian_test_candles.empty:
        # asian_test_fractals = get_session_fractals(asian_test_candles, settings.SWING_POINT_N, "AsiaTest", "_AST")
        # for f in asian_test_fractals: print(f)
    # else:
        # print("Пропуск теста get_session_fractals, т.к. нет азиатских свечей.")

    # print("\nТестирование analyze_fractal_setups...")
    original_threshold = settings.FRACTAL_PROXIMITY_THRESHOLD_PIPS
    settings.FRACTAL_PROXIMITY_THRESHOLD_PIPS = 50 
    
    all_fractals_and_setups = analyze_fractal_setups(test_df_full, current_time_for_test)
    settings.FRACTAL_PROXIMITY_THRESHOLD_PIPS = original_threshold 

    # print("\nВсе идентифицированные фракталы и сетапы для графика:")
    # if all_fractals_and_setups:
        # for p in all_fractals_and_setups:
            # details_str = f" - {p['details']}" if 'details' in p else ""
            # print(f"  Время: {p['time']}, Цена: {p['price']:.5f}, Тип: {p['type']}, Сессия: {p['session']}{details_str}")
    # else:
        # print("  Ничего не найдено.")
