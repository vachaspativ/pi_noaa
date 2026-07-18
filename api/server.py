"""
FastAPI application and Socket.IO server setup.
Manages the lifespan (startup/shutdown) of background tasks like NWS polling and WX radio.
"""
import socketio
import asyncio
from contextlib import asynccontextmanager
from datetime import datetime, timezone
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
            
    # 4. Start TLE maintainer loop
    async def tle_maintainer():
        from orbital.tle_staleness import tle_is_usable
        from orbital.tle_fetcher import fetch_and_cache_tles
        interval = cfg.pass_prediction.get("scheduler_interval_minutes", 60)
        while True:
            try:
                usable, reason = tle_is_usable()
                if not usable or reason == "stale":
                    logger.info(f"TLE data is {reason}, attempting to fetch fresh TLE...")
                    loop = asyncio.get_running_loop()
                    # fetch_and_cache_tles is blocking (httpx sync)
                    await loop.run_in_executor(None, fetch_and_cache_tles)
            except Exception as e:
                logger.error(f"Error in TLE maintainer: {e}")
            await asyncio.sleep(interval * 60)

    tle_task = asyncio.create_task(tle_maintainer())
    
    # 5. Start Pass Orchestrator loop (Time-shares the SDR for satellite passes)
    async def pass_orchestrator():
        from sdr.signal_recorder import record_pass
        from sdr.apt_decoder import decode_apt
        from sdr.image_processor import process_satdump_layers
        from alerts.cache_store import save_image
        from orbital.pass_predictor import get_next_pass
        
        logger.info("[Orchestrator] Satellite Pass Orchestrator loop started")
        
        while True:
            try:
                # Resolve mode and next pass
                mode = get_config().mode.get("primary", "auto")
                # We only orchestrate passes if the mode uses SDR (auto, dual, sdr_offline)
                # If it's api_only or degraded, we skip pass recording
                from core.mode_resolver import get_current_mode, OperatingMode
                current_mode = get_current_mode()
                
                if current_mode in (OperatingMode.API_ONLY, OperatingMode.DEGRADED):
                    await asyncio.sleep(30)
                    continue
                    
                next_pass = get_next_pass()
                if next_pass is None:
                    await asyncio.sleep(30)
                    continue
                    
                utc_now = datetime.now(timezone.utc)
                aos = next_pass.aos
                los = next_pass.los
                
                # Check if it is time to record.
                # If we are within the pass window (AOS to LOS), start recording.
                if utc_now >= aos and utc_now < los:
                    logger.info(f"[Orchestrator] Active satellite pass detected for {next_pass.satellite_name}. Initiating pass workflow.")
                    
                    # Notify UI that recording is starting
                    await sio.emit("pass_update", {
                        "state": "recording",
                        "satellite_name": next_pass.satellite_name,
                        "frequency_hz": next_pass.frequency_hz,
                        "aos": next_pass.aos.isoformat(),
                        "los": next_pass.los.isoformat(),
                    })
                    
                    # Stop Weather Radio if active to free up the SDR device
                    if app_state.wx_receiver and app_state.wx_receiver.is_monitoring:
                        logger.info("[Orchestrator] Stopping WX Radio receiver to release SDR hardware lock.")
                        app_state.wx_receiver.stop_monitoring()
                        # Short delay to allow OS drivers to release the interface cleanly
                        await asyncio.sleep(1.5)
                    
                    # Run recording (blocking call, offload to executor)
                    logger.info(f"[Orchestrator] Starting SDR recording for {next_pass.satellite_name}")
                    loop = asyncio.get_running_loop()
                    wav_path = await loop.run_in_executor(None, record_pass, next_pass)
                    
                    # Notify UI that recording has finished
                    await sio.emit("pass_update", {
                        "state": "decoding" if (wav_path and wav_path.exists()) else "failed",
                        "satellite_name": next_pass.satellite_name,
                    })
                    
                    if wav_path and wav_path.exists():
                        logger.info(f"[Orchestrator] Recording finished successfully: {wav_path.name}. Beginning SatDump demodulation.")
                        
                        # Run decoding (blocking call, offload to executor)
                        layers = await loop.run_in_executor(None, decode_apt, wav_path)
                        
                        if layers:
                            # Generate thumbnails and process colormap layers
                            processed_layers = process_satdump_layers(layers)
                            
                            # Prepare metadata payload for database
                            timestamp_str = utc_now.strftime("%Y%m%d_%H%M%S")
                            safe_name = next_pass.satellite_name.replace(" ", "_")
                            img_id = f"{safe_name}_{timestamp_str}"
                            
                            image_metadata = {
                                "id": img_id,
                                "satellite_name": next_pass.satellite_name,
                                "captured_at": utc_now.isoformat(),
                            }
                            
                            # Convert Path objects to string paths for JSON serialization
                            for layer_name, path in processed_layers.items():
                                image_metadata[layer_name] = str(path)
                            
                            logger.info(f"[Orchestrator] Saving image metadata to cache for {img_id}")
                            save_image(image_metadata)
                            
                            # Push WS event to notify client
                            await sio.emit("new_image", image_metadata)
                            logger.info(f"[Orchestrator] Pushed new_image WS update for {img_id}")
                            
                            await sio.emit("pass_update", {
                                "state": "complete",
                                "satellite_name": next_pass.satellite_name,
                                "image_id": img_id,
                            })
                        else:
                            logger.error("[Orchestrator] SatDump decoding failed or returned no layers.")
                            await sio.emit("pass_update", {
                                "state": "decode_failed",
                                "satellite_name": next_pass.satellite_name,
                            })
                    else:
                        logger.error("[Orchestrator] Satellite recording returned empty WAV file or failed.")
                    
                    # Restore Weather Radio monitoring if enabled in config
                    if cfg.noaa_weather_radio.get("enabled", False) and app_state.wx_receiver:
                        freq = cfg.noaa_weather_radio.get("preferred_frequency_hz")
                        if freq:
                            logger.info(f"[Orchestrator] Restoring WX Radio monitoring on {freq / 1e6:.4f} MHz")
                            app_state.wx_receiver.start_monitoring(freq)
                    
                    # Post-recording cooldown: sleep past LOS to avoid
                    # re-detecting this same pass on the next loop iteration
                    remaining = (los - datetime.now(timezone.utc)).total_seconds()
                    if remaining > 0:
                        logger.debug(f"[Orchestrator] Post-recording cooldown: sleeping {remaining:.0f}s past LOS")
                        await asyncio.sleep(remaining + 5)
                    else:
                        await asyncio.sleep(5)
                            
                elif utc_now < aos:
                    # Pass is in the future. Sleep until shortly before AOS,
                    # capped at 30 seconds, and clamped to at least 1 second
                    # to avoid negative/zero sleeps that spin the event loop.
                    sleep_time = (aos - utc_now).total_seconds()
                    await asyncio.sleep(max(1, min(sleep_time - 5, 30)))
                    continue
                else:
                    # Pass has already ended, sleep a moment before fetching next
                    await asyncio.sleep(10)
                    
            except Exception as e:
                logger.error(f"[Orchestrator] Error in background pass loop: {e}", exc_info=True)
                await asyncio.sleep(30)

    pass_task = asyncio.create_task(pass_orchestrator())

    # Attach state to app
    app.state.nws_monitor = app_state.nws_monitor
    app.state.same_active_alerts = app_state.same_active_alerts
    app.state.wx_receiver = app_state.wx_receiver
    
    yield
    
    # Shutdown
    logger.info("Shutting down API server lifespan")
    if app_state.nws_monitor:
        app_state.nws_monitor.stop()
    if app_state.wx_receiver:
        app_state.wx_receiver.stop_monitoring()
    
    nws_task.cancel()
    tle_task.cancel()
    pass_task.cancel()


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
