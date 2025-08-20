"""
Space API clients for fetching data from various space-related services.
"""
import asyncio
import aiohttp
import json
import time
import logging
import os
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from config.settings import settings
from ddgs import DDGS

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class SpaceAPIClient:
    """Client for interacting with various space APIs."""
    
    def __init__(self):
        self.nasa_api_key = settings.nasa_api_key
        self.spacex_base_url = settings.spacex_api_base
        self.launch_library_base_url = "https://ll.thespacedevs.com/2.0.0"
        
        # Rate limiting for Launch Library API
        self.last_launch_library_call = 0
        self.launch_library_min_interval = 30  # Minimum seconds between calls
        
        # Cache for frequently requested data
        self._cache = {}
        self._cache_ttl = 300  # 5 minutes cache TTL
        
    async def web_search(self, query: str, max_results: int = 5) -> Dict[str, Any]:
        """Perform a web search using DuckDuckGo for space and astronomy topics."""
        cache_key = self._get_cache_key("web_search", query=query, max_results=max_results)
        cached_data = self._get_cached_data(cache_key)
        if cached_data:
            return cached_data

        try:
            logger.info(f"Performing web search for: {query}")
            
            # Ensure max_results is an integer
            max_results = int(max_results) if max_results else 5
            
            # Use DDGS context manager for clean resource handling
            with DDGS() as ddgs:
                results = list(ddgs.text(query, max_results=max_results))

            if not results:
                return {
                    "search_query": query,
                    "results": [],
                    "message": "No search results found.",
                    "related_topics": self._get_related_space_suggestions(query)
                }

            # Format results for clarity
            formatted_results = []
            for r in results:
                try:
                    formatted_results.append({
                        "title": r.get("title", "No Title"),
                        "url": r.get("href", "#"),
                        "snippet": r.get("body", "No snippet available.")
                    })
                except Exception as format_error:
                    logger.warning(f"Error formatting result: {format_error}")
                    continue

            response = {
                "search_query": query,
                "results": formatted_results,
                "summary": f"Found {len(formatted_results)} results for '{query}'"
            }
            
            self._set_cached_data(cache_key, response)
            return response

        except Exception as e:
            error_msg = f"Error during web search for '{query}': {str(e)}"
            logger.error(error_msg)
            return {"error": error_msg}
        
    async def _rate_limit_launch_library(self):
        """Ensure we don't exceed rate limits for Launch Library API."""
        current_time = time.time()
        time_since_last_call = current_time - self.last_launch_library_call
        
        if time_since_last_call < self.launch_library_min_interval:
            wait_time = self.launch_library_min_interval - time_since_last_call
            logger.info(f"Rate limiting: waiting {wait_time:.1f} seconds before next Launch Library API call")
            await asyncio.sleep(wait_time)
        
        self.last_launch_library_call = time.time()
    
    def _get_cache_key(self, method: str, **kwargs) -> str:
        """Generate cache key for method and parameters."""
        kwargs_str = str(sorted(kwargs.items()))
        return f"{method}:{hash(kwargs_str)}"
    
    def _get_cached_data(self, cache_key: str) -> Optional[Dict[str, Any]]:
        """Get cached data if it exists and is not expired."""
        if cache_key in self._cache:
            data, timestamp = self._cache[cache_key]
            if time.time() - timestamp < self._cache_ttl:
                logger.info(f"Returning cached data for {cache_key}")
                return data
            else:
                # Remove expired cache entry
                del self._cache[cache_key]
        return None
    
    def _set_cached_data(self, cache_key: str, data: Dict[str, Any]):
        """Cache data with current timestamp."""
        self._cache[cache_key] = (data, time.time())
        logger.info(f"Cached data for {cache_key}")
    
    async def get_iss_location(self) -> Dict[str, Any]:
        """Get current International Space Station location."""
        cache_key = self._get_cache_key("iss_location")
        cached_data = self._get_cached_data(cache_key)
        if cached_data:
            return cached_data
            
        url = "http://api.open-notify.org/iss-now.json"
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=30) as response:
                    if response.status == 200:
                        data = await response.json()
                        # Cache ISS location for shorter time since it changes frequently
                        self._cache[cache_key] = (data, time.time())
                        return data
                    else:
                        error_msg = f"Failed to fetch ISS location: {response.status}"
                        logger.error(error_msg)
                        return {"error": error_msg}
        except asyncio.TimeoutError:
            error_msg = "Timeout while fetching ISS location"
            logger.error(error_msg)
            return {"error": error_msg}
        except Exception as e:
            error_msg = f"Error fetching ISS location: {str(e)}"
            logger.error(error_msg)
            return {"error": error_msg}
    
    async def get_people_in_space(self) -> Dict[str, Any]:
        """Get list of people currently in space."""
        cache_key = self._get_cache_key("people_in_space")
        cached_data = self._get_cached_data(cache_key)
        if cached_data:
            return cached_data
            
        url = "http://api.open-notify.org/astros.json"
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=30) as response:
                    if response.status == 200:
                        data = await response.json()
                        self._set_cached_data(cache_key, data)
                        return data
                    else:
                        error_msg = f"Failed to fetch people in space: {response.status}"
                        logger.error(error_msg)
                        return {"error": error_msg}
        except asyncio.TimeoutError:
            error_msg = "Timeout while fetching people in space data"
            logger.error(error_msg)
            return {"error": error_msg}
        except Exception as e:
            error_msg = f"Error fetching people in space: {str(e)}"
            logger.error(error_msg)
            return {"error": error_msg}
    
    async def get_spacex_launches(self, limit: int = 10) -> Dict[str, Any]:
        """Get recent SpaceX launches using Launch Library 2 API."""
        await self._rate_limit_launch_library()
        
        cache_key = self._get_cache_key("spacex_launches", limit=limit)
        cached_data = self._get_cached_data(cache_key)
        if cached_data:
            return cached_data
            
        url = f"{self.launch_library_base_url}/launch/"
        params = {
            "search": "SpaceX",
            "limit": limit,
            "ordering": "-net",  # Sort by date descending
            "format": "json"
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params, timeout=30) as response:
                    if response.status == 200:
                        data = await response.json()
                        launches = []
                        for launch in data.get("results", []):
                            launches.append({
                                "name": launch.get("name", "Unknown Mission"),
                                "date_utc": launch.get("net"),
                                "rocket": {
                                    "name": launch.get("rocket", {}).get("configuration", {}).get("full_name", "Unknown Rocket")
                                },
                                "launchpad": {
                                    "name": launch.get("pad", {}).get("location", {}).get("name", "Unknown Location"),
                                    "full_name": launch.get("pad", {}).get("name", "Unknown Pad")
                                },
                                "details": launch.get("mission", {}).get("description", "No details available"),
                                "status": launch.get("status", {}).get("name", "Unknown"),
                                "success": launch.get("status", {}).get("name") == "Success",
                                "upcoming": launch.get("status", {}).get("name") in ["Go", "TBD"],
                                "launch_library_data": launch
                            })
                        
                        result = {"launches": launches}
                        self._set_cached_data(cache_key, result)
                        return result
                    elif response.status == 429:  # Rate limited
                        error_msg = "API rate limit exceeded. Please try again in a few minutes."
                        logger.warning(error_msg)
                        return {"error": error_msg, "retry_after": 60}
                    else:
                        error_msg = f"Failed to fetch SpaceX launches: {response.status}"
                        logger.error(error_msg)
                        return {"error": error_msg}
        except asyncio.TimeoutError:
            error_msg = "Timeout while fetching SpaceX launches"
            logger.error(error_msg)
            return {"error": error_msg}
        except Exception as e:
            error_msg = f"Error fetching SpaceX launches: {str(e)}"
            logger.error(error_msg)
            return {"error": error_msg}
    
    async def get_spacex_next_launch(self) -> Dict[str, Any]:
        """Get next SpaceX launch using Launch Library 2 API."""
        await self._rate_limit_launch_library()
        
        cache_key = self._get_cache_key("spacex_next_launch")
        cached_data = self._get_cached_data(cache_key)
        if cached_data:
            return cached_data
            
        url = f"{self.launch_library_base_url}/launch/upcoming/"
        params = {
            "search": "SpaceX",
            "limit": 1,
            "format": "json"
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params, timeout=30) as response:
                    if response.status == 200:
                        data = await response.json()
                        if data.get("results"):
                            launch = data["results"][0]
                            # Transform to match expected format for better compatibility
                            result = {
                                "name": launch.get("name", "Unknown Mission"),
                                "date_utc": launch.get("net"),
                                "date_unix": None,  # Convert if needed
                                "rocket": {
                                    "name": launch.get("rocket", {}).get("configuration", {}).get("full_name", "Unknown Rocket")
                                },
                                "launchpad": {
                                    "name": launch.get("pad", {}).get("location", {}).get("name", "Unknown Location"),
                                    "full_name": launch.get("pad", {}).get("name", "Unknown Pad")
                                },
                                "details": launch.get("mission", {}).get("description", "No details available"),
                                "status": launch.get("status", {}).get("name", "Unknown"),
                                "success": None,
                                "upcoming": True,
                                "launch_library_data": launch  # Include original data for reference
                            }
                            
                            self._set_cached_data(cache_key, result)
                            return result
                        else:
                            error_msg = "No upcoming SpaceX launches found"
                            logger.warning(error_msg)
                            return {"error": error_msg}
                    elif response.status == 429:  # Rate limited
                        error_msg = "API rate limit exceeded. Please try again in a few minutes."
                        logger.warning(error_msg)
                        return {"error": error_msg, "retry_after": 60}
                    else:
                        error_msg = f"Failed to fetch next SpaceX launch: {response.status}"
                        logger.error(error_msg)
                        return {"error": error_msg}
        except asyncio.TimeoutError:
            error_msg = "Timeout while fetching next SpaceX launch"
            logger.error(error_msg)
            return {"error": error_msg}
        except Exception as e:
            error_msg = f"Error fetching next SpaceX launch: {str(e)}"
            logger.error(error_msg)
            return {"error": error_msg}
    
    async def get_mars_weather(self) -> Dict[str, Any]:
        """Get Mars weather data (from NASA InSight)."""
        cache_key = self._get_cache_key("mars_weather")
        cached_data = self._get_cached_data(cache_key)
        if cached_data:
            return cached_data
            
        url = "https://api.nasa.gov/insight_weather/"
        params = {
            "api_key": self.nasa_api_key,
            "feedtype": "json",
            "ver": "1.0"
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params, timeout=30) as response:
                    if response.status == 200:
                        data = await response.json()
                        self._set_cached_data(cache_key, data)
                        return data
                    else:
                        error_msg = f"Failed to fetch Mars weather: {response.status}"
                        logger.error(error_msg)
                        return {"error": error_msg}
        except asyncio.TimeoutError:
            error_msg = "Timeout while fetching Mars weather"
            logger.error(error_msg)
            return {"error": error_msg}
        except Exception as e:
            error_msg = f"Error fetching Mars weather: {str(e)}"
            logger.error(error_msg)
            return {"error": error_msg}
    
    async def get_near_earth_objects(self, start_date: Optional[str] = None, end_date: Optional[str] = None) -> Dict[str, Any]:
        """Get Near Earth Objects from NASA."""
        cache_key = self._get_cache_key("near_earth_objects", start_date=start_date, end_date=end_date)
        cached_data = self._get_cached_data(cache_key)
        if cached_data:
            return cached_data
            
        url = "https://api.nasa.gov/neo/rest/v1/feed"
        
        # Default to today if no dates provided
        if not start_date:
            start_date = datetime.now().strftime("%Y-%m-%d")
        if not end_date:
            end_date = (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d")
        
        params = {
            "start_date": start_date,
            "end_date": end_date,
            "api_key": self.nasa_api_key
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params, timeout=30) as response:
                    if response.status == 200:
                        data = await response.json()
                        self._set_cached_data(cache_key, data)
                        return data
                    else:
                        error_msg = f"Failed to fetch NEOs: {response.status}"
                        logger.error(error_msg)
                        return {"error": error_msg}
        except asyncio.TimeoutError:
            error_msg = "Timeout while fetching NEOs"
            logger.error(error_msg)
            return {"error": error_msg}
        except Exception as e:
            error_msg = f"Error fetching NEOs: {str(e)}"
            logger.error(error_msg)
            return {"error": error_msg}
    
    async def search_mars_photos(self, sol: int = 1000, camera: str = "fhaz") -> Dict[str, Any]:
        """Search Mars rover photos."""
        cache_key = self._get_cache_key("mars_photos", sol=sol, camera=camera)
        cached_data = self._get_cached_data(cache_key)
        if cached_data:
            return cached_data
            
        url = "https://api.nasa.gov/mars-photos/api/v1/rovers/curiosity/photos"
        params = {
            "sol": sol,
            "camera": camera,
            "api_key": self.nasa_api_key
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params, timeout=30) as response:
                    if response.status == 200:
                        data = await response.json()
                        self._set_cached_data(cache_key, data)
                        return data
                    else:
                        error_msg = f"Failed to fetch Mars photos: {response.status}"
                        logger.error(error_msg)
                        return {"error": error_msg}
        except asyncio.TimeoutError:
            error_msg = "Timeout while fetching Mars photos"
            logger.error(error_msg)
            return {"error": error_msg}
        except Exception as e:
            error_msg = f"Error fetching Mars photos: {str(e)}"
            logger.error(error_msg)
            return {"error": error_msg}

    async def get_space_news(self, limit: int = 10) -> Dict[str, Any]:
        """Get recent spaceflight news articles."""
        cache_key = self._get_cache_key("space_news", limit=limit)
        cached_data = self._get_cached_data(cache_key)
        if cached_data:
            return cached_data
            
        url = "https://api.spaceflightnewsapi.net/v4/articles/"
        params = {
            "limit": limit,
            "mode": "detailed"
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params, timeout=30) as response:
                    if response.status == 200:
                        data = await response.json()
                        articles = []
                        for article in data.get("results", []):
                            articles.append({
                                "title": article.get("title"),
                                "summary": article.get("summary"),
                                "published_at": article.get("published_at"),
                                "url": article.get("url"),
                                "news_site": article.get("news_site")
                            })
                        result = {"articles": articles}
                        self._set_cached_data(cache_key, result)
                        return result
                    else:
                        error_msg = f"Failed to fetch space news: {response.status}"
                        logger.error(error_msg)
                        return {"error": error_msg}
        except asyncio.TimeoutError:
            error_msg = "Timeout while fetching space news"
            logger.error(error_msg)
            return {"error": error_msg}
        except Exception as e:
            error_msg = f"Error fetching space news: {str(e)}"
            logger.error(error_msg)
            return {"error": error_msg}

    async def get_solar_system_body(self, body_id: str) -> Dict[str, Any]:
        """Get information about a solar system body."""
        cache_key = self._get_cache_key("solar_system_body", body_id=body_id)
        cached_data = self._get_cached_data(cache_key)
        if cached_data:
            return cached_data
            
        url = f"https://api.le-systeme-solaire.net/rest/bodies/{body_id}"
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=30) as response:
                    if response.status == 200:
                        data = await response.json()
                        self._set_cached_data(cache_key, data)
                        return data
                    else:
                        error_msg = f"Failed to fetch solar system body info: {response.status}"
                        logger.error(error_msg)
                        return {"error": error_msg}
        except asyncio.TimeoutError:
            error_msg = "Timeout while fetching solar system body info"
            logger.error(error_msg)
            return {"error": error_msg}
        except Exception as e:
            error_msg = f"Error fetching solar system body info: {str(e)}"
            logger.error(error_msg)
            return {"error": error_msg}

    async def get_space_weather(self, start_date: Optional[str] = None, end_date: Optional[str] = None) -> Dict[str, Any]:
        """Get recent news about space weather events."""
        cache_key = self._get_cache_key("space_weather", start_date=start_date, end_date=end_date)
        cached_data = self._get_cached_data(cache_key)
        if cached_data:
            return cached_data

        url = "https://api.spaceflightnewsapi.net/v4/articles/"
        
        params = {
            "search": "solar storm OR CME OR aurora OR flare",
            "limit": 5
        }

        if not start_date:
            start_date = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
        
        params["published_at_gte"] = start_date

        if end_date:
            params["published_at_lte"] = end_date
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params, timeout=30) as response:
                    if response.status == 200:
                        data = await response.json()
                        result = {"space_weather_news": data.get("results", [])}
                        self._set_cached_data(cache_key, result)
                        return result
                    else:
                        error_msg = f"Failed to fetch space weather news: {response.status}"
                        logger.error(error_msg)
                        return {"error": error_msg}
        except asyncio.TimeoutError:
            error_msg = "Timeout while fetching space weather news"
            logger.error(error_msg)
            return {"error": error_msg}
        except Exception as e:
            error_msg = f"Error fetching space weather news: {str(e)}"
            logger.error(error_msg)
            return {"error": error_msg}

    async def get_exoplanet_info(self, planet_name: str) -> Dict[str, Any]:
        """Get information about an exoplanet using web search for specific details."""
        cache_key = self._get_cache_key("exoplanet_info", planet_name=planet_name)
        cached_data = self._get_cached_data(cache_key)
        if cached_data:
            return cached_data
            
        try:
            # First, try to get specific information about the requested exoplanet
            logger.info(f"Searching for specific exoplanet information: {planet_name}")
            
            # Use web search to get specific information about the exoplanet
            with DDGS() as ddgs:
                # Search for specific exoplanet information
                specific_results = list(ddgs.text(f"{planet_name} exoplanet discovery characteristics", max_results=3))
                
                # Also search for recent news about this specific exoplanet
                news_results = list(ddgs.text(f"{planet_name} exoplanet news recent discoveries", max_results=2))
                
                # Combine results
                all_results = specific_results + news_results
                
                if all_results:
                    # Format the results
                    formatted_results = []
                    for r in all_results:
                        formatted_results.append({
                            "title": r.get("title", "No Title"),
                            "url": r.get("href", "#"),
                            "snippet": r.get("body", "No snippet available.")
                        })
                    
                    result = {
                        "exoplanet_name": planet_name,
                        "search_results": formatted_results,
                        "summary": f"Found {len(formatted_results)} results for {planet_name}",
                        "note": f"Information about exoplanet {planet_name} from web search"
                    }
                    
                    self._set_cached_data(cache_key, result)
                    return result
                else:
                    # Fallback to general exoplanet news if specific info not found
                    logger.info(f"No specific info found for {planet_name}, falling back to general exoplanet news")
                    
                    # Use spaceflight news API for general exoplanet news
                    url = "https://api.spaceflightnewsapi.net/v4/articles/"
                    params = {
                        "search": "exoplanet",
                        "limit": 3
                    }
                    
                    async with aiohttp.ClientSession() as session:
                        async with session.get(url, params=params, timeout=30) as response:
                            if response.status == 200:
                                data = await response.json()
                                articles = data.get("results", [])
                                
                                if articles:
                                    result = {
                                        "exoplanet_name": planet_name,
                                        "fallback_news": articles,
                                        "note": f"Specific information about {planet_name} not found. Showing recent exoplanet discoveries instead."
                                    }
                                    self._set_cached_data(cache_key, result)
                                    return result
                                else:
                                    return {"error": f"No information found for exoplanet {planet_name}"}
                            else:
                                return {"error": f"Failed to fetch exoplanet information: {response.status}"}
                                
        except Exception as e:
            error_msg = f"Error fetching exoplanet info for {planet_name}: {str(e)}"
            logger.error(error_msg)
            return {"error": error_msg}

    async def get_nasa_apod(self, date: Optional[str] = None, count: Optional[int] = None) -> Dict[str, Any]:
        """Get NASA's Astronomy Picture of the Day."""
        cache_key = self._get_cache_key("nasa_apod", date=date, count=count)
        cached_data = self._get_cached_data(cache_key)
        if cached_data:
            return cached_data
            
        url = "https://api.nasa.gov/planetary/apod"
        params = {"api_key": self.nasa_api_key}
        
        if date:
            params["date"] = date
        elif count:
            params["count"] = min(count, 10)  # Limit to 10 images max
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params, timeout=30) as response:
                    if response.status == 200:
                        data = await response.json()
                        self._set_cached_data(cache_key, data)
                        return data
                    else:
                        error_msg = f"Failed to fetch NASA APOD: {response.status}"
                        logger.error(error_msg)
                        return {"error": error_msg}
        except asyncio.TimeoutError:
            error_msg = "Timeout while fetching NASA APOD"
            logger.error(error_msg)
            return {"error": error_msg}
        except Exception as e:
            error_msg = f"Error fetching NASA APOD: {str(e)}"
            logger.error(error_msg)
            return {"error": error_msg}

    async def track_satellite(self, satellite_id: int, observer_lat: float = 0, observer_lng: float = 0, observer_alt: float = 0, seconds: int = 300) -> Dict[str, Any]:
        """Track satellite using N2YO API with observer position."""
        cache_key = self._get_cache_key("satellite_track", satellite_id=satellite_id, observer_lat=observer_lat, observer_lng=observer_lng, seconds=seconds)
        cached_data = self._get_cached_data(cache_key)
        if cached_data:
            return cached_data
            
        # N2YO API endpoint - you would need to get an API key from n2yo.com
        url = "https://api.n2yo.com/rest/v1/satellite/positions/{}/{}/{}/{}/{}".format(satellite_id, observer_lat, observer_lng, observer_alt, seconds)
        params = {
            "apiKey": settings.n2yo_api_key  # Use settings instead of os.getenv
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params, timeout=30) as response:
                    if response.status == 200:
                        data = await response.json()
                        self._set_cached_data(cache_key, data)
                        return data
                    else:
                        error_msg = f"Failed to track satellite: {response.status}"
                        logger.error(error_msg)
                        return {"error": error_msg}
        except Exception as e:
            error_msg = f"Error tracking satellite: {str(e)}"
            logger.error(error_msg)
            return {"error": error_msg}

    async def get_satellites_above(self, observer_lat: float, observer_lng: float, observer_alt: float = 0, elevation: float = 10) -> Dict[str, Any]:
        """Get satellites currently visible above a location.
        
        Args:
            observer_lat: Observer latitude in degrees
            observer_lng: Observer longitude in degrees  
            observer_alt: Observer altitude in meters (default: 0)
            elevation: Minimum elevation angle in degrees (default: 10, minimum to avoid SQL errors)
        """
        cache_key = self._get_cache_key("satellites_above", observer_lat=observer_lat, observer_lng=observer_lng, elevation=elevation)
        cached_data = self._get_cached_data(cache_key)
        if cached_data:
            return cached_data
            
        url = f"https://api.n2yo.com/rest/v1/satellite/above/{observer_lat}/{observer_lng}/{observer_alt}/{elevation}/0"
        params = {
            "apiKey": settings.n2yo_api_key
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params, timeout=30) as response:
                    if response.status == 200:
                        data = await response.json()
                        self._set_cached_data(cache_key, data)
                        return data
                    else:
                        error_msg = f"Failed to get satellites above: {response.status}"
                        logger.error(error_msg)
                        return {"error": error_msg}
        except Exception as e:
            error_msg = f"Error getting satellites above: {str(e)}"
            logger.error(error_msg)
            return {"error": error_msg}

    async def get_noaa_space_weather_alerts(self) -> Dict[str, Any]:
        """Get current space weather alerts from NOAA."""
        cache_key = self._get_cache_key("noaa_space_weather")
        cached_data = self._get_cached_data(cache_key)
        if cached_data:
            return cached_data
            
        url = "https://services.swpc.noaa.gov/products/alerts.json"
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=30) as response:
                    if response.status == 200:
                        data = await response.json()
                        
                        # Process and format the alerts
                        formatted_alerts = []
                        for alert in data:
                            formatted_alerts.append({
                                "alert_id": alert.get("alert_id"),
                                "product_id": alert.get("product_id"),
                                "message": alert.get("message", "").strip(),
                                "issue_datetime": alert.get("issue_datetime"),
                                "serial_number": alert.get("serial_number")
                            })
                        
                        result = {
                            "alerts": formatted_alerts,
                            "count": len(formatted_alerts),
                            "timestamp": datetime.now().isoformat()
                        }
                        
                        self._set_cached_data(cache_key, result)
                        return result
                    else:
                        error_msg = f"Failed to fetch NOAA space weather alerts: {response.status}"
                        logger.error(error_msg)
                        return {"error": error_msg}
        except Exception as e:
            error_msg = f"Error fetching NOAA space weather alerts: {str(e)}"
            logger.error(error_msg)
            return {"error": error_msg}

    async def get_noaa_solar_wind_data(self) -> Dict[str, Any]:
        """Get current solar wind data from NOAA."""
        cache_key = self._get_cache_key("noaa_solar_wind")
        cached_data = self._get_cached_data(cache_key)
        if cached_data:
            return cached_data
            
        url = "https://services.swpc.noaa.gov/products/solar-wind/mag-1-day.json"
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=30) as response:
                    if response.status == 200:
                        data = await response.json()
                        
                        # Get the most recent data point
                        if len(data) > 1:  # First row is headers
                            latest = data[-1]  # Most recent entry
                            result = {
                                "timestamp": latest[0] if len(latest) > 0 else "unknown",
                                "bt_gsm": latest[1] if len(latest) > 1 else None,
                                "bz_gsm": latest[2] if len(latest) > 2 else None,
                                "density": latest[3] if len(latest) > 3 else None,
                                "speed": latest[4] if len(latest) > 4 else None,
                                "temperature": latest[5] if len(latest) > 5 else None,
                                "note": "Solar wind magnetic field and plasma data from ACE spacecraft"
                            }
                        else:
                            result = {"error": "No solar wind data available"}
                        
                        self._set_cached_data(cache_key, result)
                        return result
                    else:
                        error_msg = f"Failed to fetch solar wind data: {response.status}"
                        logger.error(error_msg)
                        return {"error": error_msg}
        except Exception as e:
            error_msg = f"Error fetching solar wind data: {str(e)}"
            logger.error(error_msg)
            return {"error": error_msg}

    async def get_nasa_earth_imagery(self, lat: float, lon: float, date: Optional[str] = None, dim: float = 0.15) -> Dict[str, Any]:
        """Get NASA Earth imagery for a specific location."""
        cache_key = self._get_cache_key("nasa_earth_imagery", lat=lat, lon=lon, date=date, dim=dim)
        cached_data = self._get_cached_data(cache_key)
        if cached_data:
            return cached_data
            
        url = "https://api.nasa.gov/planetary/earth/imagery"
        params = {
            "lon": lon,
            "lat": lat,
            "dim": dim,
            "api_key": self.nasa_api_key
        }
        
        if date:
            params["date"] = date
        
        try:
            # Use a shorter timeout for NASA Earth imagery API to avoid long waits
            timeout = aiohttp.ClientTimeout(total=30)  # 30 seconds timeout
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(url, params=params) as response:
                    if response.status == 200:
                        # NASA Earth imagery API returns JSON with image URL
                        try:
                            data = await response.json()
                            if isinstance(data, dict) and 'url' in data:
                                result = {
                                    "url": data['url'],  # Use 'url' key for consistency
                                    "latitude": lat,
                                    "longitude": lon,
                                    "dimension": dim,
                                    "date": date or "latest",
                                    "note": "NASA Landsat 8 Earth imagery"
                                }
                            else:
                                # Fallback to response URL if JSON parsing fails
                                result = {
                                    "url": str(response.url),
                                    "latitude": lat,
                                    "longitude": lon,
                                    "dimension": dim,
                                    "date": date or "latest",
                                    "note": "NASA Landsat 8 Earth imagery"
                                }
                        except Exception as json_error:
                            logger.warning(f"JSON parsing failed for NASA Earth imagery: {json_error}")
                            # If JSON parsing fails, use response URL
                            result = {
                                "url": str(response.url),
                                "latitude": lat,
                                "longitude": lon,
                                "dimension": dim,
                                "date": date or "latest",
                                "note": "NASA Landsat 8 Earth imagery"
                            }
                        
                        self._set_cached_data(cache_key, result)
                        return result
                    else:
                        error_msg = f"Failed to fetch NASA Earth imagery: HTTP {response.status}"
                        logger.error(error_msg)
                        return {"error": error_msg}
        except asyncio.TimeoutError:
            error_msg = "NASA Earth imagery API request timed out (30s). The service may be experiencing high load."
            logger.error(error_msg)
            # Provide a helpful fallback response with location info
            fallback_result = {
                "error": error_msg,
                "location_info": {
                    "latitude": lat,
                    "longitude": lon,
                    "dimension": dim,
                    "date": date or "latest",
                    "note": "NASA Landsat 8 Earth imagery (service temporarily unavailable)"
                },
                "suggestion": "Try again later or use a different date. The NASA Earth imagery service can be slow during peak hours."
            }
            return fallback_result
        except Exception as e:
            error_msg = f"Error fetching NASA Earth imagery: {str(e)}"
            logger.error(error_msg)
            # Provide a helpful fallback response
            fallback_result = {
                "error": error_msg,
                "location_info": {
                    "latitude": lat,
                    "longitude": lon,
                    "dimension": dim,
                    "date": date or "latest",
                    "note": "NASA Landsat 8 Earth imagery (service error)"
                },
                "suggestion": "The NASA Earth imagery service may be temporarily unavailable. Please try again later."
            }
            return fallback_result

    async def get_eclipse_data(self, eclipse_type: str = "solar") -> Dict[str, Any]:
        """Get upcoming eclipse data using web search (as there's no free dedicated eclipse API)."""
        cache_key = self._get_cache_key("eclipse_data", eclipse_type=eclipse_type)
        cached_data = self._get_cached_data(cache_key)
        if cached_data:
            return cached_data
            
        try:
            # Use web search to find eclipse information
            search_query = f"upcoming {eclipse_type} eclipse 2024 2025 dates locations"
            search_results = await self.web_search(search_query, max_results=3)
            
            result = {
                "eclipse_type": eclipse_type,
                "search_results": search_results,
                "note": f"Eclipse information for {eclipse_type} eclipses from web search"
            }
            
            self._set_cached_data(cache_key, result)
            return result
            
        except Exception as e:
            error_msg = f"Error fetching eclipse data: {str(e)}"
            logger.error(error_msg)
            return {"error": error_msg}

    async def get_starlink_satellites(self) -> Dict[str, Any]:
        """Get Starlink constellation status using web search."""
        cache_key = self._get_cache_key("starlink_status")
        cached_data = self._get_cached_data(cache_key)
        if cached_data:
            return cached_data
            
        try:
            # Use web search for Starlink information
            search_results = await self.web_search("Starlink satellites active constellation count", max_results=3)
            
            result = {
                "constellation": "Starlink",
                "search_results": search_results,
                "note": "Current Starlink satellite constellation information"
            }
            
            self._set_cached_data(cache_key, result)
            return result
            
        except Exception as e:
            error_msg = f"Error fetching Starlink data: {str(e)}"
            logger.error(error_msg)
            return {"error": error_msg}

    def _get_related_space_suggestions(self, query: str) -> List[str]:
        """Generate related space topic suggestions based on the query."""
        query_lower = query.lower()
        suggestions = []
        
        # Space agency suggestions
        if any(term in query_lower for term in ["nasa", "launch", "mission"]):
            suggestions.extend([
                "NASA Artemis program",
                "SpaceX Falcon 9 launches", 
                "International Space Station",
                "Mars exploration missions"
            ])
        
        # Planetary suggestions
        if any(term in query_lower for term in ["mars", "planet", "rover"]):
            suggestions.extend([
                "Mars Perseverance rover",
                "Mars Ingenuity helicopter",
                "Mars weather data",
                "Exoplanet discoveries"
            ])
        
        # Launch-related suggestions
        if any(term in query_lower for term in ["launch", "rocket", "spacex"]):
            suggestions.extend([
                "Next SpaceX launch",
                "Recent rocket launches",
                "Launch schedule",
                "Space missions timeline"
            ])
        
        # Astronomy suggestions
        if any(term in query_lower for term in ["space", "astronomy", "telescope"]):
            suggestions.extend([
                "Hubble Space Telescope images",
                "James Webb Space Telescope",
                "Near-Earth asteroids",
                "Solar system exploration"
            ])
        
        # Remove duplicates and limit
        unique_suggestions = list(dict.fromkeys(suggestions))
        return unique_suggestions[:6]


# Global instance
space_api = SpaceAPIClient()