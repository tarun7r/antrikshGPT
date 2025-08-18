"""
LangChain/LangGraph agent with Gemini 2.5 Flash and MCP tools integration.
"""
import asyncio
import json
import subprocess
import tempfile
import os
import logging
from typing import Any, Dict, List, Optional, Union, Annotated, get_origin, get_args
from datetime import datetime, timedelta

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.tools import BaseTool
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage, ToolMessage
from pydantic import BaseModel, PrivateAttr, create_model

from config.settings import settings
from shared.space_apis import space_api

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class MCPTool(BaseTool):
    """Base class for MCP tools that can be used by LangChain."""
    
    _tool_func: Any = PrivateAttr()

    def __init__(self, name: str, description: str, tool_func, schema: Dict[str, Any]):
        # Create the args schema
        args_schema = create_model('Schema', **schema)
        
        # Pass name and description to parent class
        super().__init__(name=name, description=description, args_schema=args_schema)
        self._tool_func = tool_func
    
    def _run(self, **kwargs) -> str:
        """Synchronous run method."""
        try:
            return asyncio.run(self._arun(**kwargs))
        except Exception as e:
            logger.error(f"Error in synchronous tool execution for {self.name}: {str(e)}")
            return f"Error executing {self.name}: {str(e)}"
    
    async def _arun(self, **kwargs) -> str:
        """Asynchronous run method."""
        try:
            logger.info(f"Executing tool {self.name} with args: {kwargs}")
            result = await self._tool_func(**kwargs)
            logger.info(f"Tool {self.name} executed successfully")
            return json.dumps(result, indent=2, default=str)
        except Exception as e:
            logger.error(f"Error executing tool {self.name}: {str(e)}")
            return f"Error executing {self.name}: {str(e)}"


