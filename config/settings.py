"""
Configuration settings for SpaceGPT application.
"""
import os
from typing import Optional
from pydantic_settings import BaseSettings
from dotenv import load_dotenv

load_dotenv()


class Settings(BaseSettings):
    """
    Application settings, loaded from environment variables or a .env file.
    """
    APP_NAME: str = "antrikshGPT"
    
    # Space API Keys
    nasa_api_key: Optional[str] = "DEMO_KEY"
    google_api_key: Optional[str] = None
    spacex_api_base: Optional[str] = "https://api.spacexdata.com/v4"
    
    # Langchain Agent
    OPENAI_API_KEY: Optional[str] = None
    
    # Secret Key for JWT
    SECRET_KEY: str
    
    # MCP Server Configuration
    mcp_server_host: str = "localhost"
    mcp_server_port: int = 8001
    
    # Web App Configuration
    webapp_host: str = "localhost"
    webapp_port: int = 8000
    
    # LangChain Configuration
    langchain_tracing_v2: bool = False
    langchain_api_key: Optional[str] = None
    
    # Development
    debug: bool = True
    log_level: str = "INFO"
    
    class Config:
        """
        Configuration for loading settings from environment variables or a .env file.
        """
        env_file = ".env"
        env_file_encoding = "utf-8"


# Global settings instance
settings = Settings()