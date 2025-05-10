# bot/core/data_fetcher.py
import requests
import pandas as pd
from configs import settings # Импортируем настройки из configs/settings.py

def get_forex_data(symbol: str, interval: str, outputsize: int, api_key: str = settings.API_KEY_TWELVE_DATA):
    """
    Получает исторические данные OHLCV для указанного символа с Twelve Data API.

    Args:
        symbol (str): Символ валютной пары (например, "EUR/USD").
        interval (str): Таймфрейм (например, "1h", "30min", "1day").
        outputsize (int): Количество возвращаемых точек данных.
        api_key (str, optional): API ключ для Twelve Data. По умолчанию используется из settings.

    Returns:
        pd.DataFrame: DataFrame с данными OHLCV, отсортированный от старых к новым,
                      с DatetimeIndex. Возвращает пустой DataFrame в случае ошибки.
    """
    params = {
        "symbol": symbol,
        "interval": interval,
        "apikey": api_key,
        "outputsize": outputsize,
        "format": "JSON",
        # "timezone": "UTC", # Рекомендуется для консистентности, если ваш брокер/биржа работает в UTC
    }
    url = f"{settings.BASE_URL_TWELVE_DATA}/time_series"
    
    # print(f"data_fetcher: Запрос данных для {symbol}, интервал {interval}, {outputsize} свечей...")
    try:
        response = requests.get(url, params=params)
        response.raise_for_status()  # Вызовет исключение для HTTP ошибок (4xx или 5xx)
        data = response.json()

        if data.get("status") == "ok" and "values" in data:
            df = pd.DataFrame(data["values"])
            
            # Конвертируем типы данных
            df['datetime'] = pd.to_datetime(df['datetime'])
            numeric_cols = ['open', 'high', 'low', 'close', 'volume']
            for col in numeric_cols:
                if col in df.columns: # 'volume' может отсутствовать
                    df[col] = pd.to_numeric(df[col], errors='coerce') # errors='coerce' заменит нечисловые на NaT/NaN
            
            # Данные от Twelve Data приходят в порядке от новых к старым (DESC)
            # Развернем DataFrame, чтобы самые старые данные были в начале
            df = df.iloc[::-1].reset_index(drop=True)
            
            # Устанавливаем datetime как индекс (требуется для mplfinance и удобства работы)
            df = df.set_index('datetime')
            
            # Удаляем строки с NaN, которые могли появиться из-за errors='coerce'
            # или если какие-то значения цен/объема отсутствовали
            df.dropna(subset=['open', 'high', 'low', 'close'], inplace=True)

            if df.empty:
                print(f"data_fetcher: DataFrame для {symbol} пуст после обработки (возможно, все данные были NaN).")
                return pd.DataFrame()

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
    # Пример использования (для тестирования этого модуля)
    # Чтобы этот тест работал, вам нужно запускать его из корневой директории проекта,
    # например: python -m bot.core.data_fetcher
    # Или временно изменить импорт configs, если запускаете напрямую:
    # import sys
    # sys.path.append(os.path.join(os.path.dirname(__file__), '../../')) # Добавить корень проекта в путь
    # from configs import settings

    print("Тестирование data_fetcher.py...")
    if settings.API_KEY_TWELVE_DATA == "YOUR_TWELVE_DATA_API_KEY_HERE" or not settings.API_KEY_TWELVE_DATA:
        print("Тест не может быть выполнен: API ключ не настроен в configs/settings.py или .env файле.")
    else:
        test_symbol = "GBP/USD"
        test_interval = "1h"
        test_outputsize = 50
        
        df_test = get_forex_data(test_symbol, test_interval, test_outputsize)
        
        if not df_test.empty:
            print(f"\nПолучены данные для {test_symbol}:")
            print(df_test.head())
            print("...")
            print(df_test.tail())
            df_test.info()
        else:
            print(f"\nНе удалось получить тестовые данные для {test_symbol}.")
