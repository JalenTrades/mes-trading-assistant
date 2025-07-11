"""
WebSocket message models for MES Trading Assistant
"""

from datetime import datetime
from typing import Optional, Dict, Any, Union, List
from pydantic import BaseModel, Field, validator
from enum import Enum

class MessageType(str, Enum):
    """WebSocket message types"""
    # Client to server
    SUBSCRIBE = "subscribe"
    UNSUBSCRIBE = "unsubscribe"
    ORDER = "order"
    CANCEL_ORDER = "cancel_order"
    PING = "ping"
    
    # Server to client
    WELCOME = "welcome"
    SUBSCRIBE_RESPONSE = "subscribe_response"
    UNSUBSCRIBE_RESPONSE = "unsubscribe_response"
    ORDER_CONFIRMATION = "order_confirmation"
    ORDER_UPDATE = "order_update"
    MARKET_DATA = "market_data"
    POSITION_UPDATE = "position_update"
    ACCOUNT_UPDATE = "account_update"
    ERROR = "error"
    PONG = "pong"
    
    # System messages
    CONNECTION_STATUS = "connection_status"
    HEARTBEAT = "heartbeat"

class WebSocketMessage(BaseModel):
    """Base WebSocket message structure"""
    type: MessageType = Field(..., description="Message type")
    data: Optional[Dict[str, Any]] = Field(None, description="Message payload")
    timestamp: Optional[datetime] = Field(None, description="Message timestamp")
    client_id: Optional[str] = Field(None, description="Client identifier")
    request_id: Optional[str] = Field(None, description="Request correlation ID")
    
    class Config:
        use_enum_values = True

class WebSocketResponse(BaseModel):
    """WebSocket response message"""
    type: MessageType = Field(..., description="Response type")
    status: str = Field(..., description="Response status (success, error)")
    data: Optional[Dict[str, Any]] = Field(None, description="Response payload")
    message: Optional[str] = Field(None, description="Status message")
    error_code: Optional[str] = Field(None, description="Error code if applicable")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Response timestamp")
    request_id: Optional[str] = Field(None, description="Original request ID")
    
    class Config:
        use_enum_values = True

# Specific message types
class SubscribeMessage(BaseModel):
    """Market data subscription message"""
    type: MessageType = Field(MessageType.SUBSCRIBE, description="Message type")
    symbol: str = Field(..., description="Symbol to subscribe to")
    data_types: List[str] = Field(
        default=["quotes", "trades"], 
        description="Data types to subscribe to"
    )
    
    @validator('symbol')
    def validate_symbol(cls, v):
        if not v or not v.strip():
            raise ValueError("Symbol cannot be empty")
        return v.upper().strip()

class UnsubscribeMessage(BaseModel):
    """Market data unsubscription message"""
    type: MessageType = Field(MessageType.UNSUBSCRIBE, description="Message type")
    symbol: str = Field(..., description="Symbol to unsubscribe from")
    
    @validator('symbol')
    def validate_symbol(cls, v):
        if not v or not v.strip():
            raise ValueError("Symbol cannot be empty")
        return v.upper().strip()

class OrderMessage(BaseModel):
    """Order placement message"""
    type: MessageType = Field(MessageType.ORDER, description="Message type")
    data: Dict[str, Any] = Field(..., description="Order data")
    
    @validator('data')
    def validate_order_data(cls, v):
        required_fields = ['symbol', 'side', 'order_type', 'quantity']
        for field in required_fields:
            if field not in v:
                raise ValueError(f"Missing required field: {field}")
        return v

class CancelOrderMessage(BaseModel):
    """Order cancellation message"""
    type: MessageType = Field(MessageType.CANCEL_ORDER, description="Message type")
    order_id: str = Field(..., description="Order ID to cancel")
    symbol: Optional[str] = Field(None, description="Symbol for verification")
    
    @validator('order_id')
    def validate_order_id(cls, v):
        if not v or not v.strip():
            raise ValueError("Order ID cannot be empty")
        return v.strip()

class PingMessage(BaseModel):
    """Ping message for connection health check"""
    type: MessageType = Field(MessageType.PING, description="Message type")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Ping timestamp")

class WelcomeMessage(BaseModel):
    """Welcome message sent to new connections"""
    type: MessageType = Field(MessageType.WELCOME, description="Message type")
    client_id: str = Field(..., description="Assigned client ID")
    message: str = Field(..., description="Welcome message")
    server_time: datetime = Field(default_factory=datetime.utcnow, description="Server timestamp")
    features: List[str] = Field(
        default=["real_time_data", "order_management", "position_tracking"],
        description="Available features"
    )

