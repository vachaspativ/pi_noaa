/**
 * Main dashboard orchestration script.
 * Initializes Socket.IO and sets up basic status handlers.
 */

const socket = io();

const LEVEL_COLORS = {
    "critical": "var(--color-critical)",
    "high": "var(--color-high)",
    "moderate": "var(--color-moderate)",
    "info": "var(--color-info)"
};

// Global state
let currentAlerts = [];
let mapConfig = {};

async function init() {
    // 1. Fetch config for map
    const res = await fetch('/api/config/map');
    mapConfig = await res.json();
    
    // 2. Init modules (they attach their own socket listeners)
    if (typeof initMap === 'function') initMap();
    if (typeof initPassClock === 'function') initPassClock();
    
    // 3. Fetch initial alerts
    const alertsRes = await fetch('/api/alerts');
    const alertsData = await alertsRes.json();
    currentAlerts = alertsData.alerts || [];
    
    updateAlertUI();
    
    // 4. Fetch initial status
    fetchStatus();
    setInterval(fetchStatus, 30000);
}

function updateAlertUI() {
    if (typeof renderAlertPolygons === 'function') {
        renderAlertPolygons(currentAlerts);
    }
    if (typeof updateAlertBanner === 'function') {
        updateAlertBanner(currentAlerts);
    }
    updateAlertTable(currentAlerts);
}

function updateAlertTable(alerts) {
    const tbody = document.querySelector('#alerts-table tbody');
    if (!tbody) return;
    
    tbody.innerHTML = '';
    
    alerts.forEach(alert => {
        const tr = document.createElement('tr');
        const color = LEVEL_COLORS[alert.ui_level];
        
        tr.innerHTML = `
            <td><span class="badge" style="background-color: ${color}">${alert.severity || alert.ui_level}</span></td>
            <td>${alert.event}</td>
            <td><span class="badge" style="background-color: #2d2d3f">${alert.source}</span></td>
        `;
        
        // Click row to fly to map polygon
        tr.style.cursor = 'pointer';
        tr.onclick = () => {
            if (typeof window.flyToAlert === 'function') {
                window.flyToAlert(alert.id);
            }
        };
        
        tbody.appendChild(tr);
    });
}

async function fetchStatus() {
    try {
        const res = await fetch('/api/status');
        const data = await res.json();
        
        document.getElementById('status-mode').textContent = data.mode.toUpperCase();
        document.getElementById('status-sdr').textContent = data.sdr.present ? 
            (data.sdr.recording ? 'RECORDING' : 'READY') : 'DISCONNECTED';
            
        const tleEl = document.getElementById('status-tle');
        if (data.tle.usable) {
            tleEl.textContent = `${data.tle.age_hours}h old (OK)`;
            tleEl.style.color = 'var(--text-main)';
        } else {
            tleEl.textContent = `STALE (${data.tle.message})`;
            tleEl.style.color = 'var(--color-high)';
        }
        
    } catch (e) {
        console.error("Failed to fetch status", e);
    }
}

// Socket.IO Handlers
socket.on('connect', () => {
    console.log('Connected to server');
});

socket.on('new_alert', (alert) => {
    console.log('New alert received:', alert);
    // Remove if already exists (dedup logic)
    currentAlerts = currentAlerts.filter(a => a.id !== alert.id);
    currentAlerts.push(alert);
    // Sort again
    currentAlerts.sort((a, b) => new Date(a.expires) - new Date(b.expires));
    
    updateAlertUI();
});

socket.on('alerts_update', (alerts) => {
    currentAlerts = alerts;
    updateAlertUI();
});

socket.on('mode_change', (mode) => {
    if (typeof handleModeChange === 'function') {
        handleModeChange(mode);
    }
    fetchStatus();
});

// Start
document.addEventListener('DOMContentLoaded', init);
