// front/js/script.js

window.addEventListener('load', () => {
    const chartContainer = document.getElementById('chart-container'); // Сам график
    const chartContainerWrapper = document.getElementById('chart-container-wrapper'); // Обертка для графика
    const timeframeSelect = document.getElementById('timeframe-select');
    const backtestDateInput = document.getElementById('backtest-date');
    
    // Кнопки инструментов на новой вертикальной панели
    const toolPointerButton = document.getElementById('tool-pointer');
    const toolTrendlineButton = document.getElementById('tool-trendline');
    // const toolHorizontalLineButton = document.getElementById('tool-horizontal-line'); 
    const clearDrawnLinesButton = document.getElementById('clear-drawn-lines');

    // Контейнеры для сводки анализа
    const generalSummaryDiv = document.getElementById('analysis-summary-general');
    const detailedSummaryDiv = document.getElementById('analysis-summary-detailed');
    const targetsSummaryDiv = document.getElementById('analysis-summary-targets');
    const entryPointsSummaryDiv = document.getElementById('analysis-summary-entry-points');
    const otherSummaryDiv = document.getElementById('analysis-summary-other');

    if (!chartContainer || !chartContainerWrapper || !toolTrendlineButton || !clearDrawnLinesButton || !toolPointerButton) {
        console.error('Один или несколько необходимых HTML элементов не найдены!');
        return;
    }
    if (typeof LightweightCharts === 'undefined') {
        console.error('Библиотека LightweightCharts не загружена.');
        return;
    }

    let chart = null;
    let candlestickSeries = null;
    let serverTrendLineSeries = []; 
    let userDrawnLineSeries = [];   
    
    let currentDrawingTool = 'pointer'; 
    let firstClickPoint = null; 

    // Собираем кнопки инструментов в массив для удобного управления их состоянием
    const drawingToolButtons = [];
    if (toolPointerButton) drawingToolButtons.push(toolPointerButton);
    if (toolTrendlineButton) drawingToolButtons.push(toolTrendlineButton);
    // if (toolHorizontalLineButton) drawingToolButtons.push(toolHorizontalLineButton);


    function setActiveTool(selectedToolId) {
        currentDrawingTool = selectedToolId;
        drawingToolButtons.forEach(button => {
            if (button.id === `tool-${selectedToolId}`) { // Сравниваем ID кнопки с ID инструмента
                button.classList.add('active');
            } else {
                button.classList.remove('active');
            }
        });
        chartContainer.style.cursor = (currentDrawingTool === 'pointer') ? 'default' : 'crosshair';
        firstClickPoint = null; 
        console.log("Активный инструмент:", currentDrawingTool);
    }


    try {
        chart = LightweightCharts.createChart(chartContainer, { // Создаем график в #chart-container
            width: chartContainer.clientWidth,
            height: chartContainer.clientHeight,
            layout: { background: { color: '#FFFFFF' }, textColor: '#000000' },
            grid: { vertLines: { color: '#E0E0E0' }, horzLines: { color: '#E0E0E0' } },
            timeScale: { timeVisible: true, secondsVisible: false, borderColor: '#B0B0B0' },
            crosshair: { mode: LightweightCharts.CrosshairMode.Normal },
            priceScale: { borderColor: '#B0B0B0' },
        });

        // ИСПРАВЛЕНИЕ: Используем chart.addSeries для CandlestickSeries
        candlestickSeries = chart.addSeries(LightweightCharts.CandlestickSeries, {
            upColor: '#26A69A', downColor: '#EF5350',
            borderVisible: false, wickColor: '#7F8C8D',
            wickUpColor: '#26A69A', wickDownColor: '#EF5350',
        });

    } catch (e) {
        console.error('Ошибка при создании графика LightweightCharts:', e);
        return;
    }

    // --- ЛОГИКА РИСОВАНИЯ ЛИНИЙ ---
    if(toolPointerButton) toolPointerButton.addEventListener('click', () => setActiveTool('pointer'));
    if(toolTrendlineButton) toolTrendlineButton.addEventListener('click', () => setActiveTool('trendline'));
    // if (toolHorizontalLineButton) toolHorizontalLineButton.addEventListener('click', () => setActiveTool('horizontal'));
    
    clearDrawnLinesButton.addEventListener('click', () => {
        userDrawnLineSeries.forEach(line => chart.removeSeries(line));
        userDrawnLineSeries = [];
        console.log("Все нарисованные пользователем линии удалены.");
    });

    chart.subscribeClick(param => {
        if (currentDrawingTool === 'pointer' || !candlestickSeries) {
            return;
        }
        if (!param.point || typeof param.time !== 'number') {
            console.warn("Невалидные параметры клика для рисования.", param);
            firstClickPoint = null; 
            return;
        }
        
        const price = candlestickSeries.coordinateToPrice(param.point.y);
        const time = param.time; 

        if (price === null) { 
            console.warn("Не удалось преобразовать координату Y клика в цену.");
            firstClickPoint = null; 
            return;
        }
        
        // console.log(`Рисование: Клик -> Время=${time}, Цена=${price}, Инструмент=${currentDrawingTool}`);
        
        if (currentDrawingTool === 'trendline') {
            if (!firstClickPoint) {
                firstClickPoint = { time, price }; 
                // console.log("Линия тренда: Первая точка установлена:", firstClickPoint);
            } else {
                if (typeof firstClickPoint.time !== 'number') { 
                    console.error("Ошибка: Сохраненное firstClickPoint.time не является числом!", firstClickPoint);
                    firstClickPoint = null; 
                    return;
                }
                // console.log("Линия тренда: Вторая точка установлена:", { time, price });

                // Используем chart.addSeries(...) для пользовательских линий
                const userLine = chart.addSeries(LightweightCharts.LineSeries, {
                    color: 'purple', 
                    lineWidth: 2,
                    lineStyle: LightweightCharts.LineStyle.Dashed, 
                    lastValueVisible: false,
                    priceLineVisible: false,
                });
                
                userLine.setData([
                    { time: firstClickPoint.time, value: firstClickPoint.price },
                    { time: time, value: price } 
                ]);
                userDrawnLineSeries.push(userLine);
                // console.log("Линия тренда: Линия нарисована.");
                firstClickPoint = null; 
                // setActiveTool('pointer'); // Опционально: возвращаться к курсору после рисования
            }
        } 
    });


    // --- СУЩЕСТВУЮЩАЯ ЛОГИКА ЗАГРУЗКИ ДАННЫХ И ОТОБРАЖЕНИЯ ---
    async function fetchChartData(timeframe, backtestDate = null) {
        try {
            let url = `/api/chart_data?interval=${timeframe}`;
            if (backtestDate) {
                url += `&endDate=${backtestDate}`;
            }
            const response = await fetch(url);
            if (!response.ok) {
                console.error(`fetchChartData: Ошибка HTTP! статус: ${response.status}`);
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            const data = await response.json();
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
        return formattedData;
    }

    function formatMarkerData(data) {
         const markerMap = {
             'HH': { shape: 'circle', color: 'blue', position: 'aboveBar', text: 'HH', size: 0 },
             'HL': { shape: 'circle', color: 'green', position: 'belowBar', text: 'HL', size: 0 },
             'LH': { shape: 'circle', color: 'red', position: 'aboveBar', text: 'LH', size: 0 },
             'LL': { shape: 'circle', color: 'purple', position: 'belowBar', text: 'LL', size: 0 },
             'H': { shape: 'circle', color: '#808080', position: 'aboveBar', size: 0, text: 'H' },
             'L': { shape: 'circle', color: '#808080', position: 'belowBar', size: 0, text: 'L' },
             'F_H_AS': { shape: 'arrowDown', color: 'darkorange', position: 'aboveBar', text: '', size: 0.8 },
             'F_L_AS': { shape: 'arrowUp', color: 'darkorange', position: 'belowBar', text: '', size: 0.8 },
             'F_H_NY1': { shape: 'arrowDown', color: 'dodgerblue', position: 'aboveBar', text: '', size: 0.8 },
             'F_L_NY1': { shape: 'arrowUp', color: 'dodgerblue', position: 'belowBar', text: '', size: 0.8 },
             'F_H_NY2': { shape: 'arrowDown', color: 'deepskyblue', position: 'aboveBar', text: '', size: 0.8 }, 
             'F_L_NY2': { shape: 'arrowUp', color: 'deepskyblue', position: 'belowBar', text: '', size: 0.8 },   
             'SETUP_Resist': { shape: 'square', color: '#000000', position: 'aboveBar', text: 'SR', size: 1.2 }, 
             'SETUP_Support': { shape: 'square', color: '#000000', position: 'belowBar', text: 'SS', size: 1.2 },
             'UNKNOWN_SETUP': { shape: 'circle', color: '#A9A9A9', position: 'aboveBar', text: '?', size: 1 }, 
         };
         const filteredData = data.filter(item => markerMap.hasOwnProperty(item.type));
         return filteredData.map(item => {
             const markerType = markerMap[item.type];
             return {
                 time: new Date(item.time).getTime() / 1000, 
                 position: markerType.position,
                 color: markerType.color, 
                 shape: markerType.shape,
                 text: markerType.text !== undefined ? markerType.text : item.type,
                 size: markerType.size !== undefined ? markerType.size : 1, 
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
            lineStyle: line.lineStyle !== undefined ? line.lineStyle : LightweightCharts.LineStyle.Solid, 
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
        const chartData = await fetchChartData(timeframe, backtestDate);

        serverTrendLineSeries.forEach(series => {
            if (chart && series) chart.removeSeries(series);
        });
        serverTrendLineSeries = [];

        if (candlestickSeries) {
            if (typeof LightweightCharts.createSeriesMarkers === 'function') {
                LightweightCharts.createSeriesMarkers(candlestickSeries, []);
            } else if (typeof candlestickSeries.setMarkers === 'function') {
                candlestickSeries.setMarkers([]);
            }
        }

        if (chartData && chartData.ohlcv && chartData.ohlcv.length > 0) {
            const formattedOhlcv = formatOhlcvData(chartData.ohlcv);
            if (candlestickSeries) candlestickSeries.setData(formattedOhlcv);

            if (chartData.markers && chartData.markers.length > 0) {
                const formattedMarkers = formatMarkerData(chartData.markers);
                if (typeof LightweightCharts.createSeriesMarkers === 'function') {
                    LightweightCharts.createSeriesMarkers(candlestickSeries, formattedMarkers);
                } else if (typeof candlestickSeries.setMarkers === 'function') {
                    candlestickSeries.setMarkers(formattedMarkers);
                }
            }

            if (chartData.trendLines && chartData.trendLines.length > 0) {
                const formattedTrendLines = formatTrendLineData(chartData.trendLines);
                formattedTrendLines.forEach(lineDef => {
                    // Используем chart.addSeries(...) для серверных линий
                    const lineSeries = chart.addSeries(LightweightCharts.LineSeries, {
                        color: lineDef.color, 
                        lineWidth: lineDef.lineWidth,
                        lineStyle: lineDef.lineStyle, 
                        crosshairMarkerVisible: lineDef.crosshairMarkerVisible,
                        lastValueVisible: lineDef.lastValueVisible, 
                        priceLineVisible: lineDef.priceLineVisible,
                    });
                    lineSeries.setData(lineDef.data);
                    serverTrendLineSeries.push(lineSeries);
                });
            }
            if (chart && chart.timeScale()) chart.timeScale().fitContent();
        } else {
            if (candlestickSeries) candlestickSeries.setData([]);
        }
        displayAnalysisSummary(chartData ? chartData.analysisSummary : null);
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
    
    setActiveTool('pointer'); 

    loadChartData(timeframeSelect ? timeframeSelect.value : '1h');

    const resizeObserver = new ResizeObserver(entries => {
        if (entries.length === 0 || entries[0].target !== chartContainerWrapper) return; 
        const newRect = entries[0].contentRect;
        if (chart) {
             chart.applyOptions({ height: newRect.height, width: newRect.width });
        }
    });
    resizeObserver.observe(chartContainerWrapper); 
});