class SpaceGPTAgent:
    """LangGraph agent for SpaceGPT with Gemini 2.5 Flash and MCP tools."""
    
    def __init__(self):
        """Initialize the SpaceGPT agent with enhanced error handling and validation."""
        try:
            # Validate settings
            if not settings.google_api_key:
                raise ValueError("Google API key not configured")
            
            # Store configuration for recreating LLM client when needed
            self.llm_config = {
                "model": "gemini-2.0-flash",
                "google_api_key": os.getenv("GOOGLE_API_KEY"),
                "temperature": 0.7,
                "timeout": 30,
                "max_output_tokens": 2048,
                "max_retries": 2,
            }
            
            # Initialize the LLM client
            self.llm = None
            self.loop_id = None
            self._create_llm_client()
            
            # Initialize tools
            self.tools = self._create_tools()
            
            # Validate tool initialization
            if not self.tools:
                logger.warning("No tools were created during initialization")
            
            logger.info(f"SpaceGPT agent initialized successfully with {len(self.tools)} tools")
            
        except Exception as e:
            logger.error(f"Error initializing SpaceGPT agent: {str(e)}")
            # Create a minimal working setup
            self.llm = None
            self.tools = []
            raise RuntimeError(f"Failed to initialize SpaceGPT agent: {str(e)}")
        
        # Note: Graph initialization temporarily removed due to LangGraph compatibility issues
    
    async def cleanup(self):
        """Clean up resources, especially for serverless environments."""
        try:
            # Force cleanup of any gRPC connections
            if hasattr(self.llm, '_client') and self.llm._client:
                # Attempt to close gRPC client if accessible
                try:
                    if hasattr(self.llm._client, 'close'):
                        await self.llm._client.close()
                except Exception as e:
                    logger.warning(f"Could not close LLM client: {e}")
            logger.info("SpaceGPT agent cleanup completed")
        except Exception as e:
            logger.warning(f"Error during cleanup: {e}")
    
    def _create_llm_client(self):
        """Create or recreate the LLM client and bind it to the current event loop."""
        try:
            self.llm = ChatGoogleGenerativeAI(**self.llm_config)
            # Bind to the current event loop
            import asyncio
            self.loop_id = id(asyncio.get_event_loop())
            logger.info(f"LLM client created successfully and bound to event loop {self.loop_id}")
        except Exception as e:
            logger.error(f"Error creating LLM client: {e}")
            self.llm = None
            self.loop_id = None
            raise
    
    def _is_client_valid(self) -> bool:
        """Check if the LLM client is valid and bound to the active event loop."""
        if self.llm is None or self.loop_id is None:
            return False
        
        try:
            import asyncio
            current_loop = asyncio.get_event_loop()
            
            if current_loop.is_closed():
                logger.warning("Event loop is closed. Client is invalid.")
                return False
                
            if id(current_loop) != self.loop_id:
                logger.warning(f"Event loop changed (old: {self.loop_id}, new: {id(current_loop)}). Client is invalid.")
                return False
                
        except RuntimeError:
            logger.warning("No active event loop found. Client is invalid.")
            return False
            
        return True
    
    async def _ensure_valid_client(self):
        """Ensure we have a valid LLM client, recreating if necessary."""
        if not self._is_client_valid():
            logger.info("LLM client invalid, recreating...")
            try:
                # Clean up the old client first
                if self.llm:
                    await self.cleanup()
                
                # Create a new client
                self._create_llm_client()
                logger.info("LLM client recreated successfully")
            except Exception as e:
                logger.error(f"Failed to recreate LLM client: {e}")
                raise RuntimeError(f"Cannot establish valid LLM connection: {e}")
    
    def _create_tools(self) -> List[MCPTool]:
        """Create MCP tools for the agent."""
        tools = []
        
        # ISS Location tool
        tools.append(MCPTool(
            name="get_iss_location",
            description="Get current International Space Station location with latitude, longitude, and timestamp.",
            tool_func=space_api.get_iss_location,
            schema={}
        ))
        
        # People in Space tool
        tools.append(MCPTool(
            name="get_people_in_space",
            description="Get list of people currently in space, including their names and spacecraft.",
            tool_func=space_api.get_people_in_space,
            schema={}
        ))
        
        # SpaceX Launches tool
        tools.append(MCPTool(
            name="get_spacex_launches",
            description="Get recent and upcoming SpaceX launches with current, accurate data from Launch Library 2 API. Includes mission details, launch dates, rocket types, success status, and payload information.",
            tool_func=space_api.get_spacex_launches,
            schema={
                "limit": (int, 10)
            }
        ))
        
        # Next SpaceX Launch tool
        tools.append(MCPTool(
            name="get_spacex_next_launch",
            description="Get next scheduled SpaceX launch with current, accurate mission details from Launch Library 2 API. Includes real-time status updates, countdown information, and mission specifics.",
            tool_func=space_api.get_spacex_next_launch,
            schema={}
        ))
        
        # Mars Weather tool
        tools.append(MCPTool(
            name="get_mars_weather",
            description="Get current Mars weather data from NASA InSight lander.",
            tool_func=space_api.get_mars_weather,
            schema={}
        ))
        
        # Near Earth Objects tool
        tools.append(MCPTool(
            name="get_near_earth_objects",
            description="Get Near Earth Objects data from NASA for a date range.",
            tool_func=space_api.get_near_earth_objects,
            schema={
                "start_date": (Optional[str], None),
                "end_date": (Optional[str], None)
            }
        ))
        
        # Mars Photos tool
        tools.append(MCPTool(
            name="search_mars_photos",
            description="Search photos from Mars rovers. Specify sol (Martian day) and camera type.",
            tool_func=space_api.search_mars_photos,
            schema={
                "sol": (int, 1000),
                "camera": (str, "fhaz")
            }
        ))
        
        # Space News tool
        tools.append(MCPTool(
            name="get_space_news",
            description="Get recent spaceflight news articles. Specify limit for number of articles.",
            tool_func=space_api.get_space_news,
            schema={
                "limit": (int, 10)
            }
        ))
        
        # Solar System Body tool
        tools.append(MCPTool(
            name="get_solar_system_body",
            description="Get detailed information about a solar system body (e.g., 'mars', 'earth', 'lune' for moon). Provide the body ID or name in English or French.",
            tool_func=space_api.get_solar_system_body,
            schema={
                "body_id": (str, ...)
            }
        ))
        
        # Space Weather tool
        tools.append(MCPTool(
            name="get_space_weather",
            description="Get recent news about space weather events like solar storms, CMEs, and auroras. Optionally specify start_date and end_date in YYYY-MM-DD format. Defaults to the last 7 days if no dates are given.",
            tool_func=space_api.get_space_weather,
            schema={
                "start_date": (Optional[str], None),
                "end_date": (Optional[str], None)
            }
        ))
        
        # Exoplanet Info tool
        tools.append(MCPTool(
            name="get_exoplanet_info",
            description="Get information about an exoplanet by name from The Extrasolar Planets Encyclopaedia.",
            tool_func=space_api.get_exoplanet_info,
            schema={
                "planet_name": (str, ...)
            }
        ))
        
        # Web Search tool
        tools.append(MCPTool(
            name="web_search",
            description="Used to find information on space agencies that are NOT SpaceX. This includes NASA, ESA, ISRO, Roscosmos, and others. You MUST use this tool for queries like 'NASA's next mission' or 'ISRO's upcoming launches'.",
            tool_func=space_api.web_search,
            schema={
                "query": (str, ...),
                "max_results": (int, 5)
            }
        ))
        
        return tools
    
    async def _execute_tool_calls(self, tool_calls: List[Dict[str, Any]]) -> List[ToolMessage]:
        """Execute tool calls and return ToolMessage objects with enhanced error handling and retries."""
        tool_messages = []
        
        for tool_call in tool_calls:
            try:
                # Handle different tool call formats from Gemini with better validation
                if hasattr(tool_call, 'name'):
                    tool_name = tool_call.name
                    tool_args = tool_call.args if hasattr(tool_call, 'args') else {}
                    tool_id = tool_call.id if hasattr(tool_call, 'id') else ""
                elif isinstance(tool_call, dict):
                    tool_name = tool_call.get('name', '')
                    tool_args = tool_call.get('args', {})
                    tool_id = tool_call.get('id', '')
                else:
                    tool_name = str(tool_call)
                    tool_args = {}
                    tool_id = ""
                
                # Validate tool name
                if not tool_name or tool_name.strip() == "":
                    logger.warning("Empty tool name in tool call")
                    continue
                
                logger.info(f"Executing tool call: {tool_name} with args: {tool_args}")
                
                # Find and execute the tool with enhanced error handling and retries
                tool_executed = False
                for tool in self.tools:
                    if tool.name == tool_name:
                        try:
                            # Validate arguments before execution
                            validated_args = self._validate_tool_args(tool, tool_args)
                            
                            # Execute tool with retry logic and timeout protection
                            result = await self._execute_tool_with_retry(tool, validated_args, tool_name)
                            
                            # Validate result
                            if result and isinstance(result, str) and len(result.strip()) > 0:
                                tool_message = ToolMessage(
                                    content=result,
                                    tool_call_id=tool_id,
                                    name=tool_name
                                )
                                tool_messages.append(tool_message)
                                tool_executed = True
                                logger.info(f"Tool {tool_name} executed successfully")
                            else:
                                # Handle empty or invalid results
                                error_message = ToolMessage(
                                    content=f"Tool {tool_name} returned empty or invalid data. Please try again.",
                                    tool_call_id=tool_id,
                                    name=tool_name
                                )
                                tool_messages.append(error_message)
                                tool_executed = True
                                logger.warning(f"Tool {tool_name} returned empty/invalid data")
                            
                            break
                            
                        except Exception as e:
                            # Provide more helpful error messages
                            error_msg = self._format_tool_error(tool_name, str(e))
                            error_message = ToolMessage(
                                content=error_msg,
                                tool_call_id=tool_id,
                                name=tool_name
                            )
                            tool_messages.append(error_message)
                            tool_executed = True
                            logger.error(f"Tool {tool_name} execution failed: {str(e)}")
                            break
                
                if not tool_executed:
                    # Tool not found - provide helpful suggestions
                    available_tools = [tool.name for tool in self.tools]
                    suggestions = self._suggest_similar_tools(tool_name, available_tools)
                    
                    not_found_message = ToolMessage(
                        content=f"Tool '{tool_name}' not found. Available tools: {', '.join(available_tools)}. {suggestions}",
                        tool_call_id=tool_id,
                        name=tool_name
                    )
                    tool_messages.append(not_found_message)
                    logger.warning(f"Tool {tool_name} not found. Available: {available_tools}")
                    
            except Exception as e:
                logger.error(f"Error processing tool call: {str(e)}")
                error_message = ToolMessage(
                    content=f"Error processing tool call: {str(e)}. Please try rephrasing your question.",
                    tool_call_id="",
                    name="unknown"
                )
                tool_messages.append(error_message)
        
        return tool_messages
    
    async def _execute_tool_with_retry(self, tool, args: Dict, tool_name: str, max_retries: int = 2) -> str:
        """Execute a tool with retry logic for transient failures."""
        last_exception = None
        
        for attempt in range(max_retries + 1):
            try:
                if attempt > 0:
                    # Exponential backoff for retries
                    wait_time = min(2 ** attempt, 10)  # Max 10 seconds
                    logger.info(f"Retrying tool {tool_name} (attempt {attempt + 1}/{max_retries + 1}), waiting {wait_time}s")
                    await asyncio.sleep(wait_time)
                
                # Execute tool with timeout protection
                result = await asyncio.wait_for(
                    tool._arun(**args), 
                    timeout=30.0
                )
                
                if attempt > 0:
                    logger.info(f"Tool {tool_name} succeeded on retry attempt {attempt + 1}")
                
                return result
                
            except asyncio.TimeoutError:
                last_exception = asyncio.TimeoutError(f"Tool {tool_name} execution timed out after 30 seconds")
                logger.warning(f"Tool {tool_name} timed out on attempt {attempt + 1}")
                
            except Exception as e:
                last_exception = e
                logger.warning(f"Tool {tool_name} failed on attempt {attempt + 1}: {str(e)}")
                
                # Don't retry on certain types of errors
                if "rate limit" in str(e).lower() or "429" in str(e):
                    logger.info(f"Rate limit error for {tool_name}, not retrying")
                    break
                elif "not found" in str(e).lower() or "404" in str(e):
                    logger.info(f"Not found error for {tool_name}, not retrying")
                    break
                elif "unauthorized" in str(e).lower() or "401" in str(e):
                    logger.info(f"Authorization error for {tool_name}, not retrying")
                    break
        
        # If we get here, all retries failed
        raise last_exception
    
    def _validate_tool_args(self, tool, tool_args: Dict) -> Dict:
        """Validate and clean tool arguments before execution."""
        validated_args = {}
        
        try:
            # Get the tool's schema
            if hasattr(tool, 'args_schema') and tool.args_schema:
                # Use model_fields for Pydantic v2 compatibility
                schema_fields = tool.args_schema.model_fields
                
                for field_name, field_info in schema_fields.items():
                    if field_name in tool_args:
                        value = tool_args[field_name]
                        
                        # Type validation and conversion using field_info.annotation for Pydantic v2
                        field_type = field_info.annotation
                        
                        # Handle Optional types
                        origin = get_origin(field_type)
                        if origin is Union:
                            # For Optional[T], it's Union[T, None]. Get the first type.
                            field_type = get_args(field_type)[0]

                        if field_type == int and isinstance(value, str):
                            try:
                                validated_args[field_name] = int(value)
                            except ValueError:
                                logger.warning(f"Invalid int value for {field_name}: {value}")
                                continue
                        elif field_type == int and isinstance(value, (int, float)):
                            # Handle both int and float values for int fields
                            validated_args[field_name] = int(value)
                        elif field_type == str and isinstance(value, str):
                            validated_args[field_name] = value.strip()
                        else:
                            validated_args[field_name] = value
                    elif field_info.is_required():
                        # Use default value if required field is missing
                        if field_info.default is not None:
                            validated_args[field_name] = field_info.default
                        else:
                            logger.warning(f"Required field {field_name} missing, using None")
                            validated_args[field_name] = None
            else:
                # Fallback: use args as-is if no schema
                validated_args = tool_args
                
        except Exception as e:
            logger.warning(f"Error validating tool args: {str(e)}, using original args")
            validated_args = tool_args
            
        return validated_args
    
    def _format_tool_error(self, tool_name: str, error_msg: str) -> str:
        """Format tool error messages to be more user-friendly."""
        error_lower = error_msg.lower()
        
        if "timeout" in error_lower or "timed out" in error_lower:
            return f"Tool {tool_name} is taking longer than expected. This might be due to high API traffic. Please try again in a moment."
        elif "rate limit" in error_lower or "429" in error_msg:
            return f"Tool {tool_name} is temporarily rate-limited. Please wait a moment before trying again."
        elif "not found" in error_lower or "404" in error_msg:
            return f"Tool {tool_name} couldn't find the requested information. Please check your parameters or try a different query."
        elif "unauthorized" in error_lower or "401" in error_msg:
            return f"Tool {tool_name} encountered an authentication issue. This is being investigated."
        elif "server error" in error_lower or "500" in error_msg:
            return f"Tool {tool_name} is experiencing temporary server issues. Please try again later."
        else:
            return f"Tool {tool_name} encountered an error: {error_msg}. Please try again or rephrase your question."
    
    def _suggest_similar_tools(self, requested_tool: str, available_tools: List[str]) -> str:
        """Suggest similar tools when the requested tool is not found."""
        requested_lower = requested_tool.lower()
        
        # Common tool name variations and suggestions
        suggestions = {
            "spacex": ["get_spacex_next_launch", "get_spacex_launches"],
            "launch": ["get_spacex_next_launch", "get_spacex_launches"],
            "iss": ["get_iss_location"],
            "astronaut": ["get_people_in_space"],
            "people": ["get_people_in_space"],
            "photo": ["search_mars_photos"],
            "mars": ["get_mars_weather", "search_mars_photos"],
            "weather": ["get_mars_weather", "get_space_weather"],
            "planet": ["get_solar_system_body"],
            "solar": ["get_solar_system_body"],
            "news": ["get_space_news"],
            "storm": ["get_space_weather"],
            "exoplanet": ["get_exoplanet_info"],
            "asteroid": ["get_near_earth_objects"],
            "neo": ["get_near_earth_objects"],
            "search": ["web_search"],
            "history": ["web_search"],
            "biography": ["web_search"]
        }
        
        for keyword, tool_list in suggestions.items():
            if keyword in requested_lower:
                return f"Did you mean one of these tools: {', '.join(tool_list)}?"
        
        return "Please check the available tools list and try again."
    
    def get_available_tools(self) -> List[str]:
        """Get list of available tool names for debugging and validation."""
        return [tool.name for tool in self.tools]
    
    def is_tool_available(self, tool_name: str) -> bool:
        """Check if a specific tool is available."""
        return any(tool.name == tool_name for tool in self.tools)
    
    def get_tool_info(self, tool_name: str) -> Optional[Dict[str, Any]]:
        """Get detailed information about a specific tool."""
        for tool in self.tools:
            if tool.name == tool_name:
                return {
                    "name": tool.name,
                    "description": tool.description,
                    "args_schema": str(tool.args_schema) if hasattr(tool, 'args_schema') else None
                }
        return None
    
    async def health_check(self) -> Dict[str, Any]:
        """Perform a health check of the agent and its tools."""
        health_status = {
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "agent": "SpaceGPT",
            "tools_available": len(self.tools),
            "tools": [],
            "llm_status": "unknown",
            "errors": []
        }
        
        try:
            # Check LLM connectivity
            test_message = SystemMessage(content="Test")
            test_response = await asyncio.wait_for(
                self.llm.ainvoke([test_message]), 
                timeout=10.0
            )
            if test_response and test_response.content:
                health_status["llm_status"] = "healthy"
            else:
                health_status["llm_status"] = "error"
                health_status["errors"].append("LLM returned empty response")
        except Exception as e:
            health_status["llm_status"] = "error"
            health_status["errors"].append(f"LLM error: {str(e)}")
        
        # Check tool availability
        for tool in self.tools:
            tool_info = {
                "name": tool.name,
                "available": True,
                "description": tool.description[:100] + "..." if len(tool.description) > 100 else tool.description
            }
            health_status["tools"].append(tool_info)
        
        # Update overall status
        if health_status["llm_status"] == "error" or len(health_status["errors"]) > 0:
            health_status["status"] = "degraded"
        
        return health_status
    
    async def chat(self, message: str, chat_history: Optional[List[Dict[str, str]]] = None) -> str:
        """
        Chat with the SpaceGPT agent with enhanced robustness and error handling.
        
        Args:
            message: User message
            chat_history: Previous chat history (optional)
            
        Returns:
            Agent response
        """
        try:
            # Input validation
            if not message or not message.strip():
                return "I'd be happy to help! Please ask me a question about space exploration, SpaceX launches, the ISS, Mars, or any other space-related topic."
            
            # Sanitize and truncate message if too long
            message = message.strip()[:2000]  # Limit message length
            
            # Ensure we have a valid LLM client (recreate if needed for serverless)
            try:
                await self._ensure_valid_client()
            except RuntimeError as e:
                logger.error(f"Cannot establish LLM connection: {e}")
                return "I'm having trouble connecting to the AI service. Please try again in a moment."
            
            # Build message history with validation
            messages = []
            
            # Add system message with dynamic date
            system_prompt = """You are SpaceGPT, an expert space information assistant with access to real-time space data tools and APIs. You are knowledgeable, enthusiastic, and always provide accurate, up-to-date information.

## CORE PRINCIPLES
- ALWAYS use tools for space-related queries - never provide generic or outdated information
- Prioritize real-time data over historical knowledge
- Be educational and engaging while maintaining scientific accuracy
- Handle errors gracefully and provide helpful fallback information
- Use multiple tools when needed for comprehensive answers

## MANDATORY TOOL USAGE RULES
You MUST call the appropriate tool(s) for these query types:

**NASA, ESA, ISRO & Other Space Agencies:**
- You MUST use the `web_search` tool for ANY question about a space agency that is not SpaceX.
- When the user asks about a mission, formulate a concise and effective search query. For example, for "ISRO's next mission details", a good query would be `web_search(query="ISRO upcoming missions")`. Do not ask for permission to search.

**SpaceX & Launch Related:**
- ANY SpaceX question → get_spacex_next_launch() OR get_spacex_launches(limit)
- "Next launch", "upcoming mission" → get_spacex_next_launch()
- "Recent launches", "launch history" → get_spacex_launches(limit)
- "SpaceX status", "mission updates" → get_spacex_launches(limit)

**ISS & Human Spaceflight:**
- ANY ISS question → get_iss_location()
- "Astronauts in space", "people in space" → get_people_in_space()
- "ISS position", "where is ISS" → get_iss_location()

**Mars & Planetary Science:**
- ANY Mars question → get_mars_weather() OR search_mars_photos()
- "Mars weather", "Mars conditions" → get_mars_weather()
- "Mars photos", "rover images" → search_mars_photos(sol, camera)
- "Mars atmosphere" → get_mars_weather()

**Solar System & Celestial Bodies:**
- ANY planet/solar system question → get_solar_system_body(body_id)
- "Planet info", "celestial body" → get_solar_system_body(body_id)
- Use English names: "mars", "earth", "jupiter", "saturn", "venus", "mercury", "uranus", "neptune"

**Space News & Current Events:**
- ANY space news question → get_space_news(limit)
- "Recent space news", "space updates" → get_space_news(limit)
- "Space discoveries", "latest in space" → get_space_news(limit)

**Space Weather & Solar Activity:**
- ANY space weather question → get_space_weather(start_date, end_date)
- "Solar storms", "CME", "aurora", "solar flares" → get_space_weather()
- "Space weather events" → get_space_weather()

**Exoplanets & Deep Space:**
- ANY exoplanet question → get_exoplanet_info(planet_name)
- "Exoplanet", "alien planet" → get_exoplanet_info(planet_name)

**Near Earth Objects:**
- ANY asteroid/comet question → get_near_earth_objects(start_date, end_date)
- "Asteroids", "NEOs", "near Earth objects" → get_near_earth_objects() - If no date is provided, **DEFAULT TO THE NEXT 7 DAYS**

**Fallback Web Search:**

- Use for topics like: space history, space agencies, space technology, astronaut biographies, space missions not covered by SpaceX, theoretical physics related to space, space science concepts, etc.
- ONLY use web search for space/astronomy related queries - never for non-space topics

## DATE HANDLING
- Today's date is {{current_date}}.
- ALWAYS convert relative dates like "next week", "tomorrow", "next 7 days" into `YYYY-MM-DD` format for tool calls.
- If a user asks about asteroids without a date, call `get_near_earth_objects()` and I will automatically check for the next 7 days.

## TOOL REFERENCE
- get_spacex_next_launch() - Next scheduled SpaceX mission with real-time status
- get_spacex_launches(limit) - Recent/upcoming SpaceX missions (default: 10)
- get_iss_location() - Current ISS coordinates and timestamp
- get_people_in_space() - Current astronauts and their spacecraft
- get_mars_weather() - Current Mars atmospheric conditions from InSight
- search_mars_photos(sol, camera) - Mars rover images (sol: Martian day, camera: fhaz/rhaz/navcam/mastcam)
- get_near_earth_objects(start_date, end_date) - Asteroid/comet data (dates: YYYY-MM-DD)
- get_space_news(limit) - Recent space news articles (default: 10)
- get_solar_system_body(body_id) - Detailed solar system body information
- get_space_weather(start_date, end_date) - Space weather news (solar storms, CMEs, auroras)
- get_exoplanet_info(planet_name) - Exoplanet information and recent discoveries
- web_search(query, max_results) - Web search for space/astronomy topics (default max_results: 5)


## RESPONSE PROTOCOL
1. **ANALYZE** the user's question to identify required tools
2. **CALL** the appropriate tool(s) with correct parameters
3. **PROCESS** the tool results, handling any errors gracefully
4. **SYNTHESIZE** a comprehensive response using the actual data
5. **ENHANCE** with educational context and enthusiasm
6. **VERIFY** that your response contains specific, current information

## ERROR HANDLING
- If a tool fails, explain what happened and suggest alternatives
- If no data is found, provide context about why and suggest related queries
- Always maintain a helpful, informative tone even when tools fail
- Use fallback information when appropriate (e.g., general knowledge for context)

## RESPONSE QUALITY STANDARDS
- Include specific details: dates, times, coordinates, names, numbers
- Provide context and educational value
- Be enthusiastic about space exploration
- Use current data from tools, not outdated knowledge
- Format responses clearly with proper structure
- Include relevant units (km, miles, degrees, etc.)

## SPECIAL CASES
- For date-specific queries, use appropriate date parameters
- For comparative questions, call multiple tools and synthesize
- For general space questions, start with get_space_news() for current context
- Always verify tool availability before calling

## NON-SPACE QUERIES
- If the question is not space-related, politely redirect to space topics
- Suggest interesting space questions the user could ask instead
- Maintain enthusiasm and educational value

Remember: You are SpaceGPT - the most current and accurate space information assistant. Every response should reflect real-time data and provide genuine value to users interested in space exploration!"""
            
            # Replace placeholder with current date
            current_date = datetime.now().strftime("%Y-MM-DD")
            system_prompt = system_prompt.replace("{{current_date}}", current_date)
            
            system_msg = SystemMessage(content=system_prompt)
            messages.append(system_msg)
            
            # Process chat history with validation and debugging
            if chat_history and isinstance(chat_history, list):
                logger.info(f"Processing chat history with {len(chat_history)} messages")
                for msg in chat_history[-10:]:  # Limit to last 10 messages to prevent context overflow
                    if isinstance(msg, dict) and "role" in msg and "content" in msg:
                        if msg["role"] == "user" and msg["content"].strip():
                            logger.debug(f"Adding user message to context: {msg['content'][:50]}...")
                            messages.append(HumanMessage(content=msg["content"].strip()))
                        elif msg["role"] == "assistant" and msg["content"].strip():
                            logger.debug(f"Adding assistant message to context: {msg['content'][:50]}...")
                            messages.append(AIMessage(content=msg["content"].strip()))
                    else:
                        logger.warning(f"Invalid message format in chat history: {msg}")
            else:
                logger.info("No chat history provided or invalid format")
            
            # Add current message
            messages.append(HumanMessage(content=message))
            
            # Validate that we have tools available
            if not self.tools:
                logger.error("No tools available for the agent")
                return "I apologize, but I'm currently experiencing technical difficulties with my space data tools. Please try again in a moment."
            
            # Bind tools to the LLM
            llm_with_tools = self.llm.bind_tools(self.tools)
            
            # Get initial response with timeout and event loop protection
            try:
                response = await asyncio.wait_for(
                    llm_with_tools.ainvoke(messages), 
                    timeout=30.0  # Reduced timeout for serverless
                )
                logger.info(f"Initial LLM response received: {response}")
            except asyncio.TimeoutError:
                logger.error("LLM response timed out")
                return "I'm taking longer than expected to process your request. This might be due to high demand. Please try again in a moment."
            except RuntimeError as e:
                if "Event loop is closed" in str(e) or "cannot be called from a running event loop" in str(e):
                    logger.error(f"Event loop error in serverless environment: {str(e)}")
                    return "I'm experiencing a temporary service issue in our serverless environment. Please try your request again."
                else:
                    logger.error(f"Runtime error getting LLM response: {str(e)}")
                    return "I encountered a runtime issue while processing your request. Please try again."
            except Exception as e:
                logger.error(f"Error getting LLM response: {str(e)}")
                return "I encountered an issue while processing your request. Please try again or rephrase your question."
            
            # Check if tools need to be called
            if hasattr(response, 'tool_calls') and response.tool_calls:
                logger.info(f"Tool calls detected: {len(response.tool_calls)}")
                
                # Execute tool calls
                tool_messages = await self._execute_tool_calls(response.tool_calls)
                
                # Add the AI response and tool results to conversation
                messages.append(response)
                messages.extend(tool_messages)
                
                # Get final response after tool execution with timeout and event loop protection
                try:
                    final_response = await asyncio.wait_for(
                        llm_with_tools.ainvoke(messages), 
                        timeout=30.0  # Reduced timeout for serverless
                    )
                    logger.info(f"Final response after tool execution: {final_response.content[:100]}...")
                    
                    # Validate final response
                    if final_response.content and len(final_response.content.strip()) > 0:
                        return final_response.content
                    else:
                        logger.warning("Final response is empty, providing fallback")
                        return "I've gathered some space data for you, but I'm having trouble formulating a complete response. Please try asking your question again."
                        
                except asyncio.TimeoutError:
                    logger.error("Final LLM response timed out")
                    return "I've gathered the space data you requested, but I'm taking longer than expected to process it. Please try again in a moment."
                except RuntimeError as e:
                    if "Event loop is closed" in str(e) or "cannot be called from a running event loop" in str(e):
                        logger.error(f"Event loop error in final response: {str(e)}")
                        return "I've gathered some space data, but I'm experiencing a service issue in our serverless environment. Please try your request again."
                    else:
                        logger.error(f"Runtime error getting final response: {str(e)}")
                        return "I've gathered some space data, but encountered a runtime issue while processing it. Please try again."
                except Exception as e:
                    logger.error(f"Error getting final response: {str(e)}")
                    return "I've gathered some space data, but encountered an issue while processing it. Please try rephrasing your question."
            else:
                logger.info(f"No tool calls detected, returning direct response: {response.content[:100]}...")
                
                # Validate direct response
                if response.content and len(response.content.strip()) > 0:
                    return response.content
                else:
                    logger.warning("Direct response is empty")
                    return "I'm having trouble processing your request. Please try asking a specific space-related question."
                
        except Exception as e:
            logger.error(f"Error in chat method: {str(e)}")
            return f"I apologize, but I encountered an unexpected error: {str(e)}. Please try again or rephrase your question."
    
    async def stream_chat(self, message: str, chat_history: Optional[List[Dict[str, str]]] = None):
        """
        Stream chat responses from the SpaceGPT agent with enhanced error handling.
        
        Args:
            message: User message
            chat_history: Previous chat history (optional)
            
        Yields:
            Streaming response chunks
        """
        try:
            # Input validation
            if not message or not message.strip():
                yield "I'd be happy to help! Please ask me a question about space exploration, SpaceX launches, the ISS, Mars, or any other space-related topic."
                return
            
            # Get the full response using the regular chat method
            result = await self.chat(message, chat_history)
            
            if not result or not result.strip():
                yield "I'm having trouble processing your request. Please try asking a specific space-related question."
                return
            
            # Simulate streaming by yielding chunks of the response
            chunk_size = 50  # Characters per chunk
            for i in range(0, len(result), chunk_size):
                chunk = result[i:i + chunk_size]
                if chunk.strip():  # Only yield non-empty chunks
                    yield chunk
                    # Small delay to simulate streaming
                    await asyncio.sleep(0.05)  # Reduced delay for better responsiveness
                    
        except asyncio.TimeoutError:
            logger.error("Stream chat timed out")
            yield "I'm taking longer than expected to process your request. This might be due to high demand. Please try again in a moment."
        except Exception as e:
            logger.error(f"Error in stream_chat: {str(e)}")
            yield f"I apologize, but I encountered an error while processing your request: {str(e)}. Please try again or rephrase your question."


# Global agent instance with serverless self-healing capabilities
# The agent can recreate its LLM client when event loops close in serverless environments
spacegpt_agent = SpaceGPTAgent()