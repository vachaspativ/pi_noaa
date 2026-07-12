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
    sat_cfg = cfg.satdump_decoder
    output_dir = Path(sat_cfg["output_dir"])
    output_dir.mkdir(parents=True, exist_ok=True)

    wav_path = Path(wav_path)
    if not wav_path.exists():
        logger.error(f"WAV file not found: {wav_path}")
        return None

    backend = sat_cfg.get("backend", "satdump")
    if backend == "satdump":
        return _decode_with_satdump(wav_path, output_dir, sat_cfg)
    else:
        logger.error(f"Unsupported decoder backend: {backend}")
        return None


def _decode_with_satdump(
    wav_path: Path, final_output_dir: Path, sat_cfg: dict
) -> dict[str, Path] | None:
    """Run SatDump to decode the WAV file and extract requested products."""
    import shutil
    import tempfile

    satdump_path = sat_cfg.get("satdump_path", "satdump")
    
    # Extract satellite name from wav filename (e.g., NOAA_15_20260712.wav -> NOAA_15)
    # This is a bit brittle, but we assume the stem starts with the satellite name
    stem = wav_path.stem
    
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        
        # Satdump command: satdump noaa_apt wav input.wav output_dir
        cmd = [satdump_path, "noaa_apt", "wav", str(wav_path), str(tmp_path)]
        
        logger.info(f"Decoding APT with SatDump: {wav_path.name}")
        logger.debug(f"satdump command: {' '.join(cmd)}")
        
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300, # Satdump might take a bit longer
            )
            
            if result.returncode != 0:
                logger.error(f"satdump failed (code {result.returncode}): {result.stderr}")
                return None
                
            # Now extract the keep_products
            keep = sat_cfg.get("keep_products", ["msa", "mcir"])
            ext = sat_cfg.get("image_format", "png")
            
            output_products = {}
            found_any = False
            
            # SatDump creates files like `[product_name].[ext]` or sometimes includes sat name.
            # Usually it generates `msa.png`, `mcir.png`, `1.png`, etc. in the output dir.
            for prod in keep:
                # SatDump is case-sensitive, usually outputs things like msa.png or MSA.png
                # Let's search for it case-insensitively
                matches = list(tmp_path.glob(f"*{prod}*.{ext}"))
                if not matches:
                    matches = list(tmp_path.glob(f"*{prod.upper()}*.{ext}"))
                    
                if matches:
                    src_file = matches[0] # Take the first match
                    # Destination name: original_stem_product.png
                    dst_name = f"{stem}_{prod}.{ext}"
                    dst_path = final_output_dir / dst_name
                    
                    shutil.copy2(src_file, dst_path)
                    output_products[prod] = dst_path
                    found_any = True
            
            if found_any:
                logger.info(f"SatDump decode success: extracted {list(output_products.keys())}")
                return output_products
            else:
                logger.warning("SatDump succeeded but no requested products were found in output.")
                return None
                
        except FileNotFoundError:
            logger.error(
                f"satdump not found at '{satdump_path}'. "
                "Install it via: scripts/install_deps.sh"
            )
            return None
        except subprocess.TimeoutExpired:
            logger.error("satdump timed out after 300 seconds")
            return None
