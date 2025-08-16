"""
FastAPI backend for antrikshGPT webapp.
Modern space-themed web application with real-time chat and space data visualization.
"""
import os
import sys
import asyncio
import json
import time
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from contextlib import asynccontextmanager

# Add project root to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Depends, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel

from shared.langchain_agent import spacegpt_agent
from shared.space_apis import space_api
from webapp.backend.auth import (
    User,
    create_access_token,
    get_current_user,
    verify_password,
)
from webapp.backend.database import get_user, fake_users_db
from config.logging_config import configure_logging, get_logger

configure_logging()
logger = get_logger(__name__)


class SmartCacheManager:
    """Advanced caching system with rate limiting and fallback data for production deployment."""
    
    def __init__(self):
        self._cache = {}
        self._last_api_calls = {}
        self._api_call_counts = {}
        self._fallback_data = {
            "iss": {
                "iss_position": {"latitude": "-21.45", "longitude": "128.86"},
                "timestamp": int(time.time()),
                "message": "success"
            },
            "spacex-next": {
                "name": "Falcon 9 Block 5 | Starlink Group 17-5",
                "date_utc": (datetime.now() + timedelta(days=3)).isoformat() + "Z",
                "rocket": {"name": "Falcon 9"},
                "launchpad": {"name": "Kennedy Space Center", "full_name": "Launch Complex 39A"},
                "details": "Starlink mission to provide global broadband coverage",
                "status": "Go",
                "upcoming": True
            }
        }
        
        # Cache TTL settings (in seconds)
        self._cache_ttl = {
            "iss": 60,              # ISS updates every minute
            "spacex-next": 3600,    # Launch data every hour
            "spacex-launches": 7200, # Launch history every 2 hours
            "people-in-space": 1800, # People in space every 30 minutes
            "space-news": 1800,     # News every 30 minutes
            "mars-weather": 3600,   # Mars weather every hour
        }
        
        # Rate limiting settings
        self._rate_limits = {
            "iss": {"calls": 60, "window": 3600},           # 60 calls per hour
            "spacex-next": {"calls": 10, "window": 3600},   # 10 calls per hour
            "spacex-launches": {"calls": 5, "window": 3600}, # 5 calls per hour
            "people-in-space": {"calls": 20, "window": 3600}, # 20 calls per hour
            "space-news": {"calls": 10, "window": 3600},    # 10 calls per hour
            "mars-weather": {"calls": 10, "window": 3600},  # 10 calls per hour
        }
    
    def _is_cache_valid(self, key: str) -> bool:
        """Check if cached data is still valid."""
        if key not in self._cache:
            return False
        
        data, timestamp = self._cache[key]
        ttl = self._cache_ttl.get(key, 300)  # Default 5 minutes
        return (time.time() - timestamp) < ttl
    
    def _is_rate_limited(self, endpoint: str) -> bool:
        """Check if we're being rate limited for an endpoint."""
        if endpoint not in self._rate_limits:
            return False
        
        current_time = time.time()
        rate_config = self._rate_limits[endpoint]
        window_start = current_time - rate_config["window"]
        
        # Clean old entries
        if endpoint in self._api_call_counts:
            self._api_call_counts[endpoint] = [
                call_time for call_time in self._api_call_counts[endpoint]
                if call_time > window_start
            ]
        else:
            self._api_call_counts[endpoint] = []
        
        # Check if we've exceeded the limit
        return len(self._api_call_counts[endpoint]) >= rate_config["calls"]
    
    def _record_api_call(self, endpoint: str):
        """Record an API call for rate limiting."""
        current_time = time.time()
        if endpoint not in self._api_call_counts:
            self._api_call_counts[endpoint] = []
        self._api_call_counts[endpoint].append(current_time)
        self._last_api_calls[endpoint] = current_time
    
    async def get_data(self, endpoint: str, fetch_func, **kwargs):
        """Smart data fetching with caching, rate limiting, and fallbacks."""
        # Check cache first
        if self._is_cache_valid(endpoint):
            logger.info("Serving from cache", endpoint=endpoint)
            return self._cache[endpoint][0]
        
        # Check rate limiting
        if self._is_rate_limited(endpoint):
            logger.warning("Rate limited", endpoint=endpoint)
            # Return cached data even if expired, or fallback
            if endpoint in self._cache:
                return self._cache[endpoint][0]
            elif endpoint in self._fallback_data:
                return self._fallback_data[endpoint]
            else:
                return {"error": "Service temporarily unavailable", "cached": True}
        
        # Fetch fresh data
        try:
            logger.info("Fetching fresh data", endpoint=endpoint)
            self._record_api_call(endpoint)
            data = await fetch_func(**kwargs)
            
            # Cache successful responses
            if not data.get('error'):
                self._cache[endpoint] = (data, time.time())
                logger.info("Cached fresh data", endpoint=endpoint)
            else:
                logger.warning("API returned an error, using fallback/stale cache", endpoint=endpoint, error=data.get('error'))
                if endpoint in self._cache:
                    return self._cache[endpoint][0]
                elif endpoint in self._fallback_data:
                    return self._fallback_data[endpoint]
            
            return data
            
        except Exception as e:
            logger.error("Error fetching data", endpoint=endpoint, error=str(e))
            # Return cached data if available, otherwise fallback
            if endpoint in self._cache:
                logger.info("Serving stale cache due to error", endpoint=endpoint)
                return self._cache[endpoint][0]
            elif endpoint in self._fallback_data:
                logger.info("Serving fallback data", endpoint=endpoint)
                return self._fallback_data[endpoint]
            else:
                return {"error": f"Failed to fetch {endpoint}", "cached": True}
    
    def get_cache_stats(self) -> Dict:
        """Get caching and rate limiting statistics."""
        current_time = time.time()
        stats = {
            "cached_endpoints": list(self._cache.keys()),
            "cache_ages": {},
            "rate_limit_status": {},
            "total_api_calls": sum(len(calls) for calls in self._api_call_counts.values())
        }
        
        for endpoint, (data, timestamp) in self._cache.items():
            stats["cache_ages"][endpoint] = int(current_time - timestamp)
        
        for endpoint, calls in self._api_call_counts.items():
            if endpoint in self._rate_limits:
                rate_config = self._rate_limits[endpoint]
                window_start = current_time - rate_config["window"]
                recent_calls = len([c for c in calls if c > window_start])
                stats["rate_limit_status"][endpoint] = {
                    "calls_in_window": recent_calls,
                    "limit": rate_config["calls"],
                    "window_hours": rate_config["window"] / 3600,
                    "is_limited": recent_calls >= rate_config["calls"]
                }
            else:
                # No explicit rate limit configured for this endpoint
                stats["rate_limit_status"][endpoint] = {
                    "calls_in_window": len(calls),
                    "limit": None,
                    "window_hours": None,
                    "is_limited": False
                }
        
        return stats


