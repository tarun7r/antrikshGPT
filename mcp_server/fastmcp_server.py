"""
FastMCP Server implementation for SpaceGPT.
Modern MCP server using FastMCP framework for space-related data tools.
"""
import os
import sys
from typing import Optional

# Add project root to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from fastmcp import FastMCP
from shared.space_apis import space_api

# Create FastMCP server instance
mcp = FastMCP("SpaceGPT MCP Server")

@mcp.tool()
async def get_iss_location() -> str:
    """
    Get the current location of the International Space Station.
    
    Returns:
        JSON string with ISS coordinates (latitude, longitude) and timestamp
    """
    try:
        result = await space_api.get_iss_location()
        return str(result)
    except Exception as e:
        return f"Error fetching ISS location: {str(e)}"

@mcp.tool()
async def get_people_in_space() -> str:
    """
    Get a list of people currently in space.
    
    Returns:
        JSON string with names and spacecraft of people currently in space
    """
    try:
        result = await space_api.get_people_in_space()
        return str(result)
    except Exception as e:
        return f"Error fetching people in space: {str(e)}"

@mcp.tool()
async def get_spacex_launches(limit: int = 10) -> str:
    """
    Get recent and upcoming SpaceX launch data from Launch Library 2 API.
    
    This provides current, accurate SpaceX launch information including recent missions
    and upcoming launches with real-time status updates.
    
    Args:
        limit: Maximum number of launches to retrieve (default: 10)
    
    Returns:
        JSON string with current SpaceX launch information including:
        - Mission names and descriptions
        - Launch dates (in UTC)
        - Rocket types (Falcon 9, Falcon Heavy, Starship)
        - Launch locations
        - Mission status (Success, Failure, Go, TBD)
        - Payload details
    """
    try:
        result = await space_api.get_spacex_launches(limit)
        
        # Add helpful context for the LLM
        if "launches" in result and result["launches"]:
            launch_count = len(result["launches"])
            status_counts = {}
            for launch in result["launches"]:
                status = launch.get("status", "Unknown")
                status_counts[status] = status_counts.get(status, 0) + 1
            
            summary = f"Found {launch_count} SpaceX launches. Status breakdown: {status_counts}"
            result["summary"] = summary
        
        return str(result)
    except Exception as e:
        return f"Error fetching SpaceX launches: {str(e)}"

@mcp.tool()
async def get_spacex_next_launch() -> str:
    """
    Get the next upcoming SpaceX launch from Launch Library 2 API.
    
    This provides the most current information about the next scheduled SpaceX mission,
    including real-time updates on launch status and any delays.
    
    Returns:
        JSON string with next SpaceX launch details including:
        - Mission name (e.g., "Falcon 9 Block 5 | Starlink Group 17-5")
        - Launch date and time (UTC)
        - Rocket type and configuration
        - Launch location and pad
        - Mission description and payload details
        - Current launch status (Go, TBD, Hold, etc.)
        - Launch window information
    """
    try:
        result = await space_api.get_spacex_next_launch()
        
        # Add helpful formatting for LLMs
        if "name" in result and "date_utc" in result:
            from datetime import datetime
            try:
                launch_date = datetime.fromisoformat(result["date_utc"].replace('Z', '+00:00'))
                now = datetime.now().astimezone()
                time_until = launch_date - now
                
                if time_until.total_seconds() > 0:
                    days = time_until.days
                    hours = time_until.seconds // 3600
                    result["time_until_launch"] = f"{days} days, {hours} hours"
                else:
                    result["time_until_launch"] = "Launch time has passed or is imminent"
            except:
                result["time_until_launch"] = "Could not calculate time until launch"
        
        return str(result)
    except Exception as e:
        return f"Error fetching next SpaceX launch: {str(e)}"

