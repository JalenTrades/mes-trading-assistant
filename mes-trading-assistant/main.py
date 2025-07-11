"""
MES Trading Assistant - Main Application Entry Point

Institutional-grade MES futures trading assistant with:
- Real-time WebSocket connections to Ironbeam
- REST API and WebSocket endpoints
- Enterprise-level error handling and logging
- Modular architecture for scalability
"""

import asyncio
import logging
import uuid
from typing import Dict

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, validator
from enum import Enum

# Import from our new modular structure
from app.config import get_settings
from app.services.ironbeam_client import IronbeamClient, OrderData

# Initialize settings
settings = get_settings()

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.log_level),
    format=settings.log_format
)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="Institutional-grade MES Futures Trading Assistant",
    docs_url="/api/docs",
    redoc_url="/api/redoc"
)

# CORS Configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Enums for validation
class OrderSide(str, Enum):
    BUY = "buy"
    SELL = "sell"

class OrderType(str, Enum):
    MARKET = "market"
    LIMIT = "limit"
    STOP = "stop"
    STOP_LIMIT = "stop_limit"

# Pydantic Models
class Order(BaseModel):
    symbol: str
    side: OrderSide
    order_type: OrderType
    quantity: int
    price: float = None
    stop_price: float = None
    
    @validator('symbol')
    def validate_symbol(cls, v):
        # Add symbol validation logic here
        allowed_symbols = ['MES', 'ES', 'NQ', 'YM']  # Example symbols
        if v.upper() not in allowed_symbols:
            logger.warning(f"Trading symbol {v} not in approved list")
        return v.upper()
    
    @validator('quantity')
    def validate_quantity(cls, v):
        if v <= 0:
            raise ValueError('Quantity must be positive')
        if v > settings.max_position_size:
            raise ValueError(f'Quantity cannot exceed {settings.max_position_size}')
        return v
    
    @validator('price')
    def validate_price(cls, v, values):
        if values.get('order_type') in ['limit', 'stop_limit'] and v is None:
            raise ValueError('Price required for limit and stop_limit orders')
        if v is not None and v <= 0:
            raise ValueError('Price must be positive')
        return v
    
    @validator('stop_price')
    def validate_stop_price(cls, v, values):
        if values.get('order_type') in ['stop', 'stop_limit'] and v is None:
            raise ValueError('Stop price required for stop orders')
        if v is not None and v <= 0:
            raise ValueError('Stop price must be positive')
        return v

class CancelOrderRequest(BaseModel):
    order_id: str
    
    @validator('order_id')
    def validate_order_id(cls, v):
        if not v or not v.strip():
            raise ValueError('Order ID cannot be empty')
        return v.strip()

# WebSocket client management
clients: Dict[str, WebSocket] = {}

# Real-time event callbacks
async def on_market_data(data: dict):
    """Broadcast market data to all connected clients"""
    if not data:
        return
        
    message = {"type": "market_data", "data": data}
    disconnected_clients = []
    
    for client_id, websocket in clients.items():
        try:
            await websocket.send_json(message)
        except Exception as e:
            logger.warning(f"Failed to send market data to client {client_id}: {e}")
            disconnected_clients.append(client_id)
    
    # Clean up disconnected clients
    for client_id in disconnected_clients:
        clients.pop(client_id, None)

async def on_order_update(data: dict):
    """Broadcast order updates to all connected clients"""
    if not data:
        return
        
    message = {"type": "order_update", "data": data}
    disconnected_clients = []
    
    for client_id, websocket in clients.items():
        try:
            await websocket.send_json(message)
        except Exception as e:
            logger.warning(f"Failed to send order update to client {client_id}: {e}")
            disconnected_clients.append(client_id)
    
    # Clean up disconnected clients
    for client_id in disconnected_clients:
        clients.pop(client_id, None)

async def on_position_update(data: dict):
    """Broadcast position updates to all connected clients"""
    if not data:
        return
        
    message = {"type": "position_update", "data": data}
    disconnected_clients = []
    
    for client_id, websocket in clients.items():
        try:
            await websocket.send_json(message)
        except Exception as e:
            logger.warning(f"Failed to send position update to client {client_id}: {e}")
            disconnected_clients.append(client_id)
    
    # Clean up disconnected clients
    for client_id in disconnected_clients:
        clients.pop(client_id, None)

# Initialize Ironbeam client
ironbeam = IronbeamClient(
    api_key=settings.ironbeam_api_key,
    secret=settings.ironbeam_secret,
    base_url=settings.ironbeam_base_url,
    on_market_data=on_market_data,
    on_order_update=on_order_update,
    on_position_update=on_position_update
)

# Routes
@app.get("/")
async def root():
    """Root endpoint with system information"""
    return {
        "message": f"{settings.app_name} Running",
        "version": settings.app_version,
        "status": "healthy",
        "environment": "development" if settings.debug else "production"
    }

@app.get("/health")
async def health_check():
    """Health check endpoint for monitoring"""
    connection_stats = ironbeam.get_connection_stats()
    
    return {
        "status": "healthy",
        "timestamp": "2025-01-01T00:00:00Z",  # You might want to use real timestamp
        "ironbeam_connected": connection_stats["connected"],
        "active_clients": len(clients),
        "subscriptions": connection_stats["active_subscriptions"],
        "pending_requests": connection_stats["pending_requests"],
        "version": settings.app_version
    }

@app.get("/api/status")
async def detailed_status():
    """Detailed system status for debugging"""
    if not settings.debug:
        raise HTTPException(status_code=404, detail="Not found")
    
    return {
        "ironbeam": ironbeam.get_connection_stats(),
        "websocket_clients": len(clients),
        "settings": {
            "debug": settings.debug,
            "log_level": settings.log_level,
            "max_position_size": settings.max_position_size,
            "default_symbol": settings.default_symbol
        }
    }

