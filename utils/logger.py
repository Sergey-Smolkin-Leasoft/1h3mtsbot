"""
Module for logging configuration and utilities.
"""
import logging
from logging.handlers import RotatingFileHandler

def setup_logger():
    """
    Configure the logger.
    """
    logger = logging.getLogger('1h3mtsbot')
    logger.setLevel(logging.INFO)
    
    # Create rotating file handler
    handler = RotatingFileHandler(
        'data/logs/bot.log',
        maxBytes=1024*1024*5,  # 5MB
        backupCount=5
    )
    
    # Create formatter
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    handler.setFormatter(formatter)
    
    # Add handler to logger
    logger.addHandler(handler)
    
    return logger