@mcp.tool()
async def get_upcoming_spacex_launches(limit: int = 5) -> str:
    """
    Get upcoming SpaceX launches from Launch Library 2 API.
    
    This provides information about future SpaceX missions that are scheduled
    but haven't launched yet. Perfect for answering questions about what's coming up.
    
    Args:
        limit: Maximum number of upcoming launches to retrieve (default: 5)
    
    Returns:
        JSON string with upcoming SpaceX launches including:
        - Mission names and timeline
        - Launch dates and countdown information
        - Mission descriptions and objectives
        - Launch status (Go, TBD, Hold)
        - Rocket types and configurations
        - Launch locations
    """
    try:
        # We'll create a new method for this in space_apis.py or use the existing one with filtering
        from shared.space_apis import space_api
        import aiohttp
        
        url = f"{space_api.launch_library_base_url}/launch/upcoming/"
        params = {
            "search": "SpaceX",
            "limit": limit,
            "format": "json"
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    launches = []
                    for launch in data.get("results", []):
                        launches.append({
                            "name": launch.get("name", "Unknown Mission"),
                            "date_utc": launch.get("net"),
                            "rocket": launch.get("rocket", {}).get("configuration", {}).get("full_name", "Unknown Rocket"),
                            "location": launch.get("pad", {}).get("location", {}).get("name", "Unknown Location"),
                            "pad": launch.get("pad", {}).get("name", "Unknown Pad"),
                            "mission_description": launch.get("mission", {}).get("description", "No details available"),
                            "status": launch.get("status", {}).get("name", "Unknown"),
                            "webcast_live": launch.get("webcast_live", False),
                            "probability": launch.get("probability")
                        })
                    
                    result = {
                        "upcoming_launches": launches,
                        "total_found": data.get("count", 0),
                        "summary": f"Found {len(launches)} upcoming SpaceX launches"
                    }
                    return str(result)
                else:
                    return f"Error: Failed to fetch upcoming launches (HTTP {response.status})"
    except Exception as e:
        return f"Error fetching upcoming SpaceX launches: {str(e)}"

@mcp.tool()
async def get_mars_weather() -> str:
    """
    Get Mars weather data from NASA InSight mission.
    
    Returns:
        JSON string with Mars weather information including temperature and atmospheric data
    """
    try:
        result = await space_api.get_mars_weather()
        return str(result)
    except Exception as e:
        return f"Error fetching Mars weather: {str(e)}"

@mcp.tool()
async def get_near_earth_objects(start_date: Optional[str] = None, end_date: Optional[str] = None) -> str:
    """
    Get Near Earth Objects (asteroids) data from NASA.
    
    Args:
        start_date: Start date in YYYY-MM-DD format (optional)
        end_date: End date in YYYY-MM-DD format (optional)
    
    Returns:
        JSON string with near Earth objects data including size, velocity, and approach dates
    """
    try:
        result = await space_api.get_near_earth_objects(start_date, end_date)
        return str(result)
    except Exception as e:
        return f"Error fetching near Earth objects: {str(e)}"

@mcp.tool()
async def search_mars_photos(sol: int = 1000, camera: str = "fhaz") -> str:
    """
    Search for Mars rover photos.
    
    Args:
        sol: Martian day (sol) to search for photos (default: 1000)
        camera: Camera to search photos from (default: "fhaz")
    
    Returns:
        Formatted string with Mars photos display including image URLs and metadata
    """
    try:
        result = await space_api.search_mars_photos(sol, camera)
        
        if isinstance(result, dict) and result.get('error'):
            return f"Error: {result['error']}"
        
        if isinstance(result, dict):
            photos = result.get('photos', [])
            
            if not photos:
                return f"No Mars photos found for Sol {sol} with camera {camera}"
            
            formatted_response = f"# Mars Photos from Curiosity Rover\n\n"
            formatted_response += f"**Sol (Martian Day):** {sol}\n"
            formatted_response += f"**Camera:** {camera.upper()}\n"
            formatted_response += f"**Photos Found:** {len(photos)}\n\n"
            
            # Show first 3 photos with images
            for i, photo in enumerate(photos[:3], 1):
                img_src = photo.get('img_src', '')
                earth_date = photo.get('earth_date', '')
                rover_name = photo.get('rover', {}).get('name', 'Curiosity')
                
                formatted_response += f"## Photo {i}\n\n"
                formatted_response += f"**Earth Date:** {earth_date}\n"
                formatted_response += f"**Rover:** {rover_name}\n\n"
                if img_src:
                    formatted_response += f"![Mars Photo]({img_src})\n\n"
                formatted_response += "---\n\n"
            
            if len(photos) > 3:
                formatted_response += f"*... and {len(photos) - 3} more photos*"
            
            return formatted_response
        
        return f"Unexpected response format: {type(result)}"
        
    except Exception as e:
        return f"Error searching Mars photos: {str(e)}"

@mcp.tool()
async def get_nasa_apod(date: str = None, count: int = None) -> str:
    """
    Get NASA's Astronomy Picture of the Day.
    
    Args:
        date: Specific date in YYYY-MM-DD format (optional)
        count: Number of random images to retrieve (optional, max 10)
    
    Returns:
        Formatted string with APOD data including title, explanation, and image display
    """
    try:
        result = await space_api.get_nasa_apod(date, count)
        
        if isinstance(result, dict) and result.get('error'):
            return f"Error: {result['error']}"
        
        # Handle single APOD response
        if isinstance(result, dict):
            title = result.get('title', 'NASA Astronomy Picture of the Day')
            explanation = result.get('explanation', '')
            image_url = result.get('url', '')
            date_str = result.get('date', '')
            copyright_info = result.get('copyright', '')
            
            formatted_response = f"# {title}\n\n"
            if date_str:
                formatted_response += f"**Date:** {date_str}\n\n"
            if copyright_info:
                formatted_response += f"**Copyright:** {copyright_info}\n\n"
            if image_url:
                formatted_response += f"![NASA APOD]({image_url})\n\n"
            formatted_response += f"**Explanation:**\n{explanation}"
            
            return formatted_response
        
        # Handle multiple APOD responses (when count is specified)
        elif isinstance(result, list):
            formatted_response = "# NASA Astronomy Pictures of the Day\n\n"
            for i, apod in enumerate(result, 1):
                title = apod.get('title', f'APOD #{i}')
                explanation = apod.get('explanation', '')
                image_url = apod.get('url', '')
                date_str = apod.get('date', '')
                copyright_info = apod.get('copyright', '')
                
                formatted_response += f"## {title}\n\n"
                if date_str:
                    formatted_response += f"**Date:** {date_str}\n\n"
                if copyright_info:
                    formatted_response += f"**Copyright:** {copyright_info}\n\n"
                if image_url:
                    formatted_response += f"![NASA APOD]({image_url})\n\n"
                formatted_response += f"**Explanation:**\n{explanation}\n\n---\n\n"
            
            return formatted_response
        
        else:
            return f"Unexpected response format: {type(result)}"
            
    except Exception as e:
        return f"Error fetching NASA APOD: {str(e)}"

@mcp.tool()
async def track_satellite(satellite_id: int, observer_lat: float = 0.0, observer_lng: float = 0.0, observer_alt: float = 0.0, seconds: int = 300) -> str:
    """
    Track a satellite's position over time from an observer's location.
    
    Args:
        satellite_id: NORAD ID of the satellite to track
        observer_lat: Observer's latitude in degrees (default: 0.0)
        observer_lng: Observer's longitude in degrees (default: 0.0)
        observer_alt: Observer's altitude in meters (default: 0.0)
        seconds: Duration to track in seconds (default: 300)
    
    Returns:
        JSON string with satellite tracking data including positions over time
    """
    try:
        result = await space_api.track_satellite(satellite_id, observer_lat, observer_lng, observer_alt, seconds)
        return str(result)
    except Exception as e:
        return f"Error tracking satellite: {str(e)}"

@mcp.tool()
async def get_satellites_above(observer_lat: float, observer_lng: float, observer_alt: float = 0.0, elevation: float = 0.0) -> str:
    """
    Get satellites currently visible above a location.
    
    Args:
        observer_lat: Observer's latitude in degrees
        observer_lng: Observer's longitude in degrees
        observer_alt: Observer's altitude in meters (default: 0.0)
        elevation: Minimum elevation angle in degrees (default: 0.0)
    
    Returns:
        JSON string with list of visible satellites including their positions and details
    """
    try:
        result = await space_api.get_satellites_above(observer_lat, observer_lng, observer_alt, elevation)
        return str(result)
    except Exception as e:
        return f"Error getting satellites above location: {str(e)}"

@mcp.tool()
async def get_noaa_space_weather_alerts() -> str:
    """
    Get current space weather alerts from NOAA Space Weather Prediction Center.
    
    Returns:
        JSON string with current space weather alerts, warnings, and watches
    """
    try:
        result = await space_api.get_noaa_space_weather_alerts()
        return str(result)
    except Exception as e:
        return f"Error fetching NOAA space weather alerts: {str(e)}"

@mcp.tool()
async def get_noaa_solar_wind_data() -> str:
    """
    Get current solar wind data from NOAA including magnetic field and plasma measurements.
    
    Returns:
        JSON string with solar wind speed, density, temperature, and magnetic field data
    """
    try:
        result = await space_api.get_noaa_solar_wind_data()
        return str(result)
    except Exception as e:
        return f"Error fetching solar wind data: {str(e)}"

@mcp.tool()
async def get_nasa_earth_imagery(lat: float, lon: float, date: str = None, dim: float = 0.15) -> str:
    """
    Get NASA Earth imagery for a specific location.
    
    Args:
        lat: Latitude in degrees
        lon: Longitude in degrees
        date: Date in YYYY-MM-DD format (optional, defaults to latest)
        dim: Image dimension as degrees of width/height (default: 0.15)
    
    Returns:
        Formatted string with Earth imagery display and metadata from NASA Landsat 8
    """
    try:
        result = await space_api.get_nasa_earth_imagery(lat, lon, date, dim)
        
        if isinstance(result, dict) and result.get('error'):
            return f"Error: {result['error']}"
        
        if isinstance(result, dict):
            if result.get('error'):
                error_msg = result.get('error', 'Unknown error')
                if 'timed out' in error_msg.lower():
                    return f"# Earth Imagery Request\n\n**Status:** ⏰ Timeout\n\n**Message:** {error_msg}\n\n*The NASA Earth imagery service is currently experiencing high load. Please try again in a few minutes.*"
                else:
                    return f"# Earth Imagery Request\n\n**Status:** ❌ Error\n\n**Message:** {error_msg}"
            
            # Handle both direct URL and JSON response formats
            image_url = result.get('url') or result.get('image_url') or str(result.get('url', ''))
            
            if image_url and image_url.startswith('http'):
                formatted_response = f"# Earth Imagery from NASA Landsat 8\n\n"
                formatted_response += f"**Location:** Latitude {lat}°, Longitude {lon}°\n\n"
                if date:
                    formatted_response += f"**Date:** {date}\n\n"
                formatted_response += f"**Image Dimensions:** {dim}° x {dim}°\n\n"
                formatted_response += f"![Earth Imagery]({image_url})\n\n"
                formatted_response += f"*Satellite imagery provided by NASA Landsat 8*"
                
                return formatted_response
            else:
                return f"Error: No valid image URL found in response"
        
        return f"Unexpected response format: {type(result)}"
        
    except Exception as e:
        return f"Error fetching NASA Earth imagery: {str(e)}"

@mcp.tool()
async def get_eclipse_data(eclipse_type: str = "solar") -> str:
    """
    Get upcoming eclipse information.
    
    Args:
        eclipse_type: Type of eclipse - "solar" or "lunar" (default: "solar")
    
    Returns:
        JSON string with upcoming eclipse dates, locations, and visibility information
    """
    try:
        result = await space_api.get_eclipse_data(eclipse_type)
        return str(result)
    except Exception as e:
        return f"Error fetching eclipse data: {str(e)}"

@mcp.tool()
async def get_starlink_satellites() -> str:
    """
    Get current Starlink satellite constellation status and information.
    
    Returns:
        JSON string with Starlink constellation data including active satellite count
    """
    try:
        result = await space_api.get_starlink_satellites()
        return str(result)
    except Exception as e:
        return f"Error fetching Starlink satellite data: {str(e)}"

if __name__ == "__main__":
    print("Starting FastMCP SpaceGPT Server...")
    mcp.run()