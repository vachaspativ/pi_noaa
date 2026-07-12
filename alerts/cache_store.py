"""
SQLite backed cache store.
Saves alerts, passes, and image metadata for degraded (offline) mode operation.
"""
import sqlite3
import json
from pathlib import Path
from datetime import datetime, timezone, timedelta
from core.config_loader import get_config
from core.logger import get_logger

logger = get_logger(__name__)

_db_initialized = False


def get_db() -> sqlite3.Connection:
    """Get a database connection, initialize schema if needed."""
    global _db_initialized
    cfg = get_config()
    db_path = Path(cfg.offline_cache["db_path"])
    db_path.parent.mkdir(parents=True, exist_ok=True)
    
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    
    if not _db_initialized:
        _init_schema(conn)
        _db_initialized = True
        
    return conn


def _init_schema(conn: sqlite3.Connection) -> None:
    """Create tables if they don't exist."""
    cursor = conn.cursor()
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS alerts (
            id TEXT PRIMARY KEY,
            event TEXT,
            ui_level TEXT,
            source TEXT,
            effective TEXT,
            expires TEXT,
            payload_json TEXT,
            cached_at TEXT
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS passes (
            id TEXT PRIMARY KEY,
            satellite_name TEXT,
            aos TEXT,
            los TEXT,
            max_elevation REAL,
            payload_json TEXT,
            cached_at TEXT
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS images (
            id TEXT PRIMARY KEY,
            satellite_name TEXT,
            captured_at TEXT,
            payload_json TEXT,
            cached_at TEXT
        )
    """)
    
    conn.commit()


def save_alert(alert_data: dict) -> None:
    """Save or update an alert in the cache."""
    conn = get_db()
    cursor = conn.cursor()
    
    now = datetime.now(timezone.utc).isoformat()
    if isinstance(alert_data.get("effective"), datetime):
        alert_data["effective"] = alert_data["effective"].isoformat()
        
    if isinstance(alert_data.get("expires"), datetime):
        alert_data["expires"] = alert_data["expires"].isoformat()
        
    effective = alert_data.get("effective")
    expires = alert_data.get("expires")
    
    # We serialize datetime objects in payload_json to ISO strings
    
    cursor.execute("""
        INSERT OR REPLACE INTO alerts 
        (id, event, ui_level, source, effective, expires, payload_json, cached_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        alert_data["id"],
        alert_data["event"],
        alert_data["ui_level"],
        alert_data.get("source", "unknown"),
        effective,
        expires,
        json.dumps(alert_data),
        now
    ))
    
    conn.commit()
    conn.close()
    
    _cleanup_old_alerts()


def load_cached_alerts() -> list[dict]:
    """Load all alerts from cache that are not considered hopelessly stale."""
    cfg = get_config()
    max_age_hours = cfg.offline_cache.get("max_stale_alert_age_hours", 48)
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=max_age_hours)).isoformat()
    
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT payload_json FROM alerts 
        WHERE cached_at > ?
        ORDER BY cached_at DESC
    """, (cutoff,))
    
    results = [json.loads(row["payload_json"]) for row in cursor.fetchall()]
    conn.close()
    return results


def save_pass(pass_data: dict) -> None:
    conn = get_db()
    cursor = conn.cursor()
    now = datetime.now(timezone.utc).isoformat()
    
    # Generate an ID if needed
    pass_id = f"{pass_data['satellite_name']}_{pass_data['aos']}"
    
    cursor.execute("""
        INSERT OR REPLACE INTO passes 
        (id, satellite_name, aos, los, max_elevation, payload_json, cached_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        pass_id,
        pass_data["satellite_name"],
        pass_data["aos"],
        pass_data["los"],
        pass_data["max_elevation_deg"],
        json.dumps(pass_data),
        now
    ))
    conn.commit()
    conn.close()


def load_cached_passes() -> list[dict]:
    conn = get_db()
    cursor = conn.cursor()
    now = datetime.now(timezone.utc).isoformat()
    
    # Only load passes where LOS > now
    cursor.execute("""
        SELECT payload_json FROM passes 
        WHERE los > ?
        ORDER BY aos ASC
    """, (now,))
    
    results = [json.loads(row["payload_json"]) for row in cursor.fetchall()]
    conn.close()
    return results


def _cleanup_old_alerts() -> None:
    """Rolling window cleanup based on config limits."""
    cfg = get_config()
    max_alerts = cfg.offline_cache.get("max_cached_alerts", 200)
    
    conn = get_db()
    cursor = conn.cursor()
    
    # Delete where ID is not in the top N newest alerts
    cursor.execute(f"""
        DELETE FROM alerts WHERE id NOT IN (
            SELECT id FROM alerts ORDER BY cached_at DESC LIMIT {max_alerts}
        )
    """)
    
    conn.commit()
    conn.close()


def save_image(image_data: dict) -> None:
    """Save an image record containing multiple layers."""
    conn = get_db()
    cursor = conn.cursor()
    now = datetime.now(timezone.utc).isoformat()
    
    # Needs a unique ID per pass, e.g. NOAA15_20260712_101500
    img_id = image_data.get("id", f"{image_data.get('satellite_name')}_{image_data.get('captured_at')}")
    
    # If the table still has old schema (missing payload_json), this will fail.
    # To be perfectly safe, we try dropping it if it's the old schema, 
    # but since it was never used before, we assume fresh DB or we just catch it.
    try:
        cursor.execute("""
            INSERT OR REPLACE INTO images 
            (id, satellite_name, captured_at, payload_json, cached_at)
            VALUES (?, ?, ?, ?, ?)
        """, (
            img_id,
            image_data.get("satellite_name"),
            image_data.get("captured_at"),
            json.dumps(image_data),
            now
        ))
        conn.commit()
    except sqlite3.OperationalError:
        # Schema mismatch, drop and recreate
        cursor.execute("DROP TABLE IF EXISTS images")
        _init_schema(conn)
        cursor.execute("""
            INSERT OR REPLACE INTO images 
            (id, satellite_name, captured_at, payload_json, cached_at)
            VALUES (?, ?, ?, ?, ?)
        """, (
            img_id,
            image_data.get("satellite_name"),
            image_data.get("captured_at"),
            json.dumps(image_data),
            now
        ))
        conn.commit()
    finally:
        conn.close()


def load_cached_images() -> list[dict]:
    """Load all cached images, returning their full payloads (layers)."""
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT payload_json FROM images 
            ORDER BY captured_at DESC
        """)
        
        results = [json.loads(row["payload_json"]) for row in cursor.fetchall()]
        conn.close()
        return results
    except sqlite3.OperationalError:
        # If table doesn't exist or schema is old
        return []
