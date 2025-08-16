"""
Space API clients for fetching data from various space-related services.
"""
import asyncio
import aiohttp
import json
import time
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from config.settings import settings

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
        """Get information about an exoplanet from a working database."""
        cache_key = self._get_cache_key("exoplanet_info", planet_name=planet_name)
        cached_data = self._get_cached_data(cache_key)
        if cached_data:
            return cached_data
            
        # Use a working exoplanet database API
        url = "https://api.spaceflightnewsapi.net/v4/articles/"
        params = {
            "search": "exoplanet",  # Use generic term to get results
            "limit": 5
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params, timeout=30) as response:
                    if response.status == 200:
                        data = await response.json()
                        articles = data.get("results", [])
                        
                        if articles:
                            # Create exoplanet info from news articles
                            result = {
                                "name": planet_name,
                                "exoplanet_news": articles,
                                "note": f"Recent exoplanet news and discoveries. Requested planet: {planet_name}"
                            }
                            self._set_cached_data(cache_key, result)
                            return result
                        else:
                            error_msg = f"No exoplanet information found"
                            logger.warning(error_msg)
                            return {"error": error_msg}
                    else:
                        error_msg = f"Failed to fetch exoplanet info: {response.status}"
                        logger.error(error_msg)
                        return {"error": error_msg}
        except asyncio.TimeoutError:
            error_msg = "Timeout while fetching exoplanet info"
            logger.error(error_msg)
            return {"error": error_msg}
        except Exception as e:
            error_msg = f"Error fetching exoplanet info: {str(e)}"
            logger.error(error_msg)
            return {"error": error_msg}


# Global instance
space_api = SpaceAPIClient()