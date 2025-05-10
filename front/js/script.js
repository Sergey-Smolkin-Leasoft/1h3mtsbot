// front/js/script.js

// Изменяем слушатель события с DOMContentLoaded на window.load
window.addEventListener('load', () => {
    const chartContainer = document.getElementById('chart-container');
    const timeframeSelect = document.getElementById('timeframe-select'); // Получаем элемент select

    if (!chartContainer) {
        console.error('Контейнер для графика не найден!');
        return;
    }

    // Добавляем проверку, что LightweightCharts доступен
    if (typeof LightweightCharts === 'undefined') {
        console.error('Библиотека LightweightCharts не загружена.');
        // Возможно, стоит добавить задержку и попробовать снова, или показать сообщение пользователю
        return;
    }

    let chart = null; // Объявляем chart здесь
    let candlestickSeries = null; // Объявляем candlestickSeries здесь

    try {
        // Создаем экземпляр графика
        // Убедимся, что контейнер имеет размеры, чтобы createChart работал корректно
        // Используем актуальные размеры контейнера после загрузки страницы
        chart = LightweightCharts.createChart(chartContainer, {
            width: chartContainer.clientWidth,
            height: chartContainer.clientHeight,
            layout: {
                background: { color: '#FFFFFF' }, // БЕЛЫЙ фон графика
                textColor: '#000000', // Черный текст для меток осей
            },
            grid: {
                vertLines: { color: '#E0E0E0' }, // Светло-серые вертикальные линии сетки
                horzLines: { color: '#E0E0E0' }, // Светло-серые горизонтальные линии сетки
            },
            timeScale: {
                timeVisible: true,
                secondsVisible: false,
                borderColor: '#B0B0B0', // Цвет границы шкалы времени (темнее серого)
            },
            crosshair: {
                mode: LightweightCharts.CrosshairMode.Normal,
            },
            priceScale: {
                borderColor: '#B0B0B0', // Цвет границы ценовой шкалы (темнее серого)
            },
        });

        // Явная проверка, что chart создан успешно
        if (!chart) {
             console.error('Не удалось создать экземпляр графика LightweightCharts.');
             return; // Выходим, если chart не создан
        }

        // Добавляем серию свечей - КРАСНО-ЗЕЛЕНЫЕ ЦВЕТА
        candlestickSeries = chart.addSeries(LightweightCharts.CandlestickSeries, {
            upColor: '#26A69A', // Зеленый для растущих свечей (бычьих)
            downColor: '#EF5350', // Красный для падающих свечей (медвежьих)
            borderVisible: false, // Границы свечей не видны
            wickColor: '#7F8C8D', // Серый для фитилей (можно настроить)
            wickUpColor: '#26A69A', // Зеленый для фитилей растущих свечей
            wickDownColor: '#EF5350', // Красный для фитилей падающих свечей
        });

         // Явная проверка, что серия создана успешно
        if (!candlestickSeries) {
             console.error('Не удалось создать серию свечей.');
             return; // Выходим, если серия не создана
        }


    } catch (e) {
        console.error('Ошибка при создании графика или серии LightweightCharts:', e);
        return;
    }

    // Функция для получения данных с бэкенда с учетом таймфрейма
    async function fetchChartData(timeframe) {
        try {
            // Добавляем параметр timeframe в URL запроса
            const url = `/api/chart_data?interval=${timeframe}`;
            console.log(`fetchChartData: Запрос к URL: ${url}`); // Логируем URL запроса
            const response = await fetch(url);
            if (!response.ok) {
                console.error(`fetchChartData: Ошибка HTTP! статус: ${response.status}`); // Логируем ошибку HTTP
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            const data = await response.json();
            console.log('fetchChartData: Получены данные:', data); // Логируем полученные данные
            return data;
        } catch (error) {
            console.error('fetchChartData: Ошибка при получении данных графика:', error); // Логируем ошибку fetch
            return { ohlcv: [], markers: [] };
        }
    }

    // Функция для форматирования данных OHLCV для Lightweight Charts
    function formatOhlcvData(data) {
        const formattedData = data.map(item => ({
            time: new Date(item.time).getTime() / 1000, // Преобразуем в timestamp в секундах
            open: parseFloat(item.open),
            high: parseFloat(item.high),
            low: parseFloat(item.low),
            close: parseFloat(item.close),
        }));
        // Логируем первые несколько отформатированных точек времени
        console.log('formatOhlcvData: Первые 5 отформатированных временных меток:', formattedData.slice(0, 5).map(item => item.time));
        return formattedData;
    }

    // Функция для форматирования данных маркеров для Lightweight Charts
    function formatMarkerData(data) {
         const markerMap = {
             'HH': { shape: 'arrowDown', color: '#2962FF', position: 'aboveBar' }, // Синий
             'HL': { shape: 'circle', color: '#26A69A', position: 'belowBar' },   // Зеленый
             'LH': { shape: 'arrowUp', color: '#FF0000', position: 'belowBar' },   // Красный
             'LL': { shape: 'circle', color: '#FF0000', position: 'aboveBar' },   // Красный
             'H': { shape: 'square', color: '#2962FF', position: 'aboveBar' },    // Синий
             'L': { shape: 'square', color: '#26A69A', position: 'belowBar' },    // Зеленый
             'F_H_AS': { shape: 'circle', color: '#FFA500', position: 'aboveBar' }, // Оранжевый
             'F_L_AS': { shape: 'circle', color: '#FFA500', position: 'belowBar' }, // Оранжевый
             'F_H_NY1': { shape: 'circle', color: '#1E90FF', position: 'aboveBar' }, // Голубой
             'F_L_NY1': { shape: 'circle', color: '#1E90FF', position: 'belowBar' }, // Голубой
             'SETUP_Resist': { shape: 'square', color: '#000000', position: 'aboveBar', size: 1.5 }, // Черный
             'SETUP_Support': { shape: 'square', color: '#000000', position: 'belowBar', size: 1.5 }, // Черный
             'UNKNOWN_SETUP': { shape: 'circle', color: '#808080', position: 'aboveBar' } // Серый
         };

         return data.map(item => {
             const markerType = markerMap[item.type] || { shape: 'circle', color: '#808080', position: 'aboveBar' };
             return {
                 time: new Date(item.time).getTime() / 1000,
                 position: markerType.position,
                 color: markerType.color,
                 shape: markerType.shape,
                 text: item.type,
                 size: markerType.size || 1,
             };
         });
     }

    // Функция для загрузки и отображения данных графика
    async function loadChartData(timeframe) {
        console.log(`loadChartData: Начало загрузки данных для таймфрейма: ${timeframe}`); // Логируем начало
        const chartData = await fetchChartData(timeframe);
        console.log('loadChartData: Данные получены из fetchChartData:', chartData); // Логируем данные после fetch

        if (chartData && chartData.ohlcv && chartData.ohlcv.length > 0) {
            console.log(`loadChartData: Получено ${chartData.ohlcv.length} свечей.`); // Логируем количество свечей
            const formattedOhlcv = formatOhlcvData(chartData.ohlcv);
             // Очищаем старые данные и устанавливаем новые
             if (candlestickSeries && typeof candlestickSeries.setData === 'function') {
                candlestickSeries.setData(formattedOhlcv);
                 console.log('loadChartData: Данные свечей установлены.'); // Логируем установку данных
             } else {
                 console.error('loadChartData: candlestickSeries недействителен или не имеет метода setData.');
                 return; // Выходим, если не можем установить данные
             }


            // Устанавливаем маркеры, используя createSeriesMarkers
            // Проверяем, что candlestickSeries действителен и есть данные маркеров
            if (candlestickSeries && chartData.markers && chartData.markers.length > 0) {
                 console.log(`loadChartData: Получено ${chartData.markers.length} маркеров.`); // Логируем количество маркеров
                 const formattedMarkers = formatMarkerData(chartData.markers);
                 // Используем createSeriesMarkers как показано в документации
                 // Assuming createSeriesMarkers is available globally or via LightweightCharts object
                 if (typeof LightweightCharts.createSeriesMarkers === 'function') {
                     LightweightCharts.createSeriesMarkers(candlestickSeries, formattedMarkers);
                      console.log('loadChartData: Маркеры установлены через createSeriesMarkers.'); // Логируем установку маркеров
                 } else {
                     console.error('loadChartData: LightweightCharts.createSeriesMarkers не является функцией.');
                     // Fallback: если createSeriesMarkers недоступен, попробуем setMarkers (хотя это старый метод)
                     if (typeof candlestickSeries.setMarkers === 'function') {
                          console.warn('loadChartData: Используется устаревший метод setMarkers для маркеров.');
                          candlestickSeries.setMarkers(formattedMarkers);
                           console.log('loadChartData: Маркеры установлены через setMarkers (fallback).'); // Логируем установку маркеров
                     } else {
                          console.error('loadChartData: Невозможно установить маркеры: createSeriesMarkers и setMarkers недоступны.');
                     }
                 }

            } else if (candlestickSeries && typeof LightweightCharts.createSeriesMarkers === 'function') {
                 // Если данных маркеров нет, но createSeriesMarkers доступен, очищаем маркеры
                 console.log('loadChartData: Нет данных маркеров, очищаем через createSeriesMarkers.'); // Логируем очистку маркеров
                 LightweightCharts.createSeriesMarkers(candlestickSeries, []);
            } else if (candlestickSeries && typeof candlestickSeries.setMarkers === 'function') {
                 // Fallback для очистки маркеров с использованием старого метода
                 console.warn('loadChartData: Используется устаревший метод setMarkers для очистки маркеров.');
                 candlestickSeries.setMarkers([]);
                  console.log('loadChartData: Маркеры очищены через setMarkers (fallback).'); // Логируем очистку маркеров
            } else {
                 console.error('loadChartData: Невозможно очистить маркеры: createSeriesMarkers и setMarkers недоступны.');
            }


            chart.timeScale().fitContent();
             console.log('loadChartData: График подогнан по содержимому.'); // Логируем подгонку
        } else {
            console.warn(`loadChartData: Нет данных для отображения графика для таймфрейма ${timeframe}.`); // Логируем отсутствие данных
             // Проверяем, что candlestickSeries действителен перед очисткой
             if (candlestickSeries && typeof candlestickSeries.setData === 'function') {
                 candlestickSeries.setData([]); // Очищаем график, если нет данных
                  console.log('loadChartData: График очищен.'); // Логируем очистку графика
             }
             // Очищаем маркеры, используя createSeriesMarkers или setMarkers
             if (candlestickSeries && typeof LightweightCharts.createSeriesMarkers === 'function') {
                 LightweightCharts.createSeriesMarkers(candlestickSeries, []);
                  console.log('loadChartData: Маркеры очищены через createSeriesMarkers.'); // Логируем очистку маркеров
             } else if (candlestickSeries && typeof candlestickSeries.setMarkers === 'function') {
                 console.warn('loadChartData: Используется устаревший метод setMarkers для очистки маркеров при отсутствии данных.');
                 candlestickSeries.setMarkers([]);
                  console.log('loadChartData: Маркеры очищены через setMarkers (fallback).'); // Логируем очистку маркеров
             } else {
                 console.error('loadChartData: Невозможно очистить маркеры при отсутствии данных: createSeriesMarkers и setMarkers недоступны.');
             }
        }
         console.log(`loadChartData: Завершение загрузки данных для таймфрейма: ${timeframe}`); // Логируем завершение
    }

    // Обработчик изменения выбора таймфрейма
    if (timeframeSelect) {
        timeframeSelect.addEventListener('change', (event) => {
            const selectedTimeframe = event.target.value;
            loadChartData(selectedTimeframe); // Загружаем данные для нового таймфрейма
        });
    }


    // Инициализация: загружаем данные для таймфрейма по умолчанию (1h)
    const defaultTimeframe = timeframeSelect ? timeframeSelect.value : '1h';
    loadChartData(defaultTimeframe);


    // Обработчик изменения размера окна для адаптивности
    new ResizeObserver(entries => {
        if (entries.length === 0 || entries[0].target !== chartContainer) {
            return;
        }
        const newRect = entries[0].contentRect;
        chart.applyOptions({ height: newRect.height, width: newRect.width });
    }).observe(chartContainer);

});
