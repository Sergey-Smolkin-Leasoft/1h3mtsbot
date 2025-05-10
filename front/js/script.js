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
    let trendLineSeries = []; // Массив для хранения серий линий тренда

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
                // Явно указываем таймзону UTC
                timezone: 'UTC',
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
            return { ohlcv: [], markers: [], trendLines: [] }; // Возвращаем пустой массив для trendLines по умолчанию
        }
    }

    // Функция для форматирования данных OHLCV для Lightweight Charts
    function formatOhlcvData(data) {
        const formattedData = data.map(item => ({
            // Преобразуем в timestamp в секундах.
            // Важно, чтобы исходное время в item.time было в UTC, если мы указываем timezone: 'UTC' в настройках графика.
            time: new Date(item.time).getTime() / 1000,
            open: parseFloat(item.open),
            high: parseFloat(item.high),
            low: parseFloat(item.low),
            close: parseFloat(item.close),
        }));
        // Логируем первые несколько отформатированных точек времени
        console.log('formatOhlcvData: Первые 5 отформатированных временных меток (Unix Timestamp в секундах):', formattedData.slice(0, 5).map(item => item.time));
        return formattedData;
    }

    // Функция для форматирования данных маркеров для Lightweight Charts
    function formatMarkerData(data) {
         // Улучшенная карта маркеров для точек структуры
         const markerMap = {
             // Точки тренда (HH, HL, LH, LL) - делаем их более заметными
             'HH': { shape: 'arrowUp', color: '#2962FF', position: 'aboveBar', size: 1.5 }, // HH - Синяя стрелка вверх, больше размер
             'HL': { shape: 'circle', color: '#26A69A', position: 'belowBar', size: 1.2 },   // HL - Зеленый круг, средний размер
             'LH': { shape: 'arrowDown', color: '#FF0000', position: 'belowBar', size: 1.5 }, // LH - Красная стрелка вниз, больше размер
             'LL': { shape: 'circle', color: '#FF0000', position: 'aboveBar', size: 1.2 },   // LL - Красный круг, средний размер

             // Простые максимумы/минимумы (H, L) - менее заметные
             'H': { shape: 'square', color: '#808080', position: 'aboveBar', size: 1 },    // H - Серый квадрат, стандартный размер
             'L': { shape: 'square', color: '#808080', position: 'belowBar', size: 1 },    // L - Серый квадрат, стандартный размер

             // Сессионные фракталы (можно оставить как есть или настроить)
             'F_H_AS': { shape: 'circle', color: '#FFA500', position: 'aboveBar' }, // Оранжевый
             'F_L_AS': { shape: 'circle', color: '#FFA500', position: 'belowBar' }, // Оранжевый
             'F_H_NY1': { shape: 'circle', color: '#1E90FF', position: 'aboveBar' }, // Голубой
             'F_L_NY1': { shape: 'circle', color: '#1E90FF', position: 'belowBar' }, // Голубой

             // Сетапы (можно оставить как есть или настроить)
             'SETUP_Resist': { shape: 'square', color: '#000000', position: 'aboveBar', size: 1.5 }, // Черный квадрат, больше размер
             'SETUP_Support': { shape: 'square', color: '#000000', position: 'belowBar', size: 1.5 }, // Черный квадрат, больше размер
             'UNKNOWN_SETUP': { shape: 'circle', color: '#808080', position: 'aboveBar' } // Серый
         };

         return data.map(item => {
             const markerType = markerMap[item.type] || { shape: 'circle', color: '#808080', position: 'aboveBar' }; // Дефолтный маркер
             return {
                 time: new Date(item.time).getTime() / 1000, // Преобразуем в timestamp в секундах
                 position: markerType.position,
                 color: markerType.color,
                 shape: markerType.shape,
                 text: item.type,
                 size: markerType.size || 1, // Размер маркера, по умолчанию 1
             };
         });
     }

    // Функция для форматирования данных линий тренда для Lightweight Charts
    function formatTrendLineData(data) {
        return data.map(line => ({
            // Lightweight Charts ожидает массив точек для LineSeries
            data: [
                { time: new Date(line.start_time).getTime() / 1000, value: line.start_price },
                { time: new Date(line.end_time).getTime() / 1000, value: line.end_price }
            ],
            color: line.color || '#000000', // Цвет линии, по умолчанию черный
            lineWidth: 2, // Толщина линии
            // Используем числовое значение для LineStyle, полученное с бэкенда
            lineStyle: line.lineStyle !== undefined ? line.lineStyle : 0, // По умолчанию Solid (0)
            crosshairMarkerVisible: false, // Скрыть маркер на линии при наведении
            lastValueVisible: false, // Скрыть последнее значение на линии
            priceLineVisible: false, // Скрыть горизонтальную линию цены
        }));
    }


    // Функция для загрузки и отображения данных графика
    async function loadChartData(timeframe) {
        console.log(`loadChartData: Начало загрузки данных для таймфрейма: ${timeframe}`); // Логируем начало
        const chartData = await fetchChartData(timeframe);
        console.log('loadChartData: Данные получены из fetchChartData:', chartData); // Логируем данные после fetch

        // Очищаем старые серии линий тренда перед добавлением новых
        trendLineSeries.forEach(series => {
            if (chart && series) {
                chart.removeSeries(series);
            }
        });
        trendLineSeries = []; // Очищаем массив ссылок

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

            // Добавляем линии тренда
            if (chartData.trendLines && chartData.trendLines.length > 0) {
                console.log(`loadChartData: Получено ${chartData.trendLines.length} линий тренда.`);
                const formattedTrendLines = formatTrendLineData(chartData.trendLines);

                // Явная проверка, что chart.addLineSeries является функцией перед использованием
                if (chart && typeof chart.addSeries === 'function') {
                    formattedTrendLines.forEach(lineData => {
                        const lineSeries = chart.addSeries({
                            color: lineData.color,
                            lineWidth: lineData.lineWidth,
                            lineStyle: lineData.lineStyle, // Теперь используем числовое значение
                            crosshairMarkerVisible: lineData.crosshairMarkerVisible,
                            lastValueVisible: lineData.lastValueVisible,
                            priceLineVisible: lineData.priceLineVisible,
                        });
                        lineSeries.setData(lineData.data);
                        trendLineSeries.push(lineSeries); // Сохраняем ссылку на серию линии
                        console.log('loadChartData: Серия линии тренда добавлена.');
                    });
                } else {
                    console.error('loadChartData: chart.addLineSeries не является функцией. Невозможно добавить линии тренда.');
                }

            } else {
                console.log('loadChartData: Нет данных для линий тренда.');
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
             if (typeof LightweightCharts.createSeriesMarkers === 'function') {
                 LightweightCharts.createSeriesMarkers(candlestickSeries, []);
                  console.log('loadChartData: Маркеры очищены через createSeriesMarkers.'); // Логируем очистку маркеров
             } else if (candlestickSeries && typeof candlestickSeries.setMarkers === 'function') {
                 console.warn('loadChartData: Используется устаревший метод setMarkers для очистки маркеров при отсутствии данных.');
                 candlestickSeries.setMarkers([]);
                  console.log('loadChartData: Маркеры очищены через setMarkers (fallback).'); // Логируем очистку маркеров
             } else {
                 console.error('loadChartData: Невозможно очистить маркеры при отсутствии данных: createSeriesMarkers и setMarkers недоступны.');
             }
             // Очищаем серии линий тренда, если они были
             trendLineSeries.forEach(series => {
                 if (chart && series) {
                     chart.removeSeries(series);
                 }
             });
             trendLineSeries = [];
             console.log('loadChartData: Серии линий тренда очищены.');
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
