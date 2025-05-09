"""
Module containing various helper functions and constants.
"""

# Constants
DEFAULT_TIMEFRAMES = {
    '1H': '1H',
    '3M': '3M'
}

DEFAULT_SYMBOLS = [
    'EURUSD',
    'GBPUSD',
    'USDJPY'
]

def calculate_risk_position_size(balance, risk_per_trade, stop_loss):
    """
    Calculate position size based on risk management rules.
    
    Args:
        balance (float): Account balance
        risk_per_trade (float): Risk per trade as percentage
        stop_loss (float): Stop loss distance in points
        
    Returns:
        float: Position size
    """
    risk_amount = balance * (risk_per_trade / 100)
    position_size = risk_amount / stop_loss
    return position_size
