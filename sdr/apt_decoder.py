"""
Decodes APT signal from WAV files into weather satellite images.
Wraps the aptdec command-line tool.
"""
import subprocess
from pathlib import Path
from core.config_loader import get_config
from core.logger import get_logger

logger = get_logger(__name__)


def decode_apt(wav_path: Path) -> Path | None:
    """
    Decode an APT signal WAV file into a weather image.

    Args:
        wav_path: Path to the input WAV recording.

    Returns:
        Path to the decoded image file, or None on failure.
    """
    cfg = get_config()
    apt_cfg = cfg.apt_decoder
    output_dir = Path(apt_cfg["output_dir"])
    output_dir.mkdir(parents=True, exist_ok=True)

    wav_path = Path(wav_path)
    if not wav_path.exists():
        logger.error(f"WAV file not found: {wav_path}")
        return None

    # Output filename: same stem as WAV, with configured image format
    img_format = apt_cfg.get("image_format", "png")
    output_name = f"{wav_path.stem}.{img_format}"
    output_path = output_dir / output_name

    backend = apt_cfg.get("backend", "aptdec")

    if backend == "aptdec":
        return _decode_with_aptdec(wav_path, output_path, apt_cfg)
    else:
        logger.error(f"Unsupported APT decoder backend: {backend}")
        return None


def _decode_with_aptdec(
    wav_path: Path, output_path: Path, apt_cfg: dict
) -> Path | None:
    """Run aptdec to decode the WAV file."""
    aptdec_path = apt_cfg.get("aptdec_path", "aptdec")

    cmd = [aptdec_path]

    # Add enhancement options
    for enh in apt_cfg.get("enhancements", []):
        cmd.extend(["-e", enh])

    # Output path
    cmd.extend(["-o", str(output_path)])

    # Input WAV file
    cmd.append(str(wav_path))

    logger.info(f"Decoding APT: {wav_path.name} → {output_path.name}")
    logger.debug(f"aptdec command: {' '.join(cmd)}")

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=120,
        )

        if result.stderr:
            logger.debug(f"aptdec stderr: {result.stderr}")

        if result.returncode == 0 and output_path.exists():
            logger.info(f"APT decode success: {output_path}")
            return output_path
        else:
            logger.error(
                f"aptdec failed (code {result.returncode}): {result.stderr}"
            )
            return None

    except FileNotFoundError:
        logger.error(
            f"aptdec not found at '{aptdec_path}'. "
            "Install it via: scripts/install_deps.sh"
        )
        return None
    except subprocess.TimeoutExpired:
        logger.error("aptdec timed out after 120 seconds")
        return None