# WebSocket endpoint
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time communication"""
    client_id = str(uuid.uuid4())
    await websocket.accept()
    clients[client_id] = websocket
    logger.info(f"Client {client_id} connected. Total clients: {len(clients)}")
    
    try:
        # Send welcome message
        await websocket.send_json({
            "type": "welcome",
            "client_id": client_id,
            "message": "Connected to MES Trading Assistant"
        })
        
        while True:
            data = await websocket.receive_json()
            await process_websocket_message(client_id, data)
            
    except WebSocketDisconnect:
        logger.info(f"Client {client_id} disconnected")
    except Exception as e:
        logger.error(f"WebSocket error for client {client_id}: {str(e)}")
    finally:
        clients.pop(client_id, None)
        logger.info(f"Client {client_id} cleaned up. Remaining clients: {len(clients)}")

async def process_websocket_message(client_id: str, data: dict):
    """Process incoming WebSocket messages"""
    try:
        event_type = data.get("type")
        websocket = clients[client_id]
        
        if event_type == "subscribe":
            symbol = data.get("symbol")
            if symbol:
                result = await ironbeam.subscribe(symbol)
                await websocket.send_json({"type": "subscribe_response", "data": result})
            else:
                await websocket.send_json({"type": "error", "message": "Symbol required for subscription"})
                
        elif event_type == "unsubscribe":
            symbol = data.get("symbol")
            if symbol:
                result = await ironbeam.unsubscribe(symbol)
                await websocket.send_json({"type": "unsubscribe_response", "data": result})
                
        elif event_type == "order":
            order_data = data.get("data")
            if order_data:
                try:
                    order = Order(**order_data)
                    order_data_obj = OrderData(
                        symbol=order.symbol,
                        side=order.side,
                        order_type=order.order_type,
                        quantity=order.quantity,
                        price=order.price,
                        stop_price=order.stop_price
                    )
                    response = await ironbeam.place_order(order_data_obj)
                    await websocket.send_json({"type": "order_confirmation", "data": response})
                except ValueError as e:
                    await websocket.send_json({"type": "validation_error", "message": str(e)})
                except Exception as e:
                    await websocket.send_json({"type": "error", "message": str(e)})
            else:
                await websocket.send_json({"type": "error", "message": "Order data required"})
                
        elif event_type == "ping":
            await websocket.send_json({"type": "pong", "timestamp": data.get("timestamp")})
            
        else:
            await websocket.send_json({"type": "error", "message": f"Unknown message type: {event_type}"})
            
    except Exception as e:
        logger.error(f"Error processing WebSocket message from {client_id}: {str(e)}")
        try:
            await clients[client_id].send_json({"type": "error", "message": "Internal server error"})
        except:
            pass  # Client might be disconnected

# REST API Endpoints
@app.post("/api/place_order")
async def place_order(order: Order):
    """Place a trading order via REST API"""
    try:
        logger.info(f"REST API: Placing order {order.symbol} {order.side} {order.quantity}")
        
        order_data = OrderData(
            symbol=order.symbol,
            side=order.side,
            order_type=order.order_type,
            quantity=order.quantity,
            price=order.price,
            stop_price=order.stop_price
        )
        
        result = await ironbeam.place_order(order_data)
        return JSONResponse(content=result)
        
    except Exception as e:
        logger.error(f"Error placing order via REST: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/positions")
async def get_positions():
    """Get current positions via REST API"""
    try:
        result = await ironbeam.get_positions()
        return JSONResponse(content=result)
    except Exception as e:
        logger.error(f"Error getting positions via REST: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/cancel_order")
async def cancel_order(request: CancelOrderRequest):
    """Cancel an existing order via REST API"""
    try:
        logger.info(f"REST API: Cancelling order {request.order_id}")
        result = await ironbeam.cancel_order(request.order_id)
        return JSONResponse(content=result)
    except Exception as e:
        logger.error(f"Error cancelling order via REST: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/account_info")
async def get_account_info():
    """Get account information via REST API"""
    try:
        result = await ironbeam.get_account_info()
        return JSONResponse(content=result)
    except Exception as e:
        logger.error(f"Error getting account info via REST: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/subscriptions")
async def get_subscriptions():
    """Get current market data subscriptions"""
    return {
        "subscriptions": list(ironbeam.subscriptions),
        "count": len(ironbeam.subscriptions)
    }

# Application lifecycle events
@app.on_event("startup")
async def startup_event():
    """Initialize connections and services on startup"""
    logger.info(f"Starting {settings.app_name} v{settings.app_version}")
    logger.info(f"Debug mode: {settings.debug}")
    logger.info(f"Log level: {settings.log_level}")
    
    try:
        await ironbeam.connect()
        logger.info("Ironbeam client connected successfully")
    except Exception as e:
        logger.error(f"Failed to connect to Ironbeam: {e}")

@app.on_event("shutdown")
async def shutdown_event():
    """Clean up connections and resources on shutdown"""
    logger.info("Shutting down MES Trading Assistant")
    
    # Disconnect all WebSocket clients
    for client_id in list(clients.keys()):
        try:
            await clients[client_id].close()
        except:
            pass
    clients.clear()
    
    # Disconnect from Ironbeam
    try:
        await ironbeam.disconnect()
        logger.info("Ironbeam client disconnected")
    except Exception as e:
        logger.error(f"Error disconnecting from Ironbeam: {e}")

# Serve static files (if you have a frontend)
# app.mount("/static", StaticFiles(directory="static"), name="static")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.reload,
        log_level=settings.log_level.lower()
    )
