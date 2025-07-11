"""
Authentication middleware for MES Trading Assistant
"""

import os
import jwt
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from fastapi import HTTPException, Depends, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from app.config import settings

logger = logging.getLogger(__name__)
security = HTTPBearer(auto_error=False)

class AuthService:
    """Authentication service for JWT token management"""
    
    @staticmethod
    def create_access_token(user_id: str, scopes: list = None) -> str:
        """Create JWT access token"""
        if scopes is None:
            scopes = ["read", "write", "trade"]
            
        expire = datetime.utcnow() + timedelta(hours=settings.jwt_expiration_hours)
        to_encode = {
            "sub": user_id,
            "exp": expire,
            "iat": datetime.utcnow(),
            "scopes": scopes,
            "type": "access_token"
        }
        
        return jwt.encode(to_encode, settings.jwt_secret, algorithm=settings.jwt_algorithm)
    
    @staticmethod
    def create_api_key_token(api_key: str, permissions: list = None) -> str:
        """Create token for API key authentication"""
        if permissions is None:
            permissions = ["read", "trade"]
            
        expire = datetime.utcnow() + timedelta(days=30)  # API keys last longer
        to_encode = {
            "sub": f"api_key:{api_key}",
            "exp": expire,
            "iat": datetime.utcnow(),
            "permissions": permissions,
            "type": "api_key"
        }
        
        return jwt.encode(to_encode, settings.jwt_secret, algorithm=settings.jwt_algorithm)
    
    @staticmethod
    def verify_token(token: str) -> Dict[str, Any]:
        """Verify and decode JWT token"""
        try:
            payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
            user_id = payload.get("sub")
            token_type = payload.get("type", "access_token")
            
            if user_id is None:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid token: missing user ID"
                )
            
            return {
                "user_id": user_id,
                "token_type": token_type,
                "scopes": payload.get("scopes", []),
                "permissions": payload.get("permissions", []),
                "exp": payload.get("exp"),
                "iat": payload.get("iat")
            }
            
        except jwt.ExpiredSignatureError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token has expired"
            )
        except jwt.JWTError as e:
            logger.error(f"JWT verification error: {e}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token"
            )
    
    @staticmethod
    def verify_api_key(api_key: str) -> bool:
        """Verify API key against environment"""
        valid_keys = os.getenv("VALID_API_KEYS", "").split(",")
        return api_key in [key.strip() for key in valid_keys if key.strip()]

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> Optional[Dict[str, Any]]:
    """Dependency to get current authenticated user (optional)"""
    if not credentials:
        return None
    
    try:
        return AuthService.verify_token(credentials.credentials)
    except HTTPException:
        return None

async def require_auth(credentials: HTTPAuthorizationCredentials = Depends(security)) -> Dict[str, Any]:
    """Dependency to require authentication"""
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    return AuthService.verify_token(credentials.credentials)

def require_scopes(*required_scopes: str):
    """Decorator to require specific scopes"""
    def scope_dependency(user: Dict[str, Any] = Depends(require_auth)) -> Dict[str, Any]:
        user_scopes = user.get("scopes", [])
        user_permissions = user.get("permissions", [])
        
        # Check if user has any of the required scopes
        for scope in required_scopes:
            if scope in user_scopes or scope in user_permissions:
                return user
        
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Insufficient permissions. Required: {required_scopes}"
        )
    
    return scope_dependency

# Specific permission dependencies
require_read = require_scopes("read")
require_write = require_scopes("write")
require_trade = require_scopes("trade")
require_admin = require_scopes("admin")

class AuthMiddleware(BaseHTTPMiddleware):
    """Authentication middleware for protecting routes"""
    
    def __init__(self, app, protected_paths: list = None):
        super().__init__(app)
        self.protected_paths = protected_paths or [
            "/api/place_order",
            "/api/cancel_order",
            "/api/positions",
            "/api/account_info"
        ]
    
    async def dispatch(self, request: Request, call_next):
        # Skip auth for public endpoints
        if self._is_public_endpoint(request.url.path):
            return await call_next(request)
        
        # Check if this is a protected path
        if not self._is_protected_path(request.url.path):
            return await call_next(request)
        
        # Extract and verify token
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={"detail": "Authentication required"}
            )
        
        token = auth_header.split(" ")[1]
        
        try:
            user = AuthService.verify_token(token)
            # Add user info to request state
            request.state.user = user
            logger.info(f"Authenticated user: {user['user_id']} for {request.url.path}")
            
        except HTTPException as e:
            logger.warning(f"Authentication failed for {request.url.path}: {e.detail}")
            return JSONResponse(
                status_code=e.status_code,
                content={"detail": e.detail}
            )
        
        return await call_next(request)
    
    def _is_public_endpoint(self, path: str) -> bool:
        """Check if endpoint is public"""
        public_endpoints = [
            "/",
            "/health",
            "/docs",
            "/redoc",
            "/openapi.json",
            "/auth/login",
            "/auth/register"
        ]
        return path in public_endpoints or path.startswith("/static")
    
    def _is_protected_path(self, path: str) -> bool:
        """Check if path requires authentication"""
        return any(path.startswith(protected) for protected in self.protected_paths)

class APIKeyAuth:
    """API Key authentication for external integrations"""
    
    @staticmethod
    async def verify_api_key(request: Request) -> Optional[str]:
        """Verify API key from headers"""
        api_key = request.headers.get("X-API-Key")
        if not api_key:
            return None
        
        if AuthService.verify_api_key(api_key):
            return api_key
        
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key"
        )

# WebSocket authentication helper
class WebSocketAuth:
    """WebSocket authentication utilities"""
    
    @staticmethod
    def verify_websocket_token(token: str) -> Dict[str, Any]:
        """Verify token for WebSocket connections"""
        try:
            return AuthService.verify_token(token)
        except HTTPException:
            return None
    
    @staticmethod
    def extract_token_from_query(query_string: str) -> Optional[str]:
        """Extract token from WebSocket query parameters"""
        # Parse query string manually for token
        if not query_string:
            return None
        
        params = {}
        for param in query_string.decode().split("&"):
            if "=" in param:
                key, value = param.split("=", 1)
                params[key] = value
        
        return params.get("token")

# Demo/development authentication
class DemoAuth:
    """Demo authentication for development/testing"""
    
    @staticmethod
    def create_demo_token(user_id: str = "demo_user") -> str:
        """Create demo token for testing"""
        return AuthService.create_access_token(
            user_id=user_id,
            scopes=["read", "write", "trade", "admin"]
        )
    
    @staticmethod
    def is_demo_mode() -> bool:
        """Check if running in demo mode"""
        return settings.debug or os.getenv("DEMO_MODE", "false").lower() == "true"

# Utility functions
def get_user_from_request(request: Request) -> Optional[Dict[str, Any]]:
    """Get user info from request state"""
    return getattr(request.state, "user", None)

def require_trading_permissions(user: Dict[str, Any] = Depends(require_auth)) -> Dict[str, Any]:
    """Require trading permissions specifically"""
    scopes = user.get("scopes", [])
    permissions = user.get("permissions", [])
    
    if "trade" not in scopes and "trade" not in permissions:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Trading permissions required"
        )
    
    return user
