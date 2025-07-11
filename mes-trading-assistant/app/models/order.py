"""
Order-related Pydantic models for MES Trading Assistant
"""

from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Optional, List
from pydantic import BaseModel, validator, Field

class OrderSide(str, Enum):
    """Order side enumeration"""
    BUY = "buy"
    SELL = "sell"

class OrderType(str, Enum):
    """Order type enumeration"""
    MARKET = "market"
    LIMIT = "limit"
    STOP = "stop"
    STOP_LIMIT = "stop_limit"

class OrderStatus(str, Enum):
    """Order status enumeration"""
    PENDING = "pending"
    OPEN = "open"
    FILLED = "filled"
    PARTIALLY_FILLED = "partially_filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"
    EXPIRED = "expired"

class TimeInForce(str, Enum):
    """Time in force enumeration"""
    DAY = "day"
    GTC = "gtc"  # Good Till Cancelled
    IOC = "ioc"  # Immediate or Cancel
    FOK = "fok"  # Fill or Kill

class Order(BaseModel):
    """Order model with comprehensive validation"""
    symbol: str = Field(..., description="Trading symbol (e.g., MES, ES)")
    side: OrderSide = Field(..., description="Order side (buy/sell)")
    order_type: OrderType = Field(..., description="Order type")
    quantity: int = Field(..., gt=0, description="Order quantity")
    price: Optional[float] = Field(None, gt=0, description="Limit price")
    stop_price: Optional[float] = Field(None, gt=0, description="Stop price")
    time_in_force: TimeInForce = Field(TimeInForce.DAY, description="Time in force")
    
    # Optional metadata
    client_order_id: Optional[str] = Field(None, description="Client-provided order ID")
    reduce_only: bool = Field(False, description="Reduce only order")
    post_only: bool = Field(False, description="Post only order")
    
    @validator('symbol')
    def validate_symbol(cls, v):
        """Validate trading symbol"""
        if not v or not v.strip():
            raise ValueError("Symbol cannot be empty")
        
        # Convert to uppercase and validate against allowed symbols
        symbol = v.upper().strip()
        allowed_symbols = ['MES', 'ES', 'NQ', 'YM', 'RTY', 'CL', 'GC', 'SI']
        
        if symbol not in allowed_symbols:
            raise ValueError(f"Symbol {symbol} not in allowed list: {allowed_symbols}")
        
        return symbol
    
    @validator('quantity')
    def validate_quantity(cls, v):
        """Validate order quantity"""
        if v <= 0:
            raise ValueError("Quantity must be positive")
        if v > 100:  # Max position size
            raise ValueError("Quantity cannot exceed 100 contracts")
        return v
    
    @validator('price')
    def validate_price(cls, v, values):
        """Validate price for limit orders"""
        order_type = values.get('order_type')
        if order_type in [OrderType.LIMIT, OrderType.STOP_LIMIT]:
            if v is None:
                raise ValueError(f"Price required for {order_type} orders")
            if v <= 0:
                raise ValueError("Price must be positive")
        return v
    
    @validator('stop_price')
    def validate_stop_price(cls, v, values):
        """Validate stop price for stop orders"""
        order_type = values.get('order_type')
        if order_type in [OrderType.STOP, OrderType.STOP_LIMIT]:
            if v is None:
                raise ValueError(f"Stop price required for {order_type} orders")
            if v <= 0:
                raise ValueError("Stop price must be positive")
        return v
    
    @validator('client_order_id')
    def validate_client_order_id(cls, v):
        """Validate client order ID"""
        if v is not None:
            if len(v.strip()) == 0:
                raise ValueError("Client order ID cannot be empty")
            if len(v) > 50:
                raise ValueError("Client order ID cannot exceed 50 characters")
        return v

class CancelOrderRequest(BaseModel):
    """Request to cancel an order"""
    order_id: str = Field(..., description="Order ID to cancel")
    symbol: Optional[str] = Field(None, description="Symbol for verification")
    
    @validator('order_id')
    def validate_order_id(cls, v):
        """Validate order ID"""
        if not v or not v.strip():
            raise ValueError("Order ID cannot be empty")
        return v.strip()

