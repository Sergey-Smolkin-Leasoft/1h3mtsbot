// front/js/script.js

window.addEventListener('load', () => {
    const chartContainer = document.getElementById('chart-container');
    const chartContainerWrapper = document.getElementById('chart-container-wrapper');
    const timeframeSelect = document.getElementById('timeframe-select');
    const backtestDateInput = document.getElementById('backtest-date');

    const toolPointerButton = document.getElementById('tool-pointer');
    const toolTrendlineButton = document.getElementById('tool-trendline');
    const clearDrawnLinesButton = document.getElementById('clear-drawn-lines');

    // Get the context section div
    const contextAnalysisSectionDiv = document.getElementById('analysis-context-section');
    // MODIFIED: Get the new entry points section div and fractal count list item
    const entryPointsSectionDiv = document.getElementById('entry-points-section');
    const fractalCountItem = document.getElementById('fractal-count-item');


    if (!chartContainer || !chartContainerWrapper || !toolTrendlineButton || !clearDrawnLinesButton || !toolPointerButton || !contextAnalysisSectionDiv || !entryPointsSectionDiv || !fractalCountItem) { // Added checks for new elements
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
                background: { color: '#FFFFFF' },
                textColor: '#000000'
            },
            grid: {
                vertLines: { color: 'rgba(197, 203, 206, 0)' },
                horzLines: { color: 'rgba(197, 203, 206, 0)' },
            },
            timeScale: {
                timeVisible: true,
                secondsVisible: false,
                borderColor: '#B0B0B0',
                timezone: 'Etc/GMT-3',
            },
            crosshair: { mode: LightweightCharts.CrosshairMode.Normal },
            priceScale: { borderColor: '#B0B0B0' },
        });

        candlestickSeries = chart.addSeries(LightweightCharts.CandlestickSeries, {
            upColor: '#26A69A', downColor: '#EF5350',
            borderVisible: false, wickColor: '#7F8C8D',
            wickUpColor: '#26A69A', wickDownColor: '#EF5350',
        });

    } catch (e) {
        console.error('Ошибка при создании графика LightweightCharts:', e);
        return;
    }

    if(toolPointerButton) toolPointerButton.addEventListener('click', () => setActiveTool('pointer'));
    if(toolTrendlineButton) toolTrendlineButton.addEventListener('click', () => setActiveTool('trendline'));

    clearDrawnLinesButton.addEventListener('click', () => {
        userDrawnLineSeries.forEach(line => chart.removeSeries(line));
        userDrawnLineSeries = [];
    });

    chart.subscribeClick(param => {
        if (currentDrawingTool === 'pointer' || !candlestickSeries) return;
        if (!param.point || typeof param.time !== 'number') {
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
                const userLine = chart.addSeries(LightweightCharts.LineSeries, {
                    color: 'purple', lineWidth: 2,
                    lineStyle: LightweightCharts.LineStyle.Solid,
                    lastValueVisible: false, priceLineVisible: false,
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
            if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
            return await response.json();
        } catch (error) {
            console.error('fetchChartData: Ошибка при получении данных графика:', error);
            // MODIFIED: analysisSummary is now a list, added fractalCount
            return { ohlcv: [], markers: [], trendLines: [], analysisSummary: [], fractalCount: 0 };
        }
    }

    function formatOhlcvData(data) {
        return data.map(item => ({
            time: new Date(item.time).getTime() / 1000,
            open: parseFloat(item.open), high: parseFloat(item.high),
            low: parseFloat(item.low), close: parseFloat(item.close),
        }));
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
             'UNKNOWN_SETUP': { shape: 'circle', color: '#A9A9A9', position: 'aboveBar', text: '?', size: 1 },
         };
         const filteredData = data.filter(item => markerMap.hasOwnProperty(item.type));
         return filteredData.map(item => {
             const markerType = markerMap[item.type];
             return {
                 time: new Date(item.time).getTime() / 1000,
                 position: markerType.position, color: markerType.color,
                 shape: markerType.shape, text: markerType.text !== undefined ? markerType.text : item.type,
                 size: markerType.size !== undefined ? markerType.size : 1,
                 id: item.id || markerType.id
             };
         });
    }


    function formatTrendLineData(data) {
        return data.map(line => ({
            data: [
                { time: new Date(line.start_time).getTime() / 1000, value: line.start_price },
                { time: new Date(line.end_time).getTime() / 1000, value: line.end_price }
            ],
            color: line.color || '#000000', lineWidth: 2,
            lineStyle: line.lineStyle !== undefined ? line.lineStyle : LightweightCharts.LineStyle.Solid,
            crosshairMarkerVisible: false, lastValueVisible: false, priceLineVisible: false,
        }));
    }

    // displayAnalysisSummary to handle a list of context items
    function displayAnalysisSummary(summaryDataList) { // summaryDataList is the list of context items
        if (contextAnalysisSectionDiv) {
            const ulElement = contextAnalysisSectionDiv.querySelector('ul');
            if (ulElement) {
                ulElement.innerHTML = ''; // Clear previous items

                if (summaryDataList && Array.isArray(summaryDataList) && summaryDataList.length > 0) {
                    summaryDataList.forEach(item => {
                        const listItem = document.createElement('li');
                        listItem.classList.add('flex', 'items-center', 'mb-1');

                        const statusIcon = document.createElement('span');
                        statusIcon.classList.add('mr-2');
                        if (item.status === true) {
                            statusIcon.classList.add('text-green-500');
                            statusIcon.textContent = '✓';
                        } else if (item.status === false) {
                            statusIcon.classList.add('text-red-500');
                            statusIcon.textContent = '✗';
                        } else {
                            // Neutral or no status
                            statusIcon.textContent = '-'; // Or some other indicator
                        }

                        const description = document.createElement('span');
                        description.textContent = item.description;

                        listItem.appendChild(statusIcon);
                        listItem.appendChild(description);
                        ulElement.appendChild(listItem);
                    });
                } else {
                    const listItem = document.createElement('li');
                    listItem.textContent = 'No context analysis data available.';
                    ulElement.appendChild(listItem);
                }
            }
        } else {
            console.error("Element with ID 'analysis-context-section' not found.");
        }
    }

    // MODIFIED: New function to display fractal count
    function displayFractalCount(count) {
        if (fractalCountItem) {
            fractalCountItem.textContent = `Fractals found: ${count}`;
        } else {
            console.error("Element with ID 'fractal-count-item' not found.");
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
             if (typeof LightweightCharts.createSeriesMarkers === 'function') {
                LightweightCharts.createSeriesMarkers(candlestickSeries, []);
            } else if (typeof candlestickSeries.setMarkers === 'function') {
                candlestickSeries.setMarkers([]);
            }
        }

        if (chartData && chartData.ohlcv && chartData.ohlcv.length > 0) {
            const formattedOhlcv = formatOhlcvData(chartData.ohlcv);
            if (candlestickSeries) candlestickSeries.setData(formattedOhlcv);

            let todayTimestampUTC;
            if (backtestDate) {
                const [year, month, day] = backtestDate.split('-').map(Number);
                todayTimestampUTC = new Date(Date.UTC(year, month - 1, day, 0, 0, 0)).getTime() / 1000;
            } else {
                const lastCandleTime = new Date(formattedOhlcv[formattedOhlcv.length - 1].time * 1000);
                todayTimestampUTC = new Date(Date.UTC(lastCandleTime.getUTCFullYear(), lastCandleTime.getUTCMonth(), lastCandleTime.getUTCDate(), 0, 0, 0)).getTime() / 1000;
            }

            if (todayTimestampUTC && candlestickSeries) {
                let minPrice = Infinity;
                let maxPrice = -Infinity;
                formattedOhlcv.forEach(candle => {
                    if (candle.low < minPrice) minPrice = candle.low;
                    if (candle.high > maxPrice) maxPrice = candle.high;
                });

                const pricePadding = (maxPrice - minPrice) * 0.05;
                minPrice -= pricePadding;
                maxPrice += pricePadding;

                if (minPrice === Infinity || maxPrice === -Infinity) {
                    minPrice = candlestickSeries.coordinateToPrice(chart.priceScale('right').height());
                    maxPrice = candlestickSeries.coordinateToPrice(0);
                }

                daySeparatorLineSeries = chart.addSeries(LightweightCharts.LineSeries, {
                    color: '#000000',
                    lineWidth: 1,
                    lineStyle: LightweightCharts.LineStyle.Dashed,
                    lastValueVisible: false,
                    priceLineVisible: false,
                    autoscaleInfoProvider: () => ({
                        priceRange: {
                            minValue: minPrice,
                            maxValue: maxPrice,
                        },
                    }),
                });
                daySeparatorLineSeries.setData([
                    { time: todayTimestampUTC, value: minPrice },
                    { time: todayTimestampUTC, value: maxPrice }
                ]);
            }

            if (chartData.markers && chartData.markers.length > 0) {
                const serverMarkers = formatMarkerData(chartData.markers);
                 if (candlestickSeries && serverMarkers.length > 0) {
                     if (typeof LightweightCharts.createSeriesMarkers === 'function') {
                        LightweightCharts.createSeriesMarkers(candlestickSeries, serverMarkers);
                    } else if (typeof candlestickSeries.setMarkers === 'function') {
                        candlestickSeries.setMarkers(serverMarkers);
                    }
                }
            }

            if (chartData.trendLines && chartData.trendLines.length > 0) {
                const formattedTrendLines = formatTrendLineData(chartData.trendLines);
                formattedTrendLines.forEach(lineDef => {
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
        // Pass chartData.analysisSummary (which is now a list)
        displayAnalysisSummary(chartData ? chartData.analysisSummary : []);
        // MODIFIED: Display fractal count
        displayFractalCount(chartData ? chartData.fractalCount : 0);
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