# Global cache manager
cache_manager = SmartCacheManager()


class ChatMessage(BaseModel):
    """Chat message model."""
    message: str
    chat_history: Optional[List[Dict[str, str]]] = None


class WebSocketManager:
    """Manages WebSocket connections for real-time updates."""
    
    def __init__(self):
        self.active_connections: List[WebSocket] = []
    
    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
    
    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
    
    async def send_personal_message(self, message: str, websocket: WebSocket):
        try:
            await websocket.send_text(message)
        except:
            self.disconnect(websocket)
    
    async def broadcast(self, message: str):
        disconnected = []
        for connection in self.active_connections:
            try:
                await connection.send_text(message)
            except:
                disconnected.append(connection)
        
        # Remove disconnected clients
        for connection in disconnected:
            self.disconnect(connection)


# WebSocket manager instance
manager = WebSocketManager()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan context manager for serverless deployment."""
    # Startup
    logger.info("Starting antrikshGPT webapp...")

    logger.info("Space APIs initialized")
    logger.info("SpaceGPT agent ready")
    
    # Note: Background tasks removed for serverless compatibility
    # Vercel functions are stateless and don't support long-running background tasks
    
    yield
    
    # Shutdown - graceful cleanup for serverless
    logger.info("Shutting down antrikshGPT webapp")


# Create FastAPI app
app = FastAPI(
    title="antrikshGPT",
    description="AI-powered space exploration assistant with real-time space data",
    version="1.0.0",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def catch_exceptions_middleware(request: Request, call_next):
    """
    Middleware to catch unhandled exceptions and return a generic 500 error.
    This prevents exposing sensitive information in stack traces.
    """
    try:
        return await call_next(request)
    except Exception as e:
        logger.error(f"Unhandled exception: {e}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"detail": "Internal Server Error"},
        )


# Mount static files
app.mount("/static", StaticFiles(directory="webapp/frontend"), name="static")


@app.get("/", response_class=HTMLResponse)
async def root():
    """Serve the main webapp."""
    try:
        with open("webapp/frontend/index.html", "r") as f:
            return HTMLResponse(content=f.read())
    except FileNotFoundError:
        return HTMLResponse(content="<h1>antrikshGPT</h1><p>Frontend files not found</p>")


@app.get("/credits", response_class=HTMLResponse)
async def credits():
    """Serve the credits page."""
    try:
        with open("webapp/frontend/credits.html", "r") as f:
            return HTMLResponse(content=f.read())
    except FileNotFoundError:
        return HTMLResponse(content="<h1>antrikshGPT</h1><p>Credits file not found</p>")


@app.get("/favicon.ico")
async def favicon():
    """Serve favicon."""
    return FileResponse("webapp/frontend/favicon.ico", media_type="image/x-icon")


@app.post("/api/chat")
async def chat_endpoint(chat_data: ChatMessage):
    """Chat endpoint for the SpaceGPT agent."""
    try:
        response = await spacegpt_agent.chat(
            message=chat_data.message,
            chat_history=chat_data.chat_history
        )
        return {
            "response": response,
            "timestamp": datetime.now().isoformat(),
            "status": "success"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Chat error: {str(e)}")


@app.get("/api/space-data/{data_type}")
async def get_space_data(data_type: str):
    """Get specific space data with smart caching and rate limiting."""
    try:
        # Map data types to API functions
        api_mapping = {
            "iss": space_api.get_iss_location,
            "people-in-space": space_api.get_people_in_space,
            "spacex-next": space_api.get_spacex_next_launch,
            "spacex-launches": lambda: space_api.get_spacex_launches(limit=5),
            "space-news": lambda: space_api.get_space_news(limit=5),
            "mars-weather": space_api.get_mars_weather,
            # Default to last 7 days if no dates are given (handled in the client)
            "space-weather": lambda: space_api.get_space_weather(),
            "near-earth-objects": lambda: space_api.get_near_earth_objects(),
        }
        
        if data_type.startswith("planet-"):
            planet_id = data_type.split("-")[1]
            api_func = lambda: space_api.get_solar_system_body(body_id=planet_id)
            data = await cache_manager.get_data(data_type, api_func)
        elif data_type not in api_mapping:
            raise HTTPException(status_code=404, detail="Data type not found")
        else:
            data = await cache_manager.get_data(data_type, api_mapping[data_type])

        return {
            "data": data,
            "timestamp": datetime.now().isoformat(),
            "type": data_type,
            "cached": data.get("cached", False)
        }
    except Exception as e:
        # Return fallback response instead of error
        fallback_data = cache_manager._fallback_data.get(data_type, {
            "error": f"Service temporarily unavailable: {str(e)}", 
            "cached": True
        })
        return {
            "data": fallback_data,
            "timestamp": datetime.now().isoformat(),
            "type": data_type,
            "cached": True
        }


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time communication (limited in serverless)."""
    await manager.connect(websocket)
    try:
        # Send initial welcome message
        await manager.send_personal_message(json.dumps({
            "type": "welcome",
            "message": "🚀 Connected to antrikshGPT! Note: Real-time updates are limited in serverless mode.",
            "timestamp": datetime.now().isoformat()
        }), websocket)
        
        # Handle incoming messages (limited functionality in serverless)
        while True:
            data = await websocket.receive_text()
            try:
                message_data = json.loads(data)
                if message_data.get("type") == "chat":
                    # Process chat message
                    response = await spacegpt_agent.chat(message_data.get("message", ""))
                    await manager.send_personal_message(json.dumps({
                        "type": "chat_response",
                        "message": response,
                        "timestamp": datetime.now().isoformat()
                    }), websocket)
                elif message_data.get("type") == "ping":
                    # Respond to ping
                    await manager.send_personal_message(json.dumps({
                        "type": "pong",
                        "timestamp": datetime.now().isoformat()
                    }), websocket)
                else:
                    # Inform about limited functionality
                    await manager.send_personal_message(json.dumps({
                        "type": "info",
                        "message": "This feature has limited functionality in serverless mode. Please use the main chat interface.",
                        "timestamp": datetime.now().isoformat()
                    }), websocket)
            except json.JSONDecodeError:
                await manager.send_personal_message(json.dumps({
                    "type": "error",
                    "message": "Invalid JSON format",
                    "timestamp": datetime.now().isoformat()
                }), websocket)
    except WebSocketDisconnect:
        manager.disconnect(websocket)


