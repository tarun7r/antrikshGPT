# antrikshGPT - AI Space Explorer

> **Antriksh** (अंतरिक्ष) means "space" in Sanskrit/Hindi

An impressive AI-powered space exploration webapp that combines cutting-edge AI with real-time space data to create an immersive cosmic experience. This version is optimized for serverless deployment on Vercel.

## Quick Start

### Prerequisites
- Python 3.8+
- Vercel account and Vercel CLI
- pip package manager

### Installation & Local Launch

1. **Clone and navigate to the project:**
   ```bash
   git clone https://github.com/your-username/antrikshGPT.git
   cd antrikshGPT
   ```

2. **Set up environment variables:**
   Create a `.env` file from `env.sample` and add your API keys:
   ```bash
   cp env.sample .env
   ```
   - **`GOOGLE_API_KEY`**: Your Google AI API key for Gemini.
   - **`SECRET_KEY`**: A secret key for JWT, generate with `openssl rand -hex 32`.

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Create a default admin user:**
   The application uses a JSON file (`users.json`) for user management. A default admin user is created automatically with a secure, randomly generated password upon first launch.
   
   Check the console output for the admin password when you first run the app.

5. **Start the webapp:**
   ```bash
   cd webapp/backend
   python3 main.py
   ```

6. **Open your browser and visit:**
   ```
   http://localhost:8000
   ```

   You'll see a stunning space-themed interface that will definitely impress!

### Deployment to Vercel

This app is optimized for serverless deployment on Vercel.

1. **Install Vercel CLI and log in:**
   ```bash
   npm install -g vercel
   vercel login
   ```

2. **Deploy the app:**
   Run the `vercel` command from the project root:
   ```bash
   vercel
   ```
   Vercel will automatically detect the configuration in `vercel.json` and deploy the app.

3. **Set environment variables in Vercel:**
   - Go to your Vercel project settings -> Environment Variables.
   - Add `GOOGLE_API_KEY` and `SECRET_KEY`.

## Demo Queries to Showcase

Try these impressive queries to demonstrate the system's capabilities:

- **"Where is the ISS right now?"** - Shows real-time tracking
- **"What's the next SpaceX launch?"** - Displays upcoming mission details
- **"Show me today's NASA picture"** - Beautiful astronomy imagery
- **"What's the weather like on Mars?"** - Mars atmospheric data
- **"Who is currently in space?"** - Live astronaut information
- **"Tell me about recent space discoveries"** - Latest space news
- **"Show me Mars rover photos"** - Stunning images from Mars

## Architecture

### Backend (FastAPI)
- **FastAPI** server with WebSocket support
- **LangChain/LangGraph** agent with a robust system prompt and Gemini 2.5 Flash integration
- **12+ MCP (Model Context Protocol) tools** for seamless space data integration
- **RESTful APIs** and WebSocket endpoints for flexible connectivity
- **JWT-based Authentication** for secure admin endpoints
- **Optimized for Serverless** deployment on Vercel

### Frontend (Modern Web)
- **Pure JavaScript** with modern ES6+ features
- **CSS3 animations** and space-themed styling
- **WebSocket client** for real-time updates
- **Responsive grid layout** with interactive widgets
- **Progressive enhancement** for optimal performance
- **Spaceflight News API** for the latest breaking news
- **The Solar System / Opendata API** for detailed planetary information
- **JSON file** for simple user database

### Data Sources
- **NASA APIs** (APOD, Mars Weather, NEOs, Mars Photos)
- **SpaceX/Launch Library** for mission data
- **Open Notify** for ISS and astronaut tracking
- **Spaceflight News API** for latest space news
- **Solar System API** for planetary information

## Project Structure

```
antrikshGPT/
├── api/
│   └── index.py                 # Vercel serverless function entrypoint
├── config/
│   ├── __init__.py
│   └── settings.py              # Configuration and API keys
├── shared/
│   ├── __init__.py
│   ├── langchain_agent.py       # Core AI agent with Gemini and robust error handling
│   └── space_apis.py            # 12+ space API integrations with caching
├── mcp_server/
│   ├── __init__.py
│   └── fastmcp_server.py        # MCP server implementation
├── webapp/
│   ├── backend/
│   │   ├── __init__.py
│   │   └── main.py              # FastAPI server with WebSockets
│   └── frontend/
│       ├── index.html           # Beautiful space-themed interface
│       ├── style.css            # Stunning CSS with animations
│       ├── script.js            # Interactive JavaScript
│       └── favicon.ico          # Space-themed favicon
├── requirements.txt             # Python dependencies
├── users.json                   # Simple user database
├── vercel.json                  # Vercel deployment configuration
└── README.md                    # This file
```

