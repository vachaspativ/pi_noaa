"""
API routes for weather alerts.
"""
from fastapi import APIRouter, HTTPException
from alerts.alert_merger import merge_alerts
from alerts.cache_store import load_cached_alerts
from core.connectivity import is_internet_available
# In a real app we'd inject these dependencies, but for now we'll rely on 
# a global state or simple import. We will need access to the live monitors.

router = APIRouter(tags=["alerts"])

# We'll define a way to pass monitors to this router later,
# for now we'll use placeholder or module-level variables.
# In a full implementation, these would be accessible via request.app.state
# We will assume they are attached to the app state in server.py

@router.get("/alerts")
async def get_all_alerts(request):
    """Get all active alerts, merged and prioritized."""
    try:
        app_state = request.app.state
        
        nws_alerts = []
        if hasattr(app_state, "nws_monitor") and app_state.nws_monitor:
            nws_alerts = app_state.nws_monitor.active_alerts
            
        same_alerts = []
        # In this implementation, same_alerts are event-driven. 
        # For an API list, we'd need the SAME monitor to keep track of active ones.
        # Since SAME alerts expire, we'd filter by expiration.
        # For brevity in phase 1, we assume it's attached if available.
        if hasattr(app_state, "same_active_alerts"):
            same_alerts = app_state.same_active_alerts
            
        cached_alerts = load_cached_alerts()
        internet = is_internet_available()
        
        merged = merge_alerts(nws_alerts, same_alerts, cached_alerts, internet)
        
        return {"alerts": [a.__dict__ for a in merged]}
        
    except Exception as e:
        return {"error": str(e), "alerts": []}
