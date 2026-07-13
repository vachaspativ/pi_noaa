"""
FastAPI application and Socket.IO server setup.
Manages the lifespan (startup/shutdown) of background tasks like NWS polling and WX radio.
"""
import socketio
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path

from core.config_loader import get_config
from core.mode_resolver import OperatingMode, on_mode_change
from core.logger import get_logger

# Import routers
from api.routes import passes, images, alerts, status, config_view

logger = get_logger(__name__)

# Socket.IO server
sio = socketio.AsyncServer(async_mode="asgi", cors_allowed_origins="*")

# Create a global state to hold our monitors so routers can access them
class AppState:
    def __init__(self):
        self.nws_monitor = None
        self.wx_receiver = None
        self.same_monitor = None
        self.same_active_alerts = [] # We maintain a small list of active SAME alerts

app_state = AppState()


async def push_new_alert(alert):
    """Push a single new alert via WebSocket."""
    logger.info(f"WebSocket Push: New alert {alert.event}")
    await sio.emit("new_alert", alert.__dict__)


def handle_mode_change(mode: OperatingMode):
    """Push mode changes to clients via WebSocket."""
    # We must schedule the async emit from this sync callback
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(sio.emit("mode_change", mode.value))
    except RuntimeError:
        pass


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage background tasks for the lifetime of the application."""
    cfg = get_config()
    logger.info("Starting API server lifespan")
    
    # 1. Register Mode Change Callback
    on_mode_change(handle_mode_change)
    
    # 2. Start NWS Alert Monitor if API enabled
    # We import here to avoid circular imports if any
    from alerts.nws_alert_monitor import NWSAlertMonitor
    
    # Check if we should start the monitor based on config/mode
    # For phase 1, we'll start it and let it figure out if it has internet
    app_state.nws_monitor = NWSAlertMonitor()
    app_state.nws_monitor.on_new_alert(push_new_alert)
    
    # Start polling loop as a background task
    nws_task = asyncio.create_task(app_state.nws_monitor.run_polling_loop())
    
    # 3. Start WX Radio Receiver if enabled
    if cfg.noaa_weather_radio.get("enabled", False):
        from wx_radio.wx_radio_receiver import WXRadioReceiver
        from alerts.same_alert_monitor import SAMEAlertMonitor
        
        app_state.wx_receiver = WXRadioReceiver()
        app_state.same_monitor = SAMEAlertMonitor(app_state.wx_receiver)
        
        # When same monitor gets an alert, append to our active list and push
        def on_same(alert):
            app_state.same_active_alerts.append(alert)
            # In a real app we'd purge expired ones here
            try:
                loop = asyncio.get_running_loop()
                loop.create_task(push_new_alert(alert))
            except RuntimeError:
                pass
                
        app_state.same_monitor.on_new_alert(on_same)
        
        # Start monitoring the preferred frequency
        freq = cfg.noaa_weather_radio.get("preferred_frequency_hz")
        if freq:
            app_state.wx_receiver.start_monitoring(freq)
            
    # Attach state to app
    app.state.nws_monitor = app_state.nws_monitor
    app.state.same_active_alerts = app_state.same_active_alerts
    
    yield
    
    # Shutdown
    logger.info("Shutting down API server lifespan")
    if app_state.nws_monitor:
        app_state.nws_monitor.stop()
    if app_state.wx_receiver:
        app_state.wx_receiver.stop_monitoring()
    
    nws_task.cancel()


def build_app(mode: OperatingMode) -> socketio.ASGIApp:
    """Build and configure the FastAPI application."""
    cfg = get_config()
    
    app = FastAPI(
        title="pi_noaa",
        description="Weather Satellite Receiving Station",
        version="1.0.0",
        lifespan=lifespan
    )
    
    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cfg.server.get("cors_origins", ["*"]),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Include routers
    app.include_router(passes.router, prefix="/api")
    app.include_router(images.router, prefix="/api")
    app.include_router(alerts.router, prefix="/api")
    app.include_router(status.router, prefix="/api")
    app.include_router(config_view.router, prefix="/api")
    
    # Static files for UI
    ui_dir = Path(__file__).parent.parent / "ui"
    static_dir = ui_dir / "static"
    templates_dir = ui_dir / "templates"
    
    # Create them if they don't exist yet
    static_dir.mkdir(parents=True, exist_ok=True)
    templates_dir.mkdir(parents=True, exist_ok=True)
    
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")
    
    # Root route to serve index.html
    @app.get("/")
    async def get_index():
        index_path = templates_dir / "index.html"
        from fastapi.responses import FileResponse
        if index_path.exists():
            return FileResponse(index_path)
        return {"message": "pi_noaa API is running. UI not found."}
    
    # Wrap with Socket.IO ASGI app
    socket_app = socketio.ASGIApp(sio, app)
    
    return socket_app
