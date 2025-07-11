"""
Account and position Pydantic models for MES Trading Assistant
"""

from datetime import datetime
from decimal import Decimal
from typing import Optional, List, Dict
from pydantic import BaseModel, Field, validator

class Balance(BaseModel):
    """Account balance information"""
    currency: str = Field(..., description="Currency code (USD, EUR, etc.)")
    available: float = Field(..., ge=0, description="Available balance")
    total: float = Field(..., ge=0, description="Total balance")
    reserved: float = Field(0, ge=0, description="Reserved/locked balance")
    unrealized_pnl: float = Field(0, description="Unrealized P&L")
    
    @validator('total')
    def validate_total_balance(cls, v, values):
        """Validate total balance consistency"""
        available = values.get('available', 0)
        reserved = values.get('reserved', 0)
        
        if abs(v - (available + reserved)) > 0.01:  # Allow small floating point differences
            raise ValueError("Total balance must equal available + reserved")
        
        return v

class Position(BaseModel):
    """Trading position information"""
    symbol: str = Field(..., description="Trading symbol")
    side: str = Field(..., description="Position side (long/short)")
    size: int = Field(..., description="Position size (signed: + for long, - for short)")
    entry_price: float = Field(..., gt=0, description="Average entry price")
    market_price: float = Field(..., gt=0, description="Current market price")
    unrealized_pnl: float = Field(..., description="Unrealized P&L")
    realized_pnl: float = Field(0, description="Realized P&L for the day")
    margin_used: float = Field(..., ge=0, description="Margin used for position")
    timestamp: datetime = Field(..., description="Last update timestamp")
    
    @validator('side')
    def validate_side(cls, v):
        """Validate position side"""
        if v.lower() not in ['long', 'short']:
            raise ValueError("Position side must be 'long' or 'short'")
        return v.lower()
    
    @validator('size')
    def validate_size_consistency(cls, v, values):
        """Validate size consistency with side"""
        side = values.get('side')
        if side == 'long' and v < 0:
            raise ValueError("Long position must have positive size")
        elif side == 'short' and v > 0:
            raise ValueError("Short position must have negative size")
        return v
    
    @property
    def market_value(self) -> float:
        """Calculate current market value"""
        return abs(self.size) * self.market_price
    
    @property
    def pnl_percent(self) -> float:
        """Calculate P&L percentage"""
        if self.entry_price == 0:
            return 0
        return (self.unrealized_pnl / (abs(self.size) * self.entry_price)) * 100

class Account(BaseModel):
    """Complete account information"""
    account_id: str = Field(..., description="Account identifier")
    account_type: str = Field(..., description="Account type (margin, cash, etc.)")
    status: str = Field(..., description="Account status (active, suspended, etc.)")
    balances: List[Balance] = Field(..., description="Account balances by currency")
    positions: List[Position] = Field(default=[], description="Current positions")
    buying_power: float = Field(..., ge=0, description="Available buying power")
    margin_used: float = Field(0, ge=0, description="Total margin used")
    margin_available: float = Field(..., ge=0, description="Available margin")
    day_trading_buying_power: Optional[float] = Field(None, description="Day trading buying power")
    pattern_day_trader: bool = Field(False, description="Pattern day trader status")
    last_updated: datetime = Field(..., description="Last account update")
    
    @validator('account_type')
    def validate_account_type(cls, v):
        """Validate account type"""
        valid_types = ['cash', 'margin', 'portfolio_margin', 'ira']
        if v.lower() not in valid_types:
            raise ValueError(f"Account type must be one of: {valid_types}")
        return v.lower()
    
    @validator('status')
    def validate_status(cls, v):
        """Validate account status"""
        valid_statuses = ['active', 'suspended', 'closed', 'restricted']
        if v.lower() not in valid_statuses:
            raise ValueError(f"Account status must be one of: {valid_statuses}")
        return v.lower()
    
    @property
    def total_unrealized_pnl(self) -> float:
        """Calculate total unrealized P&L across all positions"""
        return sum(pos.unrealized_pnl for pos in self.positions)
    
    @property
    def total_realized_pnl(self) -> float:
        """Calculate total realized P&L across all positions"""
        return sum(pos.realized_pnl for pos in self.positions)
    
    @property
    def net_liquidation_value(self) -> float:
        """Calculate net liquidation value"""
        cash_balance = sum(bal.total for bal in self.balances)
        return cash_balance + self.total_unrealized_pnl

class Risk(BaseModel):
    """Risk management information"""
    account_id: str = Field(..., description="Account identifier")
    max_position_size: int = Field(..., gt=0, description="Maximum position size per symbol")
    max_daily_loss: float = Field(..., gt=0, description="Maximum daily loss limit")
    max_orders_per_minute: int = Field(..., gt=0, description="Maximum orders per minute")
    current_daily_pnl: float = Field(..., description="Current daily P&L")
    risk_level: str = Field(..., description="Current risk level (low, medium, high)")
    margin_call_threshold: float = Field(..., description="Margin call threshold")
    is_restricted: bool = Field(False, description="Whether account has trading restrictions")
    restrictions: List[str] = Field(default=[], description="List of active restrictions")
    
    @validator('risk_level')
    def validate_risk_level(cls, v):
        """Validate risk level"""
        valid_levels = ['low', 'medium', 'high', 'critical']
        if v.lower() not in valid_levels:
            raise ValueError(f"Risk level must be one of: {valid_levels}")
        return v.lower()

class Trade(BaseModel):
    """Individual trade record"""
    trade_id: str = Field(..., description="Unique trade identifier")
    order_id: str = Field(..., description="Associated order ID")
    symbol: str = Field(..., description="Trading symbol")
    side: str = Field(..., description="Trade side (buy/sell)")
    quantity: int = Field(..., gt=0, description="Trade quantity")
    price: float = Field(..., gt=0, description="Trade price")
    value: float = Field(..., description="Trade value (quantity * price)")
    commission: float = Field(0, ge=0, description="Commission paid")
    fees: float = Field(0, ge=0, description="Exchange fees")
    timestamp: datetime = Field(..., description="Trade execution timestamp")
    
    @validator('side')
    def validate_side(cls, v):
        """Validate trade side"""
        if v.lower() not in ['buy', 'sell']:
            raise ValueError("Trade side must be 'buy' or 'sell'")
        return v.lower()
    
    @property
    def net_proceeds(self) -> float:
        """Calculate net proceeds after commissions and fees"""
        return self.value - self.commission - self.fees

class AccountSummary(BaseModel):
    """Account summary for dashboard display"""
    account_id: str = Field(..., description="Account identifier")
    net_liquidation_value: float = Field(..., description="Net liquidation value")
    available_funds: float = Field(..., description="Available funds")
    buying_power: float = Field(..., description="Buying power")
    total_positions: int = Field(..., ge=0, description="Number of open positions")
    daily_pnl: float = Field(..., description="Daily P&L")
    daily_pnl_percent: float = Field(..., description="Daily P&L percentage")
    total_trades_today: int = Field(0, ge=0, description="Total trades executed today")
    last_trade_time: Optional[datetime] = Field(None, description="Last trade execution time")
    
class MarginRequirement(BaseModel):
    """Margin requirement for a symbol"""
    symbol: str = Field(..., description="Trading symbol")
    initial_margin: float = Field(..., gt=0, description="Initial margin requirement")
    maintenance_margin: float = Field(..., gt=0, description="Maintenance margin requirement")
    currency: str = Field("USD", description="Currency for margin amounts")
