# bot/core/data_fetcher.py
import requests
import pandas as pd
from configs import settings # Импортируем настройки из configs/settings.py
from datetime import datetime, timedelta # Импортируем timedelta

def get_forex_data(symbol: str, interval: str, outputsize: int = None, start_date: datetime = None, end_date: datetime = None, api_key: str = settings.API_KEY_TWELVE_DATA):
    """
    Получает исторические данные OHLCV для указанного символа с Twelve Data API.
    Может получать данные либо по outputsize (последние N свечей), либо по диапазону дат.

    Args:
        symbol (str): Символ валютной пары (например, "EUR/USD").
        interval (str): Таймфрейм (например, "1h", "30min", "1day").
        outputsize (int, optional): Количество возвращаемых точек данных (используется, если start_date и end_date не указаны).
        start_date (datetime, optional): Начальная дата диапазона данных (в UTC).
        end_date (datetime, optional): Конечная дата диапазона данных (в UTC).
        api_key (str, optional): API ключ для Twelve Data. По умолчанию используется из settings.

    Returns:
        pd.DataFrame: DataFrame с данными OHLCV, отсортированный от старых к новым,
                      с DatetimeIndex. Возвращает пустой DataFrame в случае ошибки.
    """
    params = {
        "symbol": symbol,
        "interval": interval,
        "apikey": api_key,
        "format": "JSON",
        "timezone": "UTC", # Явно запрашиваем данные в UTC
    }

    # Используем либо диапазон дат, либо outputsize
    if start_date and end_date:
        # Форматируем даты в строку YYYY-MM-DD HH:MM:SS (Twelve Data ожидает такой формат)
        params["start_date"] = start_date.strftime('%Y-%m-%d %H:%M:%S')
        params["end_date"] = end_date.strftime('%Y-%m-%d %H:%M:%S')
        print(f"data_fetcher: Запрос данных для {symbol}, интервал {interval}, диапазон: {params['start_date']} - {params['end_date']}...")
    elif outputsize is not None:
        params["outputsize"] = outputsize
        print(f"data_fetcher: Запрос данных для {symbol}, интервал {interval}, {outputsize} свечей...")
    else:
        print("data_fetcher: Ошибка: Не указаны ни outputsize, ни диапазон дат.")
        return pd.DataFrame()


    url = f"{settings.BASE_URL_TWELVE_DATA}/time_series"

    try:
        response = requests.get(url, params=params)
        response.raise_for_status()  # Вызовет исключение для HTTP ошибок (4xx или 5xx)
        data = response.json()

        if data.get("status") == "ok" and "values" in data:
            df = pd.DataFrame(data["values"])

            if df.empty:
                 print(f"data_fetcher: API вернул пустой список значений для {symbol} ({interval}).")
                 return pd.DataFrame()

            # Конвертируем типы данных
            # Twelve Data возвращает datetime в UTC, если запрошен timezone="UTC"
            df['datetime'] = pd.to_datetime(df['datetime'])
            numeric_cols = ['open', 'high', 'low', 'close', 'volume']
            for col in numeric_cols:
                if col in df.columns: # 'volume' может отсутствовать
                    # errors='coerce' заменит нечисловые на NaN
                    df[col] = pd.to_numeric(df[col], errors='coerce')

            # Устанавливаем datetime как индекс (требуется для mplfinance и удобства работы)
            # Если API вернул данные в порядке от новых к старым (DESC), развернем DataFrame.
            # Twelve Data с диапазоном дат обычно возвращает ASC, но лучше проверить.
            if not df['datetime'].is_monotonic_increasing:
                 df = df.iloc[::-1].reset_index(drop=True)

            df = df.set_index('datetime')

            # Удаляем строки с NaN
            df.dropna(subset=['open', 'high', 'low', 'close'], inplace=True)

            if df.empty:
                print(f"data_fetcher: DataFrame для {symbol} пуст после обработки (возможно, все данные были NaN).")
                return pd.DataFrame()

            # Убедимся, что индекс в UTC (если Twelve Data не вернул его таким)
            if df.index.tzinfo is None:
                 df = df.tz_localize('UTC')
            else:
                 df = df.tz_convert('UTC')


            # print(f"data_fetcher: Данные для {symbol} успешно получены. Свечей: {len(df)}")
            return df
        elif "message" in data:
            print(f"data_fetcher: Ошибка API Twelve Data для {symbol}: {data['message']} (Код: {data.get('code')})")
            return pd.DataFrame()
        else:
            print(f"data_fetcher: Неожиданный ответ от API Twelve Data для {symbol}: {data}")
            return pd.DataFrame()

    except requests.exceptions.RequestException as e:
        print(f"data_fetcher: Ошибка HTTP запроса при получении данных для {symbol}: {e}")
        return pd.DataFrame()
    except Exception as e:
        print(f"data_fetcher: Произошла непредвиденная ошибка при обработке данных для {symbol}: {e}")
        return pd.DataFrame()

if __name__ == '__main__':
    print("Тестирование data_fetcher.py (с диапазоном дат)...")
    if settings.API_KEY_TWELVE_DATA == "YOUR_TWELVE_DATA_API_KEY_HERE" or not settings.API_KEY_TWELVE_DATA:
        print("Тест не может быть выполнен: API ключ не настроен в configs/settings.py или .env файле.")
    else:
        test_symbol = "EUR/USD"
        test_interval = "1h"
        # Тестирование по диапазону дат (пример: один день)
        test_start_date = datetime(2023, 10, 1, 0, 0, 0, tzinfo=timezone.utc)
        test_end_date = datetime(2023, 10, 1, 23, 59, 59, tzinfo=timezone.utc)

        print(f"\nТестирование запроса по диапазону дат: {test_start_date} - {test_end_date}")
        df_date_range = get_forex_data(test_symbol, test_interval, start_date=test_start_date, end_date=test_end_date)

        if not df_date_range.empty:
            print(f"\nПолучены данные для {test_symbol} ({test_interval}) по диапазону дат:")
            print(df_date_range.head())
            print("...")
            print(df_date_range.tail())
            df_date_range.info()
        else:
            print(f"\nНе удалось получить тестовые данные для {test_symbol} по диапазону дат.")

        print("\nТестирование запроса по outputsize (последние 50 свечей):")
        df_outputsize = get_forex_data(test_symbol, test_interval, outputsize=50)
        if not df_outputsize.empty:
            print(f"\nПолучены данные для {test_symbol} ({test_interval}) по outputsize:")
            print(df_outputsize.head())
            print("...")
            print(df_outputsize.tail())
            df_outputsize.info()
        else:
            print(f"\nНе удалось получить тестовые данные для {test_symbol} по outputsize.")