class OrderResponse(BaseModel):
    """Response from order operations"""
    status: str = Field(..., description="Operation status")
    order_id: Optional[str] = Field(None, description="Order ID")
    client_order_id: Optional[str] = Field(None, description="Client order ID")
    symbol: Optional[str] = Field(None, description="Trading symbol")
    side: Optional[OrderSide] = Field(None, description="Order side")
    order_type: Optional[OrderType] = Field(None, description="Order type")
    quantity: Optional[int] = Field(None, description="Order quantity")
    filled_quantity: Optional[int] = Field(None, description="Filled quantity")
    remaining_quantity: Optional[int] = Field(None, description="Remaining quantity")
    price: Optional[float] = Field(None, description="Order price")
    average_fill_price: Optional[float] = Field(None, description="Average fill price")
    order_status: Optional[OrderStatus] = Field(None, description="Order status")
    created_at: Optional[datetime] = Field(None, description="Order creation time")
    updated_at: Optional[datetime] = Field(None, description="Last update time")
    message: Optional[str] = Field(None, description="Status message")
    error_code: Optional[str] = Field(None, description="Error code if applicable")

class OrderFill(BaseModel):
    """Order fill information"""
    fill_id: str = Field(..., description="Fill ID")
    order_id: str = Field(..., description="Order ID")
    symbol: str = Field(..., description="Trading symbol")
    side: OrderSide = Field(..., description="Order side")
    quantity: int = Field(..., gt=0, description="Fill quantity")
    price: float = Field(..., gt=0, description="Fill price")
    timestamp: datetime = Field(..., description="Fill timestamp")
    commission: Optional[float] = Field(None, description="Commission paid")
    fee: Optional[float] = Field(None, description="Exchange fee")

class OrderBook(BaseModel):
    """Order book snapshot"""
    symbol: str = Field(..., description="Trading symbol")
    bids: List[List[float]] = Field(..., description="Bid levels [price, quantity]")
    asks: List[List[float]] = Field(..., description="Ask levels [price, quantity]")
    timestamp: datetime = Field(..., description="Snapshot timestamp")
    sequence: Optional[int] = Field(None, description="Sequence number")

class OrderUpdate(BaseModel):
    """Real-time order update"""
    order_id: str = Field(..., description="Order ID")
    client_order_id: Optional[str] = Field(None, description="Client order ID")
    symbol: str = Field(..., description="Trading symbol")
    side: OrderSide = Field(..., description="Order side")
    order_type: OrderType = Field(..., description="Order type")
    order_status: OrderStatus = Field(..., description="Order status")
    quantity: int = Field(..., description="Order quantity")
    filled_quantity: int = Field(0, description="Filled quantity")
    remaining_quantity: int = Field(..., description="Remaining quantity")
    price: Optional[float] = Field(None, description="Order price")
    average_fill_price: Optional[float] = Field(None, description="Average fill price")
    last_fill_price: Optional[float] = Field(None, description="Last fill price")
    last_fill_quantity: Optional[int] = Field(None, description="Last fill quantity")
    timestamp: datetime = Field(..., description="Update timestamp")
    reason: Optional[str] = Field(None, description="Update reason")

class BulkOrderRequest(BaseModel):
    """Bulk order request for multiple orders"""
    orders: List[Order] = Field(..., max_items=50, description="List of orders")
    
    @validator('orders')
    def validate_orders(cls, v):
        """Validate bulk orders"""
        if len(v) == 0:
            raise ValueError("At least one order required")
        if len(v) > 50:
            raise ValueError("Cannot submit more than 50 orders at once")
        return v

class BulkOrderResponse(BaseModel):
    """Response from bulk order submission"""
    submitted: int = Field(..., description="Number of orders submitted")
    accepted: int = Field(..., description="Number of orders accepted")
    rejected: int = Field(..., description="Number of orders rejected")
    orders: List[OrderResponse] = Field(..., description="Individual order responses")
    errors: List[str] = Field(default=[], description="Error messages")
