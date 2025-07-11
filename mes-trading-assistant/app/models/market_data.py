"""
Market data Pydantic models for MES Trading Assistant
"""

from datetime import datetime
from decimal import Decimal
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, validator

class Quote(BaseModel):
    """Real-time quote data"""
    symbol: str = Field(..., description="Trading symbol")
    bid: float = Field(..., gt=0, description="Bid price")
    ask: float = Field(..., gt=0, description="Ask price")
    bid_size: int = Field(..., ge=0, description="Bid size")
    ask_size: int = Field(..., ge=0, description="Ask size")
    timestamp: datetime = Field(..., description="Quote timestamp")
    
    @validator('ask')
    def validate_spread(cls, v, values):
        """Validate that ask is greater than bid"""
        bid = values.get('bid')
        if bid and v <= bid:
            raise ValueError("Ask price must be greater than bid price")
        return v
    
    @property
    def spread(self) -> float:
        """Calculate bid-ask spread"""
        return self.ask - self.bid
    
    @property
    def mid_price(self) -> float:
        """Calculate mid price"""
        return (self.bid + self.ask) / 2

class Trade(BaseModel):
    """Trade execution data"""
    symbol: str = Field(..., description="Trading symbol")
    price: float = Field(..., gt=0, description="Trade price")
    size: int = Field(..., gt=0, description="Trade size")
    side: Optional[str] = Field(None, description="Trade side (buy/sell)")
    timestamp: datetime = Field(..., description="Trade timestamp")
    trade_id: Optional[str] = Field(None, description="Unique trade ID")
    conditions: Optional[List[str]] = Field(None, description="Trade conditions")

class MarketData(BaseModel):
    """Comprehensive market data snapshot"""
    symbol: str = Field(..., description="Trading symbol")
    last_price: float = Field(..., gt=0, description="Last trade price")
    last_size: int = Field(..., ge=0, description="Last trade size")
    bid: float = Field(..., gt=0, description="Best bid price")
    ask: float = Field(..., gt=0, description="Best ask price")
    bid_size: int = Field(..., ge=0, description="Best bid size")
    ask_size: int = Field(..., ge=0, description="Best ask size")
    volume: int = Field(..., ge=0, description="Daily volume")
    open_price: Optional[float] = Field(None, gt=0, description="Session open price")
    high_price: Optional[float] = Field(None, gt=0, description="Session high price")
    low_price: Optional[float] = Field(None, gt=0, description="Session low price")
    close_price: Optional[float] = Field(None, gt=0, description="Previous close price")
    change: Optional[float] = Field(None, description="Price change from previous close")
    change_percent: Optional[float] = Field(None, description="Percentage change")
    timestamp: datetime = Field(..., description="Data timestamp")
    
    @property
    def spread(self) -> float:
        """Calculate bid-ask spread"""
        return self.ask - self.bid
    
    @property
    def mid_price(self) -> float:
        """Calculate mid price"""
        return (self.bid + self.ask) / 2

class OrderBook(BaseModel):
    """Level 2 order book data"""
    symbol: str = Field(..., description="Trading symbol")
    bids: List[List[float]] = Field(..., description="Bid levels [price, size]")
    asks: List[List[float]] = Field(..., description="Ask levels [price, size]")
    timestamp: datetime = Field(..., description="Order book timestamp")
    sequence: Optional[int] = Field(None, description="Sequence number")
    
    @validator('bids')
    def validate_bids(cls, v):
        """Validate bid levels are properly formatted and sorted"""
        if not v:
            return v
        
        for level in v:
            if len(level) != 2:
                raise ValueError("Each bid level must have [price, size]")
            if level[0] <= 0 or level[1] < 0:
                raise ValueError("Price must be positive, size must be non-negative")
        
        # Check if bids are sorted in descending order (highest first)
        prices = [level[0] for level in v]
        if prices != sorted(prices, reverse=True):
            raise ValueError("Bid levels must be sorted by price (highest first)")
        
        return v
    
    @validator('asks')
    def validate_asks(cls, v):
        """Validate ask levels are properly formatted and sorted"""
        if not v:
            return v
        
        for level in v:
            if len(level) != 2:
                raise ValueError("Each ask level must have [price, size]")
            if level[0] <= 0 or level[1] < 0:
                raise ValueError("Price must be positive, size must be non-negative")
        
        # Check if asks are sorted in ascending order (lowest first)
        prices = [level[0] for level in v]
        if prices != sorted(prices):
            raise ValueError("Ask levels must be sorted by price (lowest first)")
        
        return v
    
    @property
    def best_bid(self) -> Optional[float]:
        """Get best bid price"""
        return self.bids[0][0] if self.bids else None
    
    @property
    def best_ask(self) -> Optional[float]:
        """Get best ask price"""
        return self.asks[0][0] if self.asks else None
    
    @property
    def spread(self) -> Optional[float]:
        """Calculate best bid-ask spread"""
        if self.best_bid and self.best_ask:
            return self.best_ask - self.best_bid
        return None

