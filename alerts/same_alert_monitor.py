"""
Wraps the WXRadioReceiver to emit WeatherAlert objects (unified schema)
instead of raw SAMEAlerts.
"""
import uuid
import asyncio
from typing import Callable, Any
from alerts.nws_alert_monitor import WeatherAlert
from alerts.alert_classifier import LEVEL_COLORS
from wx_radio.wx_radio_receiver import WXRadioReceiver
from wx_radio.same_decoder import SAMEAlert
from core.logger import get_logger

logger = get_logger(__name__)


class SAMEAlertMonitor:
    def __init__(self, wx_receiver: WXRadioReceiver):
        self.receiver = wx_receiver
        self._callbacks: list[Callable[[WeatherAlert], Any]] = []
        
        # Register our internal callback with the receiver
        self.receiver.on_same_alert(self._handle_same_alert)
        
    def on_new_alert(self, callback: Callable[[WeatherAlert], Any]) -> None:
        """Register a callback for when a SAME alert is decoded."""
        self._callbacks.append(callback)
        
    def _handle_same_alert(self, same_alert: SAMEAlert) -> None:
        weather_alert = self._same_to_weather_alert(same_alert)
        
        for cb in self._callbacks:
            if asyncio.iscoroutinefunction(cb):
                # If we're called from a thread (we are), we need to handle async callbacks carefully
                try:
                    loop = asyncio.get_running_loop()
                    loop.create_task(cb(weather_alert))
                except RuntimeError:
                    # No event loop running in this thread
                    asyncio.run(cb(weather_alert))
            else:
                try:
                    cb(weather_alert)
                except Exception as e:
                    logger.error(f"SAMEAlertMonitor callback error: {e}")

    def _same_to_weather_alert(self, same: SAMEAlert) -> WeatherAlert:
        import datetime
        
        # SAME alerts give duration, calculate expiration
        expires = same.issued_at + datetime.timedelta(minutes=same.duration_minutes)
        
        return WeatherAlert(
            id=f"same_{uuid.uuid4().hex[:8]}", # Generate a unique ID
            event=same.event_name,
            headline=f"{same.event_name} issued by {same.call_sign}",
            description="Decoded from 162 MHz NOAA Weather Radio (SAME RF). NWS text not available offline.",
            severity="Unknown", # SAME doesn't explicitly send severity strings like NWS API
            urgency="Unknown",
            certainty="Unknown",
            effective=same.issued_at,
            expires=expires,
            area_desc=f"{len(same.fips_codes)} FIPS areas: {','.join(same.fips_codes)}",
            sender_name=same.call_sign,
            instruction=None,
            geometry=None, # SAME alerts don't have polygon geometry
            ui_level=same.ui_level,
            color=LEVEL_COLORS.get(same.ui_level, "#3b82f6"),
            source="same_rf"
        )
