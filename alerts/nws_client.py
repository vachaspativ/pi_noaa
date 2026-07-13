"""
Client for the National Weather Service (api.weather.gov) API.
Fetches active alerts as GeoJSON features.
"""
import httpx
from core.config_loader import get_config
from core.logger import get_logger

logger = get_logger(__name__)


class NWSAPIError(Exception):
    """Raised when the NWS API returns a non-200 or fails."""
    pass


class NWSClient:
    def __init__(self):
        self.cfg = get_config()
        nws_cfg = self.cfg.nws_api
        
        self.base_url = nws_cfg["base_url"]
        self.timeout = nws_cfg.get("request_timeout_seconds", 15)
        
        # NWS requires a descriptive User-Agent
        self.headers = {
            "User-Agent": nws_cfg.get("user_agent", "pi_noaa/2.0"),
            "Accept": "application/geo+json"
        }
        
    async def fetch_active_alerts(self, zone: str | None = None) -> list[dict]:
        """
        Fetch active alerts from the NWS API.
        
        Args:
            zone: Optional specific NWS zone ID (e.g. ILC031). 
                  If None, reads from config.
                  
        Returns:
            List of GeoJSON feature dictionaries.
            
        Raises:
            NWSAPIError: on HTTP errors or timeouts.
        """
        if not zone:
            zone = self.cfg.nws_api.get("alert_zone")
            
        if not zone:
            logger.warning("No NWS alert_zone configured, fetching all US alerts (huge!)")
            url = f"{self.base_url}/alerts/active"
        else:
            url = f"{self.base_url}/alerts/active/zone/{zone}"
            
        try:
            async with httpx.AsyncClient(headers=self.headers, timeout=self.timeout) as client:
                logger.debug(f"[NWS API] Connecting to fetch alerts from: {url}")
                response = await client.get(url)
                
                logger.debug(f"[NWS API] Response received - Status: {response.status_code}, Bytes: {len(response.content)}")
                if response.status_code != 200:
                    raise NWSAPIError(
                        f"NWS API returned {response.status_code}: {response.text}"
                    )
                    
                data = response.json()
                features = data.get("features", [])
                logger.debug(f"[NWS API] Successfully parsed {len(features)} active NWS alerts from JSON payload")
                logger.info(f"Fetched {len(features)} active NWS alerts")
                return features
                
        except httpx.RequestError as e:
            raise NWSAPIError(f"Request failed: {e}")
        except ValueError as e:
            raise NWSAPIError(f"Invalid JSON response: {e}")
