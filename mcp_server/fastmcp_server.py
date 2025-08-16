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
        JSON string with Mars rover photo data including URLs and metadata
    """
    try:
        result = await space_api.search_mars_photos(sol, camera)
        return str(result)
    except Exception as e:
        return f"Error searching Mars photos: {str(e)}"

if __name__ == "__main__":
    print("Starting FastMCP SpaceGPT Server...")
    mcp.run()