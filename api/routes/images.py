"""
API routes for satellite images.
"""
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pathlib import Path
from alerts.cache_store import load_cached_images
from core.config_loader import get_config

router = APIRouter(tags=["images"])


@router.get("/images")
async def list_images():
    """List available decoded images (metadata)."""
    try:
        images = load_cached_images()
        return {"images": images}
    except Exception as e:
        return {"error": str(e), "images": []}


@router.get("/images/{filename}")
async def get_image(filename: str):
    """Serve full-size image file."""
    cfg = get_config()
    img_dir = Path(cfg.image["output_dir"])
    
    # Simple security check to prevent path traversal
    if ".." in filename or "/" in filename or "\\" in filename:
        raise HTTPException(status_code=400, detail="Invalid filename")
        
    img_path = img_dir / filename
    
    if not img_path.exists() or not img_path.is_file():
        raise HTTPException(status_code=404, detail="Image not found")
        
    return FileResponse(img_path)


@router.get("/images/{filename}/thumbnail")
async def get_image_thumbnail(filename: str):
    """Serve image thumbnail."""
    cfg = get_config()
    img_dir = Path(cfg.image["output_dir"])
    
    if ".." in filename or "/" in filename or "\\" in filename:
        raise HTTPException(status_code=400, detail="Invalid filename")
        
    # Construct expected thumbnail filename
    # e.g. from NOAA_15_20231010_120000.png to NOAA_15_20231010_120000_thumb.png
    base = Path(filename).stem
    ext = Path(filename).suffix
    
    # If the requested filename already has _thumb, just serve it
    if base.endswith("_thumb"):
        thumb_name = filename
    else:
        thumb_name = f"{base}_thumb{ext}"
        
    thumb_path = img_dir / thumb_name
    
    if not thumb_path.exists() or not thumb_path.is_file():
        # Fall back to original image if thumbnail doesn't exist
        orig_path = img_dir / filename
        if orig_path.exists() and orig_path.is_file():
            return FileResponse(orig_path)
            
        raise HTTPException(status_code=404, detail="Thumbnail not found")
        
    return FileResponse(thumb_path)
