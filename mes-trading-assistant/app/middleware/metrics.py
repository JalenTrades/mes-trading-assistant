"""
Metrics middleware and service for MES Trading Assistant
"""

import time
import logging
from typing import Dict, Optional
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from prometheus_client import (
    Counter, Histogram, Gauge, generate_latest, 
    CONTENT_TYPE_LATEST, CollectorRegistry, REGISTRY
)

logger = logging.getLogger(__name__)

# Custom registry for this application
app_registry = CollectorRegistry()

# Define metrics
http_requests_total = Counter(
    'http_requests_total',
    'Total HTTP requests',
    ['method', 'endpoint', 'status_code'],
    registry=app_registry
)

http_request_duration_seconds = Histogram(
    'http_request_duration_seconds',
    'HTTP request duration in seconds',
    ['method', 'endpoint'],
    registry=app_registry
)

websocket_connections_total = Counter(
    'websocket_connections_total',
    'Total WebSocket connections',
    ['type'],  # connect, disconnect
    registry=app_registry
)

websocket_connections_active = Gauge(
    'websocket_connections_active',
    'Active WebSocket connections',
    registry=app_registry
)

trading_orders_total = Counter(
    'trading_orders_total',
    'Total trading orders',
    ['symbol', 'side', 'order_type', 'status'],
    registry=app_registry
)

trading_order_duration_seconds = Histogram(
    'trading_order_duration_seconds',
    'Time taken to process orders',
    ['symbol', 'order_type'],
    registry=app_registry
)

market_data_messages_total = Counter(
    'market_data_messages_total',
    'Total market data messages processed',
    ['symbol', 'data_type'],
    registry=app_registry
)

ironbeam_connection_status = Gauge(
    'ironbeam_connection_status',
    'Ironbeam connection status (1=connected, 0=disconnected)',
    registry=app_registry
)

account_balance = Gauge(
    'account_balance',
    'Account balance',
    ['currency'],
    registry=app_registry
)

position_value = Gauge(
    'position_value',
    'Position market value',
    ['symbol', 'side'],
    registry=app_registry
)

position_pnl = Gauge(
    'position_pnl',
    'Position unrealized P&L',
    ['symbol'],
    registry=app_registry
)

# Error tracking
application_errors_total = Counter(
    'application_errors_total',
    'Total application errors',
    ['error_type', 'endpoint'],
    registry=app_registry
)

class MetricsService:
    """Service for recording application metrics"""
    
    @staticmethod
    def record_http_request(method: str, endpoint: str, status_code: int, duration: float):
        """Record HTTP request metrics"""
        http_requests_total.labels(
            method=method,
            endpoint=endpoint,
            status_code=status_code
        ).inc()
        
        http_request_duration_seconds.labels(
            method=method,
            endpoint=endpoint
        ).observe(duration)
    
    @staticmethod
    def record_websocket_connection(connection_type: str):
        """Record WebSocket connection event"""
        websocket_connections_total.labels(type=connection_type).inc()
    
    @staticmethod
    def update_active_websocket_connections(count: int):
        """Update active WebSocket connections count"""
        websocket_connections_active.set(count)
    
    @staticmethod
    def record_order(symbol: str, side: str, order_type: str, status: str, duration: float = None):
        """Record trading order metrics"""
        trading_orders_total.labels(
            symbol=symbol,
            side=side,
            order_type=order_type,
            status=status
        ).inc()
        
        if duration is not None:
            trading_order_duration_seconds.labels(
                symbol=symbol,
                order_type=order_type
            ).observe(duration)
    
    @staticmethod
    def record_market_data(symbol: str, data_type: str):
        """Record market data message"""
        market_data_messages_total.labels(
            symbol=symbol,
            data_type=data_type
        ).inc()
    
    @staticmethod
    def update_ironbeam_status(connected: bool):
        """Update Ironbeam connection status"""
        ironbeam_connection_status.set(1 if connected else 0)
    
    @staticmethod
    def update_account_balance(currency: str, balance: float):
        """Update account balance metric"""
        account_balance.labels(currency=currency).set(balance)
    
    @staticmethod
    def update_position_metrics(symbol: str, side: str, market_value: float, unrealized_pnl: float):
        """Update position metrics"""
        position_value.labels(symbol=symbol, side=side).set(market_value)
        position_pnl.labels(symbol=symbol).set(unrealized_pnl)
    
    @staticmethod
    def record_error(error_type: str, endpoint: str = "unknown"):
        """Record application error"""
        application_errors_total.labels(
            error_type=error_type,
            endpoint=endpoint
        ).inc()
    
    @staticmethod
    def get_metrics() -> str:
        """Get Prometheus metrics in text format"""
        return generate_latest(app_registry)

class MetricsMiddleware(BaseHTTPMiddleware):
    """Middleware for automatic HTTP request metrics collection"""
    
    def __init__(self, app):
        super().__init__(app)
        logger.info("Metrics middleware initialized")
    
    async def dispatch(self, request: Request, call_next):
        # Skip metrics collection for the metrics endpoint itself
        if request.url.path == "/metrics":
            return await call_next(request)
        
        start_time = time.time()
        method = request.method
        path = request.url.path
        
        # Normalize endpoint path (remove dynamic parts)
        endpoint = self._normalize_endpoint(path)
        
        try:
            response = await call_next(request)
            status_code = response.status_code
            
        except Exception as e:
            # Record error metric
            MetricsService.record_error(
                error_type=type(e).__name__,
                endpoint=endpoint
            )
            # Set error status code
            status_code = 500
            raise
        
        finally:
            # Calculate duration
            duration = time.time() - start_time
            
            # Record metrics
            MetricsService.record_http_request(
                method=method,
                endpoint=endpoint,
                status_code=status_code,
                duration=duration
            )
            
            # Log slow requests
            if duration > 1.0:  # Log requests taking more than 1 second
                logger.warning(f"Slow request: {method} {endpoint} took {duration:.2f}s")
        
        return response
    
    def _normalize_endpoint(self, path: str) -> str:
        """Normalize endpoint path for consistent metrics"""
        # Remove query parameters
        if "?" in path:
            path = path.split("?")[0]
        
        # Normalize common patterns
        path_parts = path.split("/")
        normalized_parts = []
        
        for part in path_parts:
            # Replace UUIDs and numeric IDs with placeholders
            if self._looks_like_uuid(part):
                normalized_parts.append("{uuid}")