class MarketDataMessage(BaseModel):
    """Market data update message"""
    type: MessageType = Field(MessageType.MARKET_DATA, description="Message type")
    symbol: str = Field(..., description="Trading symbol")
    data: Dict[str, Any] = Field(..., description="Market data")
    data_type: str = Field(..., description="Type of market data (quote, trade, etc.)")
    timestamp: datetime = Field(..., description="Data timestamp")
    sequence: Optional[int] = Field(None, description="Sequence number")

class OrderUpdateMessage(BaseModel):
    """Order status update message"""
    type: MessageType = Field(MessageType.ORDER_UPDATE, description="Message type")
    order_id: str = Field(..., description="Order ID")
    symbol: str = Field(..., description="Trading symbol")
    status: str = Field(..., description="Order status")
    filled_quantity: int = Field(0, ge=0, description="Filled quantity")
    remaining_quantity: int = Field(..., ge=0, description="Remaining quantity")
    average_fill_price: Optional[float] = Field(None, description="Average fill price")
    timestamp: datetime = Field(..., description="Update timestamp")
    reason: Optional[str] = Field(None, description="Update reason")

class PositionUpdateMessage(BaseModel):
    """Position update message"""
    type: MessageType = Field(MessageType.POSITION_UPDATE, description="Message type")
    symbol: str = Field(..., description="Trading symbol")
    size: int = Field(..., description="Position size")
    entry_price: float = Field(..., description="Average entry price")
    market_price: float = Field(..., description="Current market price")
    unrealized_pnl: float = Field(..., description="Unrealized P&L")
    timestamp: datetime = Field(..., description="Update timestamp")

class ErrorMessage(BaseModel):
    """Error message"""
    type: MessageType = Field(MessageType.ERROR, description="Message type")
    error_code: str = Field(..., description="Error code")
    message: str = Field(..., description="Error message")
    details: Optional[Dict[str, Any]] = Field(None, description="Additional error details")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Error timestamp")
    request_id: Optional[str] = Field(None, description="Related request ID")

class HeartbeatMessage(BaseModel):
    """Heartbeat message for connection monitoring"""
    type: MessageType = Field(MessageType.HEARTBEAT, description="Message type")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Heartbeat timestamp")
    server_uptime: Optional[int] = Field(None, description="Server uptime in seconds")
    active_connections: Optional[int] = Field(None, description="Number of active connections")

class ConnectionStatusMessage(BaseModel):
    """Connection status update message"""
    type: MessageType = Field(MessageType.CONNECTION_STATUS, description="Message type")
    status: str = Field(..., description="Connection status (connected, disconnected, reconnecting)")
    message: str = Field(..., description="Status message")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Status timestamp")
    
    @validator('status')
    def validate_status(cls, v):
        valid_statuses = ['connected', 'disconnected', 'reconnecting', 'error']
        if v.lower() not in valid_statuses:
            raise ValueError(f"Status must be one of: {valid_statuses}")
        return v.lower()

# Message factory for creating typed messages
class MessageFactory:
    """Factory for creating WebSocket messages"""
    
    @staticmethod
    def create_welcome(client_id: str, message: str = "Connected to MES Trading Assistant") -> WelcomeMessage:
        return WelcomeMessage(client_id=client_id, message=message)
    
    @staticmethod
    def create_error(error_code: str, message: str, request_id: str = None, 
                    details: Dict[str, Any] = None) -> ErrorMessage:
        return ErrorMessage(
            error_code=error_code,
            message=message,
            request_id=request_id,
            details=details
        )
    
    @staticmethod
    def create_market_data(symbol: str, data: Dict[str, Any], 
                          data_type: str = "quote") -> MarketDataMessage:
        return MarketDataMessage(
            symbol=symbol,
            data=data,
            data_type=data_type,
            timestamp=datetime.utcnow()
        )
    
    @staticmethod
    def create_order_update(order_id: str, symbol: str, status: str, 
                           filled_quantity: int = 0, remaining_quantity: int = 0,
                           average_fill_price: float = None, reason: str = None) -> OrderUpdateMessage:
        return OrderUpdateMessage(
            order_id=order_id,
            symbol=symbol,
            status=status,
            filled_quantity=filled_quantity,
            remaining_quantity=remaining_quantity,
            average_fill_price=average_fill_price,
            reason=reason,
            timestamp=datetime.utcnow()
        )
    
    @staticmethod
    def create_position_update(symbol: str, size: int, entry_price: float,
                              market_price: float, unrealized_pnl: float) -> PositionUpdateMessage:
        return PositionUpdateMessage(
            symbol=symbol,
            size=size,
            entry_price=entry_price,
            market_price=market_price,
            unrealized_pnl=unrealized_pnl,
            timestamp=datetime.utcnow()
        )
    
    @staticmethod
    def create_response(message_type: MessageType, status: str, data: Dict[str, Any] = None,
                       message: str = None, request_id: str = None) -> WebSocketResponse:
        return WebSocketResponse(
            type=message_type,
            status=status,
            data=data,
            message=message,
            request_id=request_id
        )
