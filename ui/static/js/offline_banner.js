/**
 * Controls the top-level connectivity status banner.
 */

function handleModeChange(mode) {
    const banner = document.getElementById('offline-banner');
    if (!banner) return;
    
    switch(mode.toLowerCase()) {
        case 'dual':
            banner.classList.add('hidden');
            break;
            
        case 'sdr_offline':
            banner.classList.remove('hidden');
            banner.style.backgroundColor = 'var(--color-info)';
            banner.innerHTML = '📡 <strong>SDR Offline Mode:</strong> Internet unreachable. Alerts sourced from 162 MHz WX Radio.';
            break;
            
        case 'api_only':
            banner.classList.remove('hidden');
            banner.style.backgroundColor = 'var(--color-moderate)';
            banner.innerHTML = '⚠ <strong>API Only Mode:</strong> SDR hardware not detected. Monitoring NWS via internet only.';
            break;
            
        case 'degraded':
            banner.classList.remove('hidden');
            banner.style.backgroundColor = 'var(--color-critical)';
            banner.innerHTML = '🔴 <strong>Fully Offline (Degraded):</strong> No internet and no SDR. Showing stale cached data.';
            break;
            
        default:
            banner.classList.add('hidden');
    }
}
