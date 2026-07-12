"""
Periodically polls the NWS API and normalizes GeoJSON features into WeatherAlert objects.
"""
import asyncio
import dateutil.parser
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Optional, Callable, Any
from alerts.nws_client import NWSClient, NWSAPIError
from alerts.alert_classifier import classify_alert
from alerts.cache_store import save_alert
from core.config_loader import get_config
from core.logger import get_logger

logger = get_logger(__name__)


@dataclass
class WeatherAlert:
    id: str
    event: str
    headline: str
    description: str
    severity: str
    urgency: str
    certainty: str
    effective: datetime
    expires: datetime
    area_desc: str
    sender_name: str
    instruction: Optional[str]
    geometry: Optional[dict]
    ui_level: str
    color: str
    source: str = "nws_api"


class NWSAlertMonitor:
    def __init__(self):
        self.client = NWSClient()
        self.cfg = get_config()
        self._active_alerts: list[WeatherAlert] = []
        self._seen_ids: set[str] = set()
        self._callbacks: list[Callable[[WeatherAlert], Any]] = []
        self._polling = False
        self._task: asyncio.Task | None = None

    def on_new_alert(self, callback: Callable[[WeatherAlert], Any]) -> None:
        """Register a callback (sync or async) for new NWS alerts."""
        self._callbacks.append(callback)

    @property
    def active_alerts(self) -> list[WeatherAlert]:
        return self._active_alerts

    async def run_polling_loop(self) -> None:
        """Run continuous polling loop for the lifetime of the application."""
        if self._polling:
            return
        
        self._polling = True
        poll_interval = self.cfg.nws_api.get("poll_interval_seconds", 60)
        logger.info(f"Started NWS API polling loop (every {poll_interval}s)")
        
        while self._polling:
            try:
                await self.fetch_alerts()
            except Exception as e:
                logger.error(f"Error in NWS poll loop: {e}")
                
            await asyncio.sleep(poll_interval)

    def stop(self):
        self._polling = False

    async def fetch_alerts(self) -> list[WeatherAlert]:
        """Fetch, parse, cache, and return active alerts."""
        try:
            features = await self.client.fetch_active_alerts()
        except NWSAPIError as e:
            logger.warning(f"Failed to fetch NWS alerts: {e}")
            return self._active_alerts
            
        parsed_alerts = []
        new_alerts = []
        
        for feature in features:
            props = feature.get("properties", {})
            alert_id = props.get("id")
            
            if not alert_id:
                continue
                
            # Parse dates separately
            now = datetime.now(timezone.utc)
            try:
                effective = dateutil.parser.parse(props.get("effective", ""))
            except (ValueError, TypeError, Exception):
                effective = now
                
            try:
                expires = dateutil.parser.parse(props.get("expires", ""))
            except (ValueError, TypeError, Exception):
                expires = effective
                
            # Filter expired alerts
            if expires < datetime.now(timezone.utc):
                continue
                
            event = props.get("event", "Unknown Event")
            severity = props.get("severity", "Unknown")
            ui_level, color = classify_alert(event, severity)
            
            alert = WeatherAlert(
                id=alert_id,
                event=event,
                headline=props.get("headline", ""),
                description=props.get("description", ""),
                severity=severity,
                urgency=props.get("urgency", ""),
                certainty=props.get("certainty", ""),
                effective=effective,
                expires=expires,
                area_desc=props.get("areaDesc", ""),
                sender_name=props.get("senderName", ""),
                instruction=props.get("instruction"),
                geometry=feature.get("geometry"),
                ui_level=ui_level,
                color=color,
            )
            
            parsed_alerts.append(alert)
            
            if alert.id not in self._seen_ids:
                self._seen_ids.add(alert.id)
                new_alerts.append(alert)
                
                # Save to offline cache
                save_alert(self._alert_to_cache_dict(alert))
                
        self._active_alerts = parsed_alerts
        
        # Fire callbacks for genuinely new alerts
        for alert in new_alerts:
            for cb in self._callbacks:
                if asyncio.iscoroutinefunction(cb):
                    await cb(alert)
                else:
                    cb(alert)
                    
        return parsed_alerts

    def _alert_to_cache_dict(self, alert: WeatherAlert) -> dict:
        """Convert dataclass to simple dict for cache_store."""
        d = asdict(alert)
        d["effective"] = alert.effective.isoformat()
        d["expires"] = alert.expires.isoformat()
        return d
