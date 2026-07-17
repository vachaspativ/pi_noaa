"""
Orchestrates recording of a full satellite pass.
Arms the SDR before AOS, records until LOS, returns WAV path.
"""
import time
from pathlib import Path
from datetime import datetime, timezone
from core.config_loader import get_config
from core.logger import get_logger

logger = get_logger(__name__)


def record_pass(satellite_pass) -> Path | None:
    """
    Record a complete satellite pass to WAV file.

    Args:
        satellite_pass: A SatellitePass dataclass with satellite_name,
                       frequency_hz, aos, los attributes.

    Returns:
        Path to the recorded WAV file, or None on failure.
    """
    from sdr.sdr_controller import SDRController

    cfg = get_config()
    rec_cfg = cfg.recording
    output_dir = Path(rec_cfg["output_dir"])
    output_dir.mkdir(parents=True, exist_ok=True)

    # Generate filename from satellite name + timestamp
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    safe_name = satellite_pass.satellite_name.replace(" ", "_")
    filename = f"{safe_name}_{timestamp}.wav"
    output_path = output_dir / filename

    sdr = SDRController()

    if not sdr.is_hardware_present():
        logger.error("SDR hardware not present — cannot record pass")
        return None

    # Calculate recording duration (remaining time until LOS)
    if satellite_pass.aos and satellite_pass.los:
        now = datetime.now(timezone.utc)
        duration_seconds = max(0.0, (satellite_pass.los - now).total_seconds())
    else:
        duration_seconds = rec_cfg.get("max_recording_minutes", 20) * 60

    # Apply safety cap
    max_seconds = rec_cfg.get("max_recording_minutes", 20) * 60
    duration_seconds = min(duration_seconds, max_seconds)

    logger.info(
        f"Recording pass: {satellite_pass.satellite_name} "
        f"@ {satellite_pass.frequency_hz / 1e6:.4f} MHz "
        f"for {duration_seconds:.0f}s → {output_path}"
    )

    # Start recording
    if not sdr.start_recording(satellite_pass.frequency_hz, output_path):
        logger.error("Failed to start SDR recording")
        return None

    try:
        # Wait for the pass duration
        time.sleep(duration_seconds)
    except KeyboardInterrupt:
        logger.warning("Recording interrupted by user")
    finally:
        sdr.stop_recording()

    if output_path.exists() and output_path.stat().st_size > 0:
        logger.info(f"Recording complete: {output_path} ({output_path.stat().st_size} bytes)")

        # Optionally clean up raw recording after decode
        if not rec_cfg.get("keep_raw_recordings", False):
            logger.debug(f"Raw recording will be deleted after decode: {output_path}")

        return output_path
    else:
        logger.error(f"Recording file missing or empty: {output_path}")
        return None