@app.post("/api/login")
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends()):
    user = get_user(form_data.username)
    if not user or not verify_password(form_data.password, user["hashed_password"]):
        raise HTTPException(
            status_code=401,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = timedelta(minutes=30)
    access_token = create_access_token(
        data={"sub": user["username"]}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}


@app.get("/api/health")
async def health_check():
    """Health check endpoint with cache statistics."""
    cache_stats = cache_manager.get_cache_stats()
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "services": {
            "spacegpt_agent": "online",
            "space_apis": "online",
            "websocket": "online",
            "cache_manager": "online"
        },
        "cache_stats": cache_stats
    }


@app.get("/api/cache/stats")
async def get_cache_stats():
    """Get detailed cache and rate limiting statistics."""
    return {
        "timestamp": datetime.now().isoformat(),
        "cache_stats": cache_manager.get_cache_stats()
    }


@app.get("/api/space-search/{query}")
async def space_search(query: str, num_results: int = 5):
    """Web search for space-related queries as a fallback."""
    try:
        data = await cache_manager.get_data(
            f"web_search_{query}_{num_results}", 
            space_api.web_search_space,
            query=query,
            num_results=num_results
        )
        return {
            "data": data,
            "timestamp": datetime.now().isoformat(),
            "type": "space_search",
            "query": query,
            "cached": data.get("cached", False)
        }
    except Exception as e:
        return {
            "data": {"error": f"Search failed: {str(e)}", "query": query},
            "timestamp": datetime.now().isoformat(),
            "type": "space_search",
            "query": query,
            "cached": False
        }


@app.post("/api/cache/clear")
async def clear_cache(current_user: User = Depends(get_current_user)):
    """Clear all cached data (admin endpoint)."""
    cache_manager._cache.clear()
    cache_manager._api_call_counts.clear()
    return {
        "status": "Cache cleared successfully",
        "timestamp": datetime.now().isoformat()
    }


if __name__ == "__main__":
    import uvicorn
    logger.info("Starting antrikshGPT webapp on http://localhost:8000")
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )