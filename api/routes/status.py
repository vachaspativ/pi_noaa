"""
System health and status API routes.
"""
import shutil
import psutil
from fastapi import APIRouter
from core.mode_resolver import get_current_mode
from core.connectivity import is_internet_available
from orbital.tle_staleness import get_tle_age_hours, tle_is_usable
from sdr.sdr_controller import SDRController

router = APIRouter(tags=["status"])

# Instantiate once for status checks
_sdr_controller = SDRController()


@router.get("/status")
async def get_system_status():
    """Return comprehensive system health and status."""
    
    # Mode & connectivity
    mode = get_current_mode()
    mode_str = mode.value if mode else "unknown"
    internet = is_internet_available()
    
    # TLE
    tle_age = get_tle_age_hours()
    tle_usable, tle_msg = tle_is_usable()
    
    # SDR
    sdr_present = _sdr_controller.is_hardware_present()
    sdr_recording = _sdr_controller.is_recording
    
    # System resources
    disk = shutil.disk_usage("/")
    disk_percent = (disk.used / disk.total) * 100
    
    cpu_percent = psutil.cpu_percent(interval=0.1)
    mem = psutil.virtual_memory()
    
    return {
        "mode": mode_str,
        "internet_available": internet,
        "sdr": {
            "present": sdr_present,
            "recording": sdr_recording,
        },
        "tle": {
            "age_hours": round(tle_age, 2) if tle_age else None,
            "usable": tle_usable,
            "message": tle_msg
        },
        "system": {
            "disk_usage_percent": round(disk_percent, 1),
            "cpu_percent": round(cpu_percent, 1),
            "memory_percent": round(mem.percent, 1)
        }
    }
