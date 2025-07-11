"""
Enhanced Ironbeam WebSocket Client for MES Trading Assistant

Provides robust WebSocket connection management, order execution,
and real-time market data streaming for institutional trading.
"""

import asyncio
import json
import websockets
import logging
from datetime import datetime
from typing import Dict, Any, Optional, Callable
from dataclasses import dataclass

@dataclass
class OrderData:
    """Order data structure for trading operations"""
    symbol: str
    side: str
    order_type: str
    quantity: int
    price: Optional[float] = None
    stop_price: Optional[float] = None

class IronbeamClient:
    """
    Enhanced Ironbeam WebSocket client with enterprise features:
    - Automatic reconnection with exponential backoff
    - Request/response correlation with timeouts
    - Comprehensive error handling and logging
    - Real-time event callbacks
    - Connection health monitoring
    """
    
    def __init__(self, api_key: str, secret: str, base_url: str, 
                 on_market_data: Optional[Callable] = None,
                 on_order_update: Optional[Callable] = None, 
                 on_position_update: Optional[Callable] = None):
        self.api_key = api_key
        self.api_secret = secret
        self.base_url = base_url
        self.ws = None
        self.connected = False
        self.subscriptions = set()
        self.reconnect_attempts = 0
        self.max_reconnect_attempts = 10
        self.pending_requests = {}
        self.request_id = 0

        # Event callbacks
        self.on_market_data = on_market_data
        self.on_order_update = on_order_update
        self.on_position_update = on_position_update

        # Setup logging
        self.logger = logging.getLogger(__name__)

    def is_connected(self) -> bool:
        """Check if client is connected to Ironbeam"""
        return self.connected and self.ws is not None

    async def connect(self):
        """Connect to Ironbeam WebSocket with retry logic"""
        while not self.connected and self.reconnect_attempts < self.max_reconnect_attempts:
            try:
                self.logger.info(f"Connecting to Ironbeam WebSocket: {self.base_url}")
                self.ws = await websockets.connect(
                    self.base_url,
                    ping_interval=20,
                    ping_timeout=10,
                    close_timeout=10
                )
                await self.authenticate()
                self.connected = True
                self.reconnect_attempts = 0
                
                # Start listening task
                asyncio.create_task(self.listen())
                self.logger.info("Successfully connected to Ironbeam")
                
            except Exception as e:
                self.reconnect_attempts += 1
                wait_time = min(5 * self.reconnect_attempts, 60)
                self.logger.error(f"WebSocket connection failed (attempt {self.reconnect_attempts}): {e}")
                self.logger.info(f"Retrying in {wait_time} seconds...")
                await asyncio.sleep(wait_time)
        
        if not self.connected:
            self.logger.error("Max reconnection attempts reached. Unable to connect to Ironbeam.")

    async def disconnect(self):
        """Gracefully disconnect from WebSocket"""
        self.connected = False
        if self.ws:
            try:
                await self.ws.close()
                self.logger.info("WebSocket connection closed gracefully")
            except Exception as e:
                self.logger.error(f"Error closing WebSocket: {e}")
        
        # Clear pending requests
        for request_id, future in self.pending_requests.items():
            if not future.done():
                future.set_exception(Exception("Connection closed"))
        self.pending_requests.clear()

    async def authenticate(self):
        """Authenticate with Ironbeam API"""
        auth_message = {
            "action": "authenticate",
            "api_key": self.api_key,
            "secret": self.api_secret,
            "timestamp": datetime.utcnow().isoformat()
        }
        await self.send(auth_message)
        self.logger.info("Sent authentication message to Ironbeam")

    async def listen(self):
        """Listen for incoming WebSocket messages"""
        try:
            async for message in self.ws:
                await self.handle_message(message)
        except websockets.exceptions.ConnectionClosed:
            self.logger.warning("WebSocket connection closed by server")
        except Exception as e:
            self.logger.error(f"WebSocket listen error: {e}")
        finally:
            self.connected = False
            if self.reconnect_attempts < self.max_reconnect_attempts:
                self.logger.info("Attempting to reconnect...")
                await self.connect()

    async def handle_message(self, message: str):
        """Handle incoming WebSocket messages"""
        try:
            data = json.loads(message)
            event_type = data.get("type")
            request_id = data.get("request_id")

            # Handle responses to pending requests
            if request_id and request_id in self.pending_requests:
                future = self.pending_requests.pop(request_id)
                if not future.done():
                    future.set_result(data)
                return

            # Handle real-time events
            if event_type == "market_data" and self.on_market_data:
                await self.on_market_data(data.get("data", {}))
            elif event_type == "order_update" and self.on_order_update:
                await self.on_order_update(data.get("data", {}))
            elif event_type == "position_update" and self.on_position_update:
                await self.on_position_update(data.get("data", {}))
            elif event_type == "error":
                self.logger.error(f"Ironbeam error: {data.get('message', 'Unknown error')}")
            else:
                self.logger.debug(f"Unhandled message type '{event_type}': {data}")
                
        except json.JSONDecodeError:
            self.logger.error(f"Failed to decode message: {message}")
        except Exception as e:
            self.logger.error(f"Error handling message: {e}")

    async def subscribe(self, symbol: str, websocket_client=None) -> Dict[str, Any]:
        """Subscribe to market data for a symbol"""
        if symbol in self.subscriptions:
            return {"status": "already_subscribed", "symbol": symbol}
        
        request_id = self._get_request_id()
        message = {
            "action": "subscribe",
            "request_id": request_id,
            "symbol": symbol
        }
        
        try:
            response = await self.send_with_response(message, request_id, timeout=5.0)
            self.subscriptions.add(symbol)
            self.logger.info(f"Subscribed to market data: {symbol}")
            return {"status": "subscribed", "symbol": symbol, "data": response}
        except Exception as e:
            self.logger.error(f"Failed to subscribe to {symbol}: {e}")
            return {"status": "error", "message": str(e), "symbol": symbol}

    async def unsubscribe(self, symbol: str) -> Dict[str, Any]:
        """Unsubscribe from market data"""
        if symbol not in self.subscriptions:
            return {"status": "not_subscribed", "symbol": symbol}
        
        request_id = self._get_request_id()
        message = {
            "action": "unsubscribe",
            "request_id": request_id,
            "symbol": symbol
        }
        
        try:
            response = await self.send_with_response(message, request_id, timeout=5.0)
            self.subscriptions.discard(symbol)
            self.logger.info(f"Unsubscribed from: {symbol}")
            return {"status": "unsubscribed", "symbol": symbol, "data": response}
        except Exception as e:
            self.logger.error(f"Failed to unsubscribe from {symbol}: {e}")
            return {"status": "error", "message": str(e), "symbol": symbol}

    async def place_order(self, order: OrderData) -> Dict[str, Any]:
        """Place a trading order"""
        request_id = self._get_request_id()
        
        order_message = {
            "action": "place_order",
            "request_id": request_id,
            "symbol": order.symbol,
            "side": order.side,
            "order_type": order.order_type,
            "quantity": order.quantity,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        if order.price is not None:
            order_message["price"] = order.price
        if order.stop_price is not None:
            order_message["stop_price"] = order.stop_price

        try:
            response = await self.send_with_response(order_message, request_id, timeout=10.0)
            self.logger.info(f"Placed order: {order.symbol} {order.side} {order.quantity} @ {order.price or 'market'}")
            return response
        except Exception as e:
            self.logger.error(f"Failed to place order: {e}")
            return {"status": "error", "message": str(e)}

    async def cancel_order(self, order_id: str) -> Dict[str, Any]:
        """Cancel an existing order"""
        request_id = self._get_request_id()
        
        message = {
            "action": "cancel_order",
            "request_id": request_id,
            "order_id": order_id,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        try:
            response = await self.send_with_response(message, request_id, timeout=10.0)
            self.logger.info(f"Cancelled order: {order_id}")
            return response
        except Exception as e:
            self.logger.error(f"Failed to cancel order {order_id}: {e}")
            return {"status": "error", "message": str(e)}

    async def get_positions(self) -> Dict[str, Any]:
        """Get current positions"""
        request_id = self._get_request_id()
        
        message = {
            "action": "get_positions",
            "request_id": request_id,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        try:
            response = await self.send_with_response(message, request_id, timeout=10.0)
            return response
        except Exception as e:
            self.logger.error(f"Failed to get positions: {e}")
            return {"status": "error", "message": str(e)}

    async def get_account_info(self) -> Dict[str, Any]:
        """Get account information"""
        request_id = self._get_request_id()
        
        message = {
            "action": "get_account_info",
            "request_id": request_id,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        try:
            response = await self.send_with_response(message, request_id, timeout=10.0)
            return response
        except Exception as e:
            self.logger.error(f"Failed to get account info: {e}")
            return {"status": "error", "message": str(e)}

    async def send_with_response(self, message: Dict[str, Any], request_id: str, timeout: float = 10.0) -> Dict[str, Any]:
        """Send message and wait for response with timeout"""
        if not self.is_connected():
            raise Exception("WebSocket not connected")
        
        # Create future for response
        future = asyncio.Future()
        self.pending_requests[request_id] = future
        
        try:
            # Send message
            await self.send(message)
            
            # Wait for response with timeout
            response = await asyncio.wait_for(future, timeout=timeout)
            return response
        except asyncio.TimeoutError:
            # Clean up pending request
            self.pending_requests.pop(request_id, None)
            raise Exception(f"Request {request_id} timed out after {timeout}s")
        except Exception as e:
            # Clean up pending request
            self.pending_requests.pop(request_id, None)
            raise e

    async def send(self, message: Dict[str, Any]):
        """Send message to WebSocket"""
        if not self.is_connected():
            raise Exception("WebSocket not connected")
        
        try:
            message_str = json.dumps(message)
            await self.ws.send(message_str)
            self.logger.debug(f"Sent message: {message.get('action', 'unknown')}")
        except Exception as e:
            self.logger.error(f"Failed to send message: {e}")
            self.connected = False
            raise e

    def _get_request_id(self) -> str:
        """Generate unique request ID"""
        self.request_id += 1
        return f"req_{self.request_id}_{int(datetime.now().timestamp() * 1000)}"

    def get_connection_stats(self) -> Dict[str, Any]:
        """Get connection statistics"""
        return {
            "connected": self.connected,
            "reconnect_attempts": self.reconnect_attempts,
            "active_subscriptions": len(self.subscriptions),
            "pending_requests": len(self.pending_requests),
            "subscriptions": list(self.subscriptions)
        }
