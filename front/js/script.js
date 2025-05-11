// front/js/script.js

window.addEventListener('load', () => {
    // Получаем необходимые элементы DOM
    const chartContainer = document.getElementById('chart-container'); 
    const chartContainerWrapper = document.getElementById('chart-container-wrapper'); 
    const timeframeSelect = document.getElementById('timeframe-select');
    const backtestDateInput = document.getElementById('backtest-date');
    
    const toolPointerButton = document.getElementById('tool-pointer');
    const toolTrendlineButton = document.getElementById('tool-trendline');
    const clearDrawnLinesButton = document.getElementById('clear-drawn-lines');

    const contextAnalysisSectionDiv = document.getElementById('analysis-context-section'); 

    if (!chartContainer || !chartContainerWrapper || !toolTrendlineButton || !clearDrawnLinesButton || !toolPointerButton || !contextAnalysisSectionDiv) {
        console.error('Один или несколько необходимых HTML элементов не найдены! Убедитесь, что ID "analysis-context-section" присутствует в HTML.');
        if (document.body) document.body.innerHTML = '<p style="color: red; padding: 20px;">Ошибка: Необходимые элементы интерфейса не найдены. Проверьте консоль.</p>';
        return;
    }
    if (typeof LightweightCharts === 'undefined') {
        console.error('Библиотека LightweightCharts не загружена.');
         if (document.body) document.body.innerHTML = '<p style="color: red; padding: 20px;">Ошибка: Библиотека LightweightCharts не загружена. Проверьте подключение скрипта.</p>';
        return;
    }

    let chart = null;
    let candlestickSeries = null;
    let serverTrendLineSeries = []; 
    let userDrawnLineSeries = [];   
    let daySeparatorLineSeries = null; 
    
    let currentDrawingTool = 'pointer'; 
    let firstClickPoint = null; 

    const drawingToolButtons = [];
    if (toolPointerButton) drawingToolButtons.push(toolPointerButton);
    if (toolTrendlineButton) drawingToolButtons.push(toolTrendlineButton);

    function setActiveTool(selectedToolId) {
        currentDrawingTool = selectedToolId;
        drawingToolButtons.forEach(button => {
            if (button.id === `tool-${selectedToolId}`) { 
                button.classList.add('active');
            } else {
                button.classList.remove('active');
            }
        });
        chartContainer.style.cursor = (currentDrawingTool === 'pointer') ? 'default' : 'crosshair';
        firstClickPoint = null; 
    }

    try {
        chart = LightweightCharts.createChart(chartContainer, { 
            width: chartContainer.clientWidth,
            height: chartContainer.clientHeight,
            layout: { 
                background: { type: LightweightCharts.ColorType.Solid, color: '#FFFFFF' }, 
                textColor: '#000000' 
            },
            grid: { 
                vertLines: { color: 'rgba(197, 203, 206, 0.1)' }, 
                horzLines: { color: 'rgba(197, 203, 206, 0.1)' },
            },
            timeScale: { 
                timeVisible: true, 
                secondsVisible: false, 
                borderColor: '#B0B0B0',
            },
            crosshair: { mode: LightweightCharts.CrosshairMode.Normal },
            priceScale: { borderColor: '#B0B0B0' },
        });

        // ИЗМЕНЕНО: Используем chart.addSeries(LightweightCharts.CandlestickSeries, options)
        candlestickSeries = chart.addSeries(LightweightCharts.CandlestickSeries, { 
            upColor: '#26A69A', downColor: '#EF5350',
            borderVisible: false, 
            wickUpColor: '#26A69A', wickDownColor: '#EF5350',
        });

    } catch (e) {
        console.error('Ошибка при создании графика LightweightCharts:', e);
        if (chartContainer) chartContainer.innerHTML = '<p class="text-red-500 p-4">Не удалось загрузить график. См. консоль для деталей.</p>';
        return;
    }

    if(toolPointerButton) toolPointerButton.addEventListener('click', () => setActiveTool('pointer'));
    if(toolTrendlineButton) toolTrendlineButton.addEventListener('click', () => setActiveTool('trendline'));
    
    clearDrawnLinesButton.addEventListener('click', () => {
        userDrawnLineSeries.forEach(line => chart.removeSeries(line));
        userDrawnLineSeries = [];
    });

    chart.subscribeClick(param => {
        if (currentDrawingTool === 'pointer' || !candlestickSeries || !param.point) return;
        
        if (typeof param.time !== 'number') { 
            firstClickPoint = null; 
            return;
        }

        const price = candlestickSeries.coordinateToPrice(param.point.y);
        const time = param.time; 

        if (price === null) { 
            firstClickPoint = null; 
            return;
        }

        if (currentDrawingTool === 'trendline') {
            if (!firstClickPoint) {
                firstClickPoint = { time, price }; 
            } else {
                if (typeof firstClickPoint.time !== 'number') { 
                    firstClickPoint = null; 
                    return;
                }
                // ИЗМЕНЕНО: Используем chart.addSeries(LightweightCharts.LineSeries, options)
                const userLine = chart.addSeries(LightweightCharts.LineSeries, { 
                    color: 'purple', 
                    lineWidth: 2,
                    lineStyle: LightweightCharts.LineStyle.Solid, 
                    lastValueVisible: false, 
                    priceLineVisible: false,
                });
                userLine.setData([
                    { time: firstClickPoint.time, value: firstClickPoint.price },
                    { time: time, value: price } 
                ]);
                userDrawnLineSeries.push(userLine);
                firstClickPoint = null; 
            }
        } 
    });

    async function fetchChartData(timeframe, backtestDate = null) {
        try {
            let url = `/api/chart_data?interval=${timeframe}`;
            if (backtestDate) url += `&endDate=${backtestDate}`; 
            const response = await fetch(url);
            if (!response.ok) throw new Error(`HTTP error! status: ${response.status}, message: ${await response.text()}`);
            const jsonData = await response.json();
            if (jsonData && !Array.isArray(jsonData.analysisSummary)) {
                console.warn("fetchChartData: analysisSummary is not an array, defaulting to empty array. Received:", jsonData.analysisSummary);
                jsonData.analysisSummary = [];
            }
            return jsonData;
        } catch (error) {
            console.error('fetchChartData: Ошибка при получении данных графика:', error);
            return { ohlcv: [], markers: [], trendLines: [], analysisSummary: [] }; 
        }
    }

    function formatOhlcvData(data) {
        if (!Array.isArray(data)) return [];
        return data.map(item => ({
            time: new Date(item.time).getTime() / 1000, 
            open: parseFloat(item.open), 
            high: parseFloat(item.high),
            low: parseFloat(item.low), 
            close: parseFloat(item.close),
        }));
    }

    function formatMarkerData(data) {
        if (!Array.isArray(data)) return [];
         const markerMap = { 
             'HH': { shape: 'circle', color: 'blue', position: 'aboveBar', text: 'HH', size: 0.8 },
             'HL': { shape: 'circle', color: 'green', position: 'belowBar', text: 'HL', size: 0.8 },
             'LH': { shape: 'circle', color: 'red', position: 'aboveBar', text: 'LH', size: 0.8 },
             'LL': { shape: 'circle', color: 'purple', position: 'belowBar', text: 'LL', size: 0.8 },
             'H': { shape: 'circle', color: '#808080', position: 'aboveBar', size: 0.7, text: 'H' }, 
             'L': { shape: 'circle', color: '#808080', position: 'belowBar', size: 0.7, text: 'L' },
             'F_H_AS': { shape: 'arrowDown', color: 'darkorange', position: 'aboveBar', text: 'AsH', size: 0.9 }, 
             'F_L_AS': { shape: 'arrowUp', color: 'darkorange', position: 'belowBar', text: 'AsL', size: 0.9 },   
             'F_H_NY1': { shape: 'arrowDown', color: 'dodgerblue', position: 'aboveBar', text: 'NyH', size: 0.9 },
             'F_L_NY1': { shape: 'arrowUp', color: 'dodgerblue', position: 'belowBar', text: 'NyL', size: 0.9 },  
             'F_H_NY2': { shape: 'arrowDown', color: 'deepskyblue', position: 'aboveBar', text: 'NyH-1', size: 0.9 }, 
             'F_L_NY2': { shape: 'arrowUp', color: 'deepskyblue', position: 'belowBar', text: 'NyL-1', size: 0.9 },   
             'SETUP_Resist': { shape: 'square', color: 'black', position: 'aboveBar', text: 'SR', size: 1 }, 
             'SETUP_Support': { shape: 'square', color: 'black', position: 'belowBar', text: 'SS', size: 1 }, 
             'UNKNOWN_SETUP': { shape: 'circle', color: '#A9A9A9', position: 'aboveBar', text: '?', size: 1 }, 
         };
         const filteredData = data.filter(item => item && markerMap.hasOwnProperty(item.type)); 
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
        if (!Array.isArray(data)) return [];
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

    function displayAnalysisSummary(summaryDataList) { 
        if (contextAnalysisSectionDiv) {
            const ulElement = contextAnalysisSectionDiv.querySelector('ul');
            if (ulElement) {
                ulElement.innerHTML = ''; 

                if (summaryDataList && Array.isArray(summaryDataList) && summaryDataList.length > 0) {
                    summaryDataList.forEach(item => {
                        if (typeof item.description !== 'string') { 
                            console.warn("Skipping item with non-string description:", item);
                            return; 
                        }
                        const listItem = document.createElement('li');
                        listItem.classList.add('flex', 'items-center', 'mb-1', 'text-xs'); 
                        
                        const statusIcon = document.createElement('span');
                        statusIcon.classList.add('mr-2');
                        if (item.status === true) {
                            statusIcon.classList.add('text-green-500');
                            statusIcon.textContent = '✓';
                        } else if (item.status === false) {
                            statusIcon.classList.add('text-red-500');
                            statusIcon.textContent = '✗';
                        } else { 
                            statusIcon.textContent = '•'; 
                            statusIcon.classList.add('text-gray-500');
                        }
                        
                        const description = document.createElement('span');
                        description.textContent = item.description;
                        
                        listItem.appendChild(statusIcon);
                        listItem.appendChild(description);
                        ulElement.appendChild(listItem);
                    });
                } else {
                    const listItem = document.createElement('li');
                    listItem.textContent = 'Нет данных для анализа контекста.';
                    listItem.classList.add('text-xs', 'text-gray-500');
                    ulElement.appendChild(listItem);
                }
            } else {
                 console.error("UL элемент внутри 'analysis-context-section' не найден.");
            }
        } else {
            console.error("Элемент с ID 'analysis-context-section' не найден в DOM.");
        }
    }
    
    async function loadChartData(timeframe, backtestDate = null) {
        const chartData = await fetchChartData(timeframe, backtestDate);

        serverTrendLineSeries.forEach(series => {
            if (chart && series) chart.removeSeries(series);
        });
        serverTrendLineSeries = [];

        if (daySeparatorLineSeries && chart) {
            chart.removeSeries(daySeparatorLineSeries);
            daySeparatorLineSeries = null;
        }

        if (candlestickSeries) { 
            if (typeof candlestickSeries.setMarkers === 'function') {
                candlestickSeries.setMarkers([]); 
            } else {
                console.warn('candlestickSeries.setMarkers is not a function when trying to clear markers. Series object:', candlestickSeries);
            }
        }

        if (chartData && chartData.ohlcv && chartData.ohlcv.length > 0) {
            const formattedOhlcv = formatOhlcvData(chartData.ohlcv);
            if (candlestickSeries) candlestickSeries.setData(formattedOhlcv);

            let todayTimestampUTC;
            const lastCandleTime = new Date(formattedOhlcv[formattedOhlcv.length - 1].time * 1000); 
            
            if (backtestDate) { 
                const [year, month, day] = backtestDate.split('-').map(Number);
                todayTimestampUTC = new Date(Date.UTC(year, month - 1, day, 0, 0, 0)).getTime() / 1000;
            } else { 
                todayTimestampUTC = new Date(Date.UTC(lastCandleTime.getUTCFullYear(), lastCandleTime.getUTCMonth(), lastCandleTime.getUTCDate(), 0, 0, 0)).getTime() / 1000;
            }

            if (todayTimestampUTC && candlestickSeries && formattedOhlcv.length > 0) {
                let minPrice = Infinity;
                let maxPrice = -Infinity;
                
                const visibleRange = chart.timeScale().getVisibleLogicalRange();
                let relevantData = formattedOhlcv;
                if(visibleRange && visibleRange.from !== null && visibleRange.to !== null) {
                    relevantData = formattedOhlcv.slice(Math.max(0, Math.floor(visibleRange.from)), Math.min(formattedOhlcv.length, Math.ceil(visibleRange.to)));
                }
                if(relevantData.length === 0) relevantData = formattedOhlcv;

                relevantData.forEach(candle => {
                    if (candle.low < minPrice) minPrice = candle.low;
                    if (candle.high > maxPrice) maxPrice = candle.high;
                });

                 if (minPrice === Infinity || maxPrice === -Infinity) { 
                    minPrice = formattedOhlcv.reduce((min, p) => p.low < min ? p.low : min, formattedOhlcv[0].low);
                    maxPrice = formattedOhlcv.reduce((max, p) => p.high > max ? p.high : max, formattedOhlcv[0].high);
                 }

                const pricePadding = (maxPrice - minPrice) * 0.05; 
                const lineMinPrice = minPrice - pricePadding;
                const lineMaxPrice = maxPrice + pricePadding;
                
                // ИЗМЕНЕНО: Используем chart.addSeries(LightweightCharts.LineSeries, options)
                daySeparatorLineSeries = chart.addSeries(LightweightCharts.LineSeries, {
                    color: 'rgba(100, 100, 100, 0.5)', 
                    lineWidth: 1,
                    lineStyle: LightweightCharts.LineStyle.Dashed,
                    lastValueVisible: false,
                    priceLineVisible: false,
                    crosshairMarkerVisible: false,
                     autoscaleInfoProvider: () => ({ 
                        priceRange: {
                            minValue: lineMinPrice, 
                            maxValue: lineMaxPrice,
                        },
                    }),
                });
                daySeparatorLineSeries.setData([
                    { time: todayTimestampUTC, value: lineMinPrice },
                    { time: todayTimestampUTC, value: lineMaxPrice }
                ]);
            }
            
            if (chartData.markers && chartData.markers.length > 0) {
                const serverMarkers = formatMarkerData(chartData.markers);
                if (candlestickSeries) {
                    if (typeof candlestickSeries.setMarkers === 'function') {
                        if (serverMarkers.length > 0) {
                            candlestickSeries.setMarkers(serverMarkers);
                        }
                    } else {
                         console.warn('candlestickSeries.setMarkers is not a function when trying to set new markers. Series object:', candlestickSeries);
                    }
                }
            }

            if (chartData.trendLines && chartData.trendLines.length > 0) {
                const formattedTrendLines = formatTrendLineData(chartData.trendLines);
                formattedTrendLines.forEach(lineDef => {
                    // ИЗМЕНЕНО: Используем chart.addSeries(LightweightCharts.LineSeries, options)
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
        displayAnalysisSummary(chartData && Array.isArray(chartData.analysisSummary) ? chartData.analysisSummary : []); 
    }

    if (timeframeSelect) {
        timeframeSelect.addEventListener('change', () => {
            const selectedTimeframe = timeframeSelect.value;
            const selectedDate = backtestDateInput.value || null; 
            loadChartData(selectedTimeframe, selectedDate);
        });
    }
    if (backtestDateInput) {
        backtestDateInput.addEventListener('change', () => {
            const selectedTimeframe = timeframeSelect.value;
            const selectedDate = backtestDateInput.value || null;
            loadChartData(selectedTimeframe, selectedDate);
        });
    }
    
    setActiveTool('pointer'); 
    loadChartData(timeframeSelect ? timeframeSelect.value : '1h', backtestDateInput ? backtestDateInput.value : null);

    const resizeObserver = new ResizeObserver(entries => {
        if (entries.length === 0 || entries[0].target !== chartContainerWrapper) return; 
        const newRect = entries[0].contentRect;
        if (chart) {
             chart.applyOptions({ height: newRect.height, width: newRect.width });
        }
    });
    if (chartContainerWrapper) { 
        resizeObserver.observe(chartContainerWrapper); 
    }
});
