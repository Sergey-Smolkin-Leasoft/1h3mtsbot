# 1H3MTS Bot

A trading bot that implements a strategy combining 1H timeframe context analysis with 3M timeframe signal generation.

## Project Structure

```
1h3mtsbot/
├── bot/                      # Основной код бота
│   ├── core/                 # Ядро бота: загрузка данных, основная логика
│   ├── strategy/             # Логика торговой стратегии
│   ├── utils/                # Вспомогательные утилиты
│   └── main_controller.py    # Главный управляющий скрипт
├── configs/                  # Конфигурационные файлы
├── data/                     # Данные и логи
├── tests/                    # Тесты
└── requirements.txt          # Зависимости
```

## Setup

1. Create a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Copy `.env_example` to `.env` and fill in your API keys:
```bash
cp .env_example .env
```

## Running the Bot

```bash
python bot/main_controller.py
```

## Features

- 1H timeframe market context analysis
- 3M timeframe signal generation
- Risk management
- Logging system
- Configurable parameters
- Modular architecture
