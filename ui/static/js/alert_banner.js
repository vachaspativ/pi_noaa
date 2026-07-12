/**
 * Controls the horizontal scrolling ticker banner.
 */

function updateAlertBanner(alerts) {
    const banner = document.getElementById('alert-banner');
    const ticker = document.getElementById('alert-ticker');
    
    if (!banner || !ticker) return;
    
    if (alerts.length === 0) {
        banner.classList.add('hidden');
        return;
    }
    
    banner.classList.remove('hidden');
    ticker.innerHTML = '';
    
    // Sort critical first
    const sorted = [...alerts].sort((a, b) => {
        const weightA = getWeight(a.ui_level);
        const weightB = getWeight(b.ui_level);
        return weightA - weightB;
    });
    
    sorted.forEach(alert => {
        const item = document.createElement('div');
        item.className = 'ticker-item';
        
        // Critical alerts pulse
        if (alert.ui_level === 'critical') {
            item.style.animation = 'pulse-opacity 2s infinite';
        }
        
        const color = LEVEL_COLORS[alert.ui_level];
        
        item.innerHTML = `
            <span style="color: ${color}; font-weight: bold;">[${alert.source}]</span> 
            <span style="color: white; font-weight: bold; margin-right: 10px;">${alert.event}</span>
            <span style="color: #ccc;">${alert.area_desc}</span>
        `;
        
        item.style.cursor = 'pointer';
        item.onclick = () => {
            if (typeof window.flyToAlert === 'function') {
                window.flyToAlert(alert.id);
            }
        };
        
        ticker.appendChild(item);
    });
}

function getWeight(level) {
    switch(level) {
        case 'critical': return 0;
        case 'high': return 1;
        case 'moderate': return 2;
        default: return 3;
    }
}
