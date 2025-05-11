// front/js/script.js

// Изменяем слушатель события с DOMContentLoaded на window.load
window.addEventListener('load', () => {
    const chartContainer = document.getElementById('chart-container');
    const timeframeSelect = document.getElementById('timeframe-select'); // Получаем элемент select
    const backtestDateInput = document.getElementById('backtest-date'); // Получаем элемент выбора даты

    // Получаем ссылки на контейнеры для каждой секции сводки анализа
    const generalSummaryDiv = document.getElementById('analysis-summary-general');
    const detailedSummaryDiv = document.getElementById('analysis-summary-detailed');
    const targetsSummaryDiv = document.getElementById('analysis-summary-targets');
    const entryPointsSummaryDiv = document.getElementById('analysis-summary-entry-points');
    const otherSummaryDiv = document.getElementById('analysis-summary-other');


    if (!chartContainer) {
        console.error('Контейнер для графика не найден!');
        return;
    }

    // Добавляем проверку, что LightweightCharts доступен
    if (typeof LightweightCharts === 'undefined') {
        console.error('Библиотека LightweightCharts не загружена.');
        return;
    }

    let chart = null; // Объявляем chart здесь
    let candlestickSeries = null; // Объявляем candlestickSeries здесь
    let trendLineSeries = []; // Массив для хранения серий линий тренда

    try {
        // Создаем экземпляр графика
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
                timezone: 'UTC',
            },
            crosshair: {
                mode: LightweightCharts.CrosshairMode.Normal,
            },
            priceScale: {
                borderColor: '#B0B0B0', // Цвет границы ценовой шкалы (темнее серого)
            },
        });

        if (!chart) {
             console.error('Не удалось создать экземпляр графика LightweightCharts.');
             return;
        }

        candlestickSeries = chart.addSeries(LightweightCharts.CandlestickSeries, {
            upColor: '#26A69A',
            downColor: '#EF5350',
            borderVisible: false,
            wickColor: '#7F8C8D',
            wickUpColor: '#26A69A',
            wickDownColor: '#EF5350',
        });

        if (!candlestickSeries) {
             console.error('Не удалось создать серию свечей.');
             return;
        }

    } catch (e) {
        console.error('Ошибка при создании графика или серии LightweightCharts:', e);
        return;
    }

    async function fetchChartData(timeframe, backtestDate = null) {
        try {
            let url = `/api/chart_data?interval=${timeframe}`;
            if (backtestDate) {
                url += `&endDate=${backtestDate}`;
            }
            console.log(`fetchChartData: Запрос к URL: ${url}`);
            const response = await fetch(url);
            if (!response.ok) {
                console.error(`fetchChartData: Ошибка HTTP! статус: ${response.status}`);
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            const data = await response.json();
            console.log('fetchChartData: Получены данные:', data);
            return data;
        } catch (error) {
            console.error('fetchChartData: Ошибка при получении данных графика:', error);
            return { ohlcv: [], markers: [], trendLines: [], analysisSummary: {"Общая информация": [], "Подробная информация": [], "Цели": [], "Точки набора": [], "Другое": []} };
        }
    }

    function formatOhlcvData(data) {
        const formattedData = data.map(item => ({
            time: new Date(item.time).getTime() / 1000,
            open: parseFloat(item.open),
            high: parseFloat(item.high),
            low: parseFloat(item.low),
            close: parseFloat(item.close),
        }));
        console.log('formatOhlcvData: Первые 5 отформатированных временных меток (Unix Timestamp в секундах):', formattedData.slice(0, 5).map(item => item.time));
        return formattedData;
    }

    function formatMarkerData(data) {
         const markerMap = {
             // --- МАРКЕРЫ СТРУКТУРЫ РЫНКА (HH, HL, LH, LL) - ТЕПЕРЬ "ТОЛЬКО ТЕКСТ" ---
             // Форма сделана очень маленьким кружком (size: 0), чтобы была почти невидима
             'HH': { shape: 'circle', color: 'blue', position: 'aboveBar', text: 'HH', size: 0 },
             'HL': { shape: 'circle', color: 'green', position: 'belowBar', text: 'HL', size: 0 },
             'LH': { shape: 'circle', color: 'red', position: 'aboveBar', text: 'LH', size: 0 },
             'LL': { shape: 'circle', color: 'purple', position: 'belowBar', text: 'LL', size: 0 },

             // Простые максимумы/минимумы (H, L) - также "только текст"
             'H': { shape: 'circle', color: '#808080', position: 'aboveBar', size: 0, text: 'H' },
             'L': { shape: 'circle', color: '#808080', position: 'belowBar', size: 0, text: 'L' },

             // Сетапы УДАЛЕНЫ по запросу пользователя
             // 'SETUP_Resist': { shape: 'square', color: '#000000', position: 'aboveBar', size: 1.5 },
             // 'SETUP_Support': { shape: 'square', color: '#000000', position: 'belowBar', size: 1.5 },
             // 'UNKNOWN_SETUP': { shape: 'circle', color: '#808080', position: 'aboveBar' },

             // --- МАРКЕРЫ ДЛЯ СЕССИОННЫХ ФРАКТАЛОВ (ТРЕУГОЛЬНИКИ БЕЗ ТЕКСТА) ---
             'F_H_AS': { shape: 'arrowDown', color: 'darkorange', position: 'aboveBar', text: '', size: 0.8 },
             'F_L_AS': { shape: 'arrowUp', color: 'darkorange', position: 'belowBar', text: '', size: 0.8 },
             'F_H_NY1': { shape: 'arrowDown', color: 'dodgerblue', position: 'aboveBar', text: '', size: 0.8 },
             'F_L_NY1': { shape: 'arrowUp', color: 'dodgerblue', position: 'belowBar', text: '', size: 0.8 },
         };

         const filteredData = data.filter(item => markerMap.hasOwnProperty(item.type));

         return filteredData.map(item => {
             const markerType = markerMap[item.type];
             return {
                 time: new Date(item.time).getTime() / 1000,
                 position: markerType.position,
                 color: markerType.color, // Этот цвет будет применен к тексту и крошечной форме
                 shape: markerType.shape,
                 text: markerType.text !== undefined ? markerType.text : item.type,
                 size: markerType.size !== undefined ? markerType.size : 1, // Используем size из карты, если есть, иначе 1
             };
         });
     }

    function formatTrendLineData(data) {
        return data.map(line => ({
            data: [
                { time: new Date(line.start_time).getTime() / 1000, value: line.start_price },
                { time: new Date(line.end_time).getTime() / 1000, value: line.end_price }
            ],
            color: line.color || '#000000',
            lineWidth: 2,
            lineStyle: line.lineStyle !== undefined ? line.lineStyle : 0,
            crosshairMarkerVisible: false,
            lastValueVisible: false,
            priceLineVisible: false,
        }));
    }

    function displayAnalysisSummary(summaryData) {
        if (generalSummaryDiv) generalSummaryDiv.querySelector('ul').innerHTML = '';
        if (detailedSummaryDiv) detailedSummaryDiv.querySelector('ul').innerHTML = '';
        if (targetsSummaryDiv) targetsSummaryDiv.querySelector('ul').innerHTML = '';
        if (entryPointsSummaryDiv) entryPointsSummaryDiv.querySelector('ul').innerHTML = '';
        if (otherSummaryDiv) otherSummaryDiv.querySelector('ul').innerHTML = '';

        const sectionContainers = {
            'Общая информация': generalSummaryDiv,
            'Подробная информация': detailedSummaryDiv,
            'Цели': targetsSummaryDiv,
            'Точки набора': entryPointsSummaryDiv,
            'Другое': otherSummaryDiv
        };

        if (summaryData) {
            for (const section in summaryData) {
                if (sectionContainers[section] && summaryData[section] && Array.isArray(summaryData[section])) {
                    const ulElement = sectionContainers[section].querySelector('ul');
                    if (ulElement) { 
                        if (summaryData[section].length > 0) {
                            summaryData[section].forEach(item => {
                                const listItem = document.createElement('li');
                                listItem.classList.add('flex', 'items-center', 'mb-1');
                                const statusIcon = document.createElement('span');
                                statusIcon.classList.add('mr-2', item.status ? 'text-green-500' : 'text-red-500');
                                statusIcon.textContent = item.status ? '✓' : '✗';
                                const description = document.createElement('span');
                                description.textContent = item.description;

                                listItem.appendChild(statusIcon);
                                listItem.appendChild(description);
                                ulElement.appendChild(listItem);
                            });
                        } else {
                             const listItem = document.createElement('li');
                             listItem.textContent = `Нет данных для секции "${section}".`;
                             ulElement.appendChild(listItem);
                        }
                    }
                }
            }
        } else {
             for (const section in sectionContainers) {
                 if (sectionContainers[section]) {
                     const ulElement = sectionContainers[section].querySelector('ul');
                     if (ulElement) { 
                        const listItem = document.createElement('li');
                        listItem.textContent = 'Нет данных сводки анализа.';
                        ulElement.appendChild(listItem);
                     }
                 }
             }
        }
    }

    async function loadChartData(timeframe, backtestDate = null) {
        console.log(`loadChartData: Начало загрузки данных для таймфрейма: ${timeframe} до даты: ${backtestDate || 'последняя доступная'}`);
        const chartData = await fetchChartData(timeframe, backtestDate);
        console.log('loadChartData: Данные получены из fetchChartData:', chartData);

        trendLineSeries.forEach(series => {
            if (chart && series) {
                chart.removeSeries(series);
            }
        });
        trendLineSeries = [];

        if (chartData && chartData.ohlcv && chartData.ohlcv.length > 0) {
            console.log(`loadChartData: Получено ${chartData.ohlcv.length} свечей.`);
            const formattedOhlcv = formatOhlcvData(chartData.ohlcv);
            if (candlestickSeries && typeof candlestickSeries.setData === 'function') {
                candlestickSeries.setData(formattedOhlcv);
                console.log('loadChartData: Данные свечей установлены.');
            } else {
                console.error('loadChartData: candlestickSeries недействителен или не имеет метода setData.');
                displayAnalysisSummary(chartData.analysisSummary);
                return;
            }

            if (candlestickSeries && chartData.markers && chartData.markers.length > 0) {
                console.log(`loadChartData: Получено ${chartData.markers.length} маркеров.`);
                const formattedMarkers = formatMarkerData(chartData.markers);
                if (typeof LightweightCharts.createSeriesMarkers === 'function') {
                    LightweightCharts.createSeriesMarkers(candlestickSeries, formattedMarkers);
                    console.log('loadChartData: Маркеры установлены через createSeriesMarkers.');
                } else if (typeof candlestickSeries.setMarkers === 'function') {
                    console.warn('loadChartData: Используется устаревший метод setMarkers для маркеров.');
                    candlestickSeries.setMarkers(formattedMarkers);
                    console.log('loadChartData: Маркеры установлены через setMarkers (fallback).');
                } else {
                    console.error('loadChartData: Невозможно установить маркеры: createSeriesMarkers и setMarkers недоступны.');
                }
            } else if (candlestickSeries) { 
                 const clearMarkersFunction = LightweightCharts.createSeriesMarkers || candlestickSeries.setMarkers;
                 if (clearMarkersFunction && typeof clearMarkersFunction === 'function') {
                    console.log('loadChartData: Нет данных маркеров, очищаем маркеры.');
                    if (LightweightCharts.createSeriesMarkers) { 
                        LightweightCharts.createSeriesMarkers(candlestickSeries, []);
                    } else {
                        candlestickSeries.setMarkers([]); 
                    }
                 } else {
                    console.error('loadChartData: Невозможно очистить маркеры.');
                 }
            }


            if (chartData.trendLines && chartData.trendLines.length > 0) {
                console.log(`loadChartData: Получено ${chartData.trendLines.length} линий тренда.`);
                const formattedTrendLines = formatTrendLineData(chartData.trendLines);
               
                    formattedTrendLines.forEach(lineData => {
                        const lineSeries = chart.addSeries(LightweightCharts.LineSeries, {
                            color: lineData.color,
                            lineWidth: lineData.lineWidth,
                            lineStyle: lineData.lineStyle,
                            crosshairMarkerVisible: lineData.crosshairMarkerVisible,
                            lastValueVisible: lineData.lastValueVisible,
                            priceLineVisible: lineData.priceLineVisible,
                        });
                        lineSeries.setData(lineData.data);
                        trendLineSeries.push(lineSeries);
                    });
                    console.log('loadChartData: Серии линий тренда добавлены.');
            }

            displayAnalysisSummary(chartData.analysisSummary);
            console.log('loadChartData: Сводка анализа отображена.');

            chart.timeScale().fitContent();
            console.log('loadChartData: График подогнан по содержимому.');
        } else {
            console.warn(`loadChartData: Нет данных для отображения графика для таймфрейма ${timeframe} до даты ${backtestDate || 'последняя доступная'}.`);
            if (candlestickSeries && typeof candlestickSeries.setData === 'function') {
                candlestickSeries.setData([]);
                console.log('loadChartData: График очищен.');
            }
             if (candlestickSeries) { 
                 const clearMarkersFunction = LightweightCharts.createSeriesMarkers || candlestickSeries.setMarkers;
                 if (clearMarkersFunction && typeof clearMarkersFunction === 'function') { 
                    console.log('loadChartData: Нет данных графика, очищаем маркеры.');
                     if (LightweightCharts.createSeriesMarkers) { 
                        LightweightCharts.createSeriesMarkers(candlestickSeries, []);
                    } else {
                        candlestickSeries.setMarkers([]); 
                    }
                 } else {
                    console.error('loadChartData: Невозможно очистить маркеры при отсутствии данных графика.');
                 }
            }
            trendLineSeries.forEach(series => {
                if (chart && series) {
                    chart.removeSeries(series);
                }
            });
            trendLineSeries = [];
            console.log('loadChartData: Серии линий тренда очищены.');
            displayAnalysisSummary(chartData ? chartData.analysisSummary : null);
            console.log('loadChartData: Сводка анализа отображена (нет данных графика).');
        }
        console.log(`loadChartData: Завершение загрузки данных для таймфрейма: ${timeframe} до даты: ${backtestDate || 'последняя доступная'}`);
    }

    if (timeframeSelect) {
        timeframeSelect.addEventListener('change', () => {
            const selectedTimeframe = timeframeSelect.value;
            const selectedDate = backtestDateInput.value;
            loadChartData(selectedTimeframe, selectedDate);
        });
    }

    if (backtestDateInput) {
        backtestDateInput.addEventListener('change', () => {
            const selectedTimeframe = timeframeSelect.value;
            const selectedDate = backtestDateInput.value;
            loadChartData(selectedTimeframe, selectedDate);
        });
    }

    const defaultTimeframe = timeframeSelect ? timeframeSelect.value : '1h';
    loadChartData(defaultTimeframe);

    new ResizeObserver(entries => {
        if (entries.length === 0 || entries[0].target !== chartContainer) {
            return;
        }
        const newRect = entries[0].contentRect;
        chart.applyOptions({ height: newRect.height, width: newRect.width });
    }).observe(chartContainer);
});