class Candle(BaseModel):
    """OHLCV candle data"""
    symbol: str = Field(..., description="Trading symbol")
    open_price: float = Field(..., gt=0, description="Open price")
    high_price: float = Field(..., gt=0, description="High price")
    low_price: float = Field(..., gt=0, description="Low price")
    close_price: float = Field(..., gt=0, description="Close price")
    volume: int = Field(..., ge=0, description="Volume")
    timestamp: datetime = Field(..., description="Candle timestamp")
    interval: str = Field(..., description="Time interval (1m, 5m, 1h, etc.)")
    
    @validator('high_price')
    def validate_high(cls, v, values):
        """Validate high is the highest price"""
        open_price = values.get('open_price')
        if open_price and v < open_price:
            raise ValueError("High price must be >= open price")
        return v
    
    @validator('low_price')
    def validate_low(cls, v, values):
        """Validate low is the lowest price"""
        open_price = values.get('open_price')
        high_price = values.get('high_price')
        if open_price and v > open_price:
            raise ValueError("Low price must be <= open price")
        if high_price and v > high_price:
            raise ValueError("Low price must be <= high price")
        return v
    
    @validator('close_price')
    def validate_close(cls, v, values):
        """Validate close is within high/low range"""
        high_price = values.get('high_price')
        low_price = values.get('low_price')
        if high_price and v > high_price:
            raise ValueError("Close price must be <= high price")
        if low_price and v < low_price:
            raise ValueError("Close price must be >= low price")
        return v

class MarketStatus(BaseModel):
    """Market status information"""
    symbol: str = Field(..., description="Trading symbol")
    status: str = Field(..., description="Market status (open, closed, pre_market, after_hours)")
    session_start: Optional[datetime] = Field(None, description="Session start time")
    session_end: Optional[datetime] = Field(None, description="Session end time")
    timezone: str = Field("UTC", description="Timezone")
    is_trading: bool = Field(..., description="Whether trading is currently allowed")
    next_session_start: Optional[datetime] = Field(None, description="Next session start")

class SubscriptionRequest(BaseModel):
    """Market data subscription request"""
    symbol: str = Field(..., description="Symbol to subscribe to")
    data_types: List[str] = Field(
        default=["quotes", "trades"], 
        description="Types of data to subscribe to"
    )
    
    @validator('data_types')
    def validate_data_types(cls, v):
        """Validate data types"""
        valid_types = ["quotes", "trades", "orderbook", "candles", "level1", "level2"]
        for data_type in v:
            if data_type not in valid_types:
                raise ValueError(f"Invalid data type: {data_type}. Valid types: {valid_types}")
        return v

class SubscriptionResponse(BaseModel):
    """Market data subscription response"""
    symbol: str = Field(..., description="Subscribed symbol")
    status: str = Field(..., description="Subscription status")
    data_types: List[str] = Field(..., description="Subscribed data types")
    message: Optional[str] = Field(None, description="Status message")

class MarketDataUpdate(BaseModel):
    """Real-time market data update"""
    type: str = Field(..., description="Update type (quote, trade, orderbook)")
    symbol: str = Field(..., description="Trading symbol")
    data: Dict[str, Any] = Field(..., description="Update data")
    timestamp: datetime = Field(..., description="Update timestamp")
    sequence: Optional[int] = Field(None, description="Sequence number")

class TechnicalIndicator(BaseModel):
    """Technical indicator data"""
    symbol: str = Field(..., description="Trading symbol")
    indicator: str = Field(..., description="Indicator name (RSI, MACD, SMA, etc.)")
    value: float = Field(..., description="Indicator value")
    timestamp: datetime = Field(..., description="Calculation timestamp")
    period: Optional[int] = Field(None, description="Calculation period")
    parameters: Optional[Dict[str, Any]] = Field(None, description="Indicator parameters")