## Features That Will Impress

### Advanced AI Assistant
- **Gemini 2.5 Flash** powered conversational AI for exceptional performance and accuracy
- **12+ Specialized Space Tools** for real-time, accurate data retrieval
- **Robust Error Handling** with graceful fallbacks and intelligent retries
- **Context-Aware Responses** for engaging and relevant conversations
- **Natural language queries** for complex space topics and missions

### Real-Time Space Data
- **Live ISS Tracking** - Real-time International Space Station location with animated visualization
- **SpaceX Mission Data** - Current and upcoming launches with detailed mission info
- **Space News Feed** - Latest space discoveries and mission updates
- **Astronaut Tracker** - Live count and details of people currently in space
- **Mars Weather** - Current atmospheric conditions on Mars
- **NASA APOD** - Daily astronomy picture with explanations
- **Near Earth Objects** - Asteroid and comet tracking
- **Solar System Data** - Detailed planetary and celestial body information

### Production-Ready Enhancements
- **Smart Caching System** - Advanced caching with TTL and rate limiting to reduce latency and API usage
- **Rate Limit Protection** - Prevents API quota exhaustion and ensures high availability
- **Fallback Data** and Graceful Degradation when APIs are unavailable
- **Cache Indicators** - Visual indicators show live vs cached data
- **Monitoring Endpoints** - Cache statistics and health monitoring for observability
- **Admin Endpoints** - Secure endpoints for cache management
- **Background Processing** and intelligent data pre-loading
- **WebSocket Real-time** updates with cache awareness

## Key Technologies

- **AI/ML:** Gemini 2.5 Flash, LangChain, LangGraph
- **Backend:** FastAPI, WebSockets, AsyncIO
- **Frontend:** Modern HTML5/CSS3/ES6+, WebSocket client
- **Deployment:** Vercel (Serverless)
- **APIs:** NASA, SpaceX, Launch Library, Open Notify
- **Tools:** Python 3.12, MCP (Model Context Protocol)
- **Authentication:** JWT, passlib, python-jose

## Space Data Coverage

| Data Source | Real-time | Cached | Features |
|-------------|-----------|---------|----------|
| ISS Location | Yes (30s) | Yes (5min) | Live tracking, altitude, coordinates |
| SpaceX Launches | Yes | Yes (5min) | Mission details, status, countdown |
| NASA APOD | Daily | Yes (1day) | HD images, explanations |
| Astronauts | Yes | Yes (5min) | Names, spacecraft, count |
| Mars Weather | Yes | Yes (1hr) | Temperature, pressure, season |
| Space News | Yes | Yes (5min) | Latest articles, summaries |
| Planetary Data | Yes | Yes (1day) | Detailed info on planets, moons, etc. |

## Configuration

The app uses API keys stored in a `.env` file (create from `env.sample`):
- **Google AI API** for Gemini 2.5 Flash
- **NASA API** for space data
- **`SECRET_KEY`** for JWT token encryption

### Other APIs
- **Other APIs** are public/free (no keys required)

## Production-Ready Features

- **Smart Caching System** - Advanced caching with TTL and rate limiting
- **Rate Limit Protection** - Prevents API quota exhaustion
- **Fallback Data** - Graceful degradation when APIs are unavailable
- **Cache Indicators** - Visual indicators show live vs cached data
- **Monitoring Endpoints** - Cache statistics and health monitoring
- **Secure Admin Actions** - Authenticated endpoint for clearing cache
- **Background Processing** - Intelligent data pre-loading
- **WebSocket Real-time** - Live updates with cache awareness
- **Deployment Ready** - Production configuration included for Vercel
- **Robust Agent** - Advanced error handling, retries, and system prompt

## License

This project is open source and available under the MIT License.

---

**Built with love for space exploration and AI innovation**

*"ऋतं सत्यं परं ब्रह्म।" - "Cosmic order (ṛta) and truth (satya) are the supreme Brahman."*
