// web/script.js

// Изменяем слушатель события с DOMContentLoaded на window.load
window.addEventListener('load', () => {
    const chartContainer = document.getElementById('chart-container');

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

    let chart = null; // Объявляем chart здесь, чтобы он был доступен в блоке catch

    try {
        // Создаем экземпляр графика
        // Убедимся, что контейнер имеет размеры, чтобы createChart работал корректно
        // Используем актуальные размеры контейнера после загрузки страницы
        chart = LightweightCharts.createChart(chartContainer, {
            width: chartContainer.clientWidth,
            height: chartContainer.clientHeight,
            layout: {
                background: { color: '#ffffff' }, // Белый фон
                textColor: '#333', // Темный текст
            },
            grid: {
                vertLines: { color: '#e1ecf2' }, // Светлые вертикальные линии сетки
                horzLines: { color: '#e1ecf2' }, // Светлые горизонтальные линии сетки
            },
            timeScale: {
                timeVisible: true, // Показать время на оси X
                secondsVisible: false, // Скрыть секунды
            },
            crosshair: {
                mode: LightweightCharts.CrosshairMode.Normal,
            },
            // Настройки цены
            priceScale: {
                borderColor: '#e1ecf2', // Цвет границы ценовой шкалы
            },
        });

        // Явная проверка, что chart создан успешно
        if (!chart) {
             console.error('Не удалось создать экземпляр графика LightweightCharts.');
             return; // Выходим, если chart не создан
        }

    } catch (e) {
        console.error('Ошибка при создании графика LightweightCharts:', e);
        return; // Выходим, если произошла ошибка при создании графика
    }


    // Добавляем серию свечей - теперь используем addSeries с указанием типа
    const candlestickSeries = chart.addSeries(LightweightCharts.CandlestickSeries, {
        upColor: '#4CAF50', // Зеленый для растущих свечей
        downColor: '#F44336', // Красный для падающих свечей
        borderVisible: false,
        wickColor: '#7F8C8D', // Серый для фитилей
        wickUpColor: '#4CAF50', // Зеленый для фитилей растущих свечей
        wickDownColor: '#F44336', // Красный для фитилей падающих свечей
    });

    // Функция для получения данных с бэкенда
    async function fetchChartData() {
        try {
            // Замените '/api/chart_data' на реальный эндпоинт вашего Python бэкенда
            const response = await fetch('/api/chart_data');
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            const data = await response.json();
            return data;
        } catch (error) {
            console.error('Ошибка при получении данных графика:', error);
            // Вернуть пустые данные или данные-заглушку в случае ошибки
            return { ohlcv: [], markers: [] };
        }
    }

    // Функция для форматирования данных OHLCV для Lightweight Charts
    function formatOhlcvData(data) {
        // Lightweight Charts ожидает формат:
        // [{ time: timestamp_in_seconds, open: ..., high: ..., low: ..., close: ... }, ...]
        // Предполагаем, что ваш бэкенд возвращает данные с полем 'time' в формате ISO 8601 строки или timestamp в миллисекундах
        return data.map(item => ({
            time: new Date(item.time).getTime() / 1000, // Преобразуем в timestamp в секундах
            open: parseFloat(item.open),
            high: parseFloat(item.high),
            low: parseFloat(item.low),
            close: parseFloat(item.close),
        }));
    }

    // Функция для форматирования данных маркеров для Lightweight Charts
    function formatMarkerData(data) {
         // Lightweight Charts ожидает формат маркеров:
         // [{ time: timestamp_in_seconds, position: 'aboveBar' | 'belowBar', color: ..., shape: 'arrowUp' | 'arrowDown' | 'circle' | 'square', text: ... }, ...]
         // Ваш бэкенд должен предоставить тип маркера ('HH', 'LL', 'SETUP_Resist' и т.д.)
         // Нужно будет сопоставить ваши типы с форматом Lightweight Charts
         const markerMap = {
             'HH': { shape: 'arrowDown', color: '#2962FF', position: 'aboveBar' }, // Пример: HH как стрелка вниз над баром
             'HL': { shape: 'circle', color: '#26A69A', position: 'belowBar' },   // Пример: HL как круг под баром
             'LH': { shape: 'arrowUp', color: '#FF0000', position: 'belowBar' },   // Пример: LH как стрелка вверх под баром
             'LL': { shape: 'circle', color: '#FF0000', position: 'aboveBar' },   // Пример: LL как круг над баром
             'H': { shape: 'square', color: '#2962FF', position: 'aboveBar' },    // Пример: H как квадрат над баром
             'L': { shape: 'square', color: '#26A69A', position: 'belowBar' },    // Пример: L как квадрат под баром
             'F_H_AS': { shape: 'circle', color: '#FFA500', position: 'aboveBar' }, // Пример: Азиатский фрактал H
             'F_L_AS': { shape: 'circle', color: '#FFA500', position: 'belowBar' }, // Пример: Азиатский фрактал L
             'F_H_NY1': { shape: 'circle', color: '#1E90FF', position: 'aboveBar' }, // Пример: НЙ фрактал H (-1 день)
             'F_L_NY1': { shape: 'circle', color: '#1E90FF', position: 'belowBar' }, // Пример: НЙ фрактал L (-1 день)
             'SETUP_Resist': { shape: 'square', color: '#000000', position: 'aboveBar', size: 1.5 }, // Пример: Сетап сопротивления
             'SETUP_Support': { shape: 'square', color: '#000000', position: 'belowBar', size: 1.5 }, // Пример: Сетап поддержки
             'UNKNOWN_SETUP': { shape: 'circle', color: '#808080', position: 'aboveBar' } // Пример: Неизвестный сетап
         };

         return data.map(item => {
             const markerType = markerMap[item.type] || { shape: 'circle', color: '#808080', position: 'aboveBar' }; // Дефолтный маркер
             return {
                 time: new Date(item.time).getTime() / 1000, // Преобразуем в timestamp в секундах
                 position: markerType.position,
                 color: markerType.color,
                 shape: markerType.shape,
                 text: item.type, // Текст маркера - тип точки
                 size: markerType.size || 1, // Размер маркера
             };
         });
     }


    // Инициализация: получаем данные и отображаем их
    async function initChart() {
        const chartData = await fetchChartData();

        if (chartData && chartData.ohlcv && chartData.ohlcv.length > 0) {
            const formattedOhlcv = formatOhlcvData(chartData.ohlcv);
            candlestickSeries.setData(formattedOhlcv);

            if (chartData.markers && chartData.markers.length > 0) {
                 const formattedMarkers = formatMarkerData(chartData.markers);
                 candlestickSeries.setMarkers(formattedMarkers);
            }

            // Подгоняем график под данные
            chart.timeScale().fitContent();
        } else {
            console.warn('Нет данных для отображения графика.');
        }
    }

    // Вызываем функцию инициализации
    initChart();

    // Обработчик изменения размера окна для адаптивности
    new ResizeObserver(entries => {
        if (entries.length === 0 || entries[0].target !== chartContainer) {
            return;
        }
        const newRect = entries[0].contentRect;
        chart.applyOptions({ height: newRect.height, width: newRect.width });
    }).observe(chartContainer);

});
