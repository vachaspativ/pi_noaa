/**
 * Next Satellite Pass Countdown Clock
 */

let nextPass = null;
let clockInterval = null;

async function initPassClock() {
    await fetchNextPass();
    // Refresh the pass API every 5 mins just in case
    setInterval(fetchNextPass, 300000); 
    
    // Start ticking the clock locally every second
    if (clockInterval) clearInterval(clockInterval);
    clockInterval = setInterval(updateClockUI, 1000);
}

async function fetchNextPass() {
    try {
        const res = await fetch('/api/passes/next');
        const data = await res.json();
        nextPass = data.pass;
        updateClockUI();
    } catch (e) {
        console.error("Failed to fetch next pass", e);
    }
}

function updateClockUI() {
    const timeEl = document.querySelector('.time-large');
    const detailsEl = document.querySelector('.pass-details');
    
    if (!timeEl || !detailsEl) return;
    
    if (!nextPass) {
        timeEl.textContent = "--:--:--";
        detailsEl.textContent = "No upcoming passes";
        return;
    }
    
    const now = new Date();
    const aos = new Date(nextPass.aos);
    const los = new Date(nextPass.los);
    
    if (now >= aos && now <= los) {
        // Active pass
        timeEl.textContent = "RECORDING";
        timeEl.style.color = "var(--color-critical)";
        
        const duration = (los - aos) / 1000;
        const elapsed = (now - aos) / 1000;
        const percent = Math.round((elapsed / duration) * 100);
        
        detailsEl.innerHTML = `
            <div>${nextPass.satellite_name} @ ${(nextPass.frequency_hz/1e6).toFixed(4)} MHz</div>
            <div style="width:100%; height:4px; background:#333; margin-top:5px;">
                <div style="width:${percent}%; height:100%; background:var(--color-critical);"></div>
            </div>
        `;
    } else if (now > los) {
        // Pass ended, wait for next fetch
        timeEl.textContent = "PROCESSING";
        timeEl.style.color = "var(--accent)";
        detailsEl.textContent = "Decoding image...";
        
        // Force a refresh soon
        setTimeout(fetchNextPass, 5000);
    } else {
        // Countdown
        const diffSeconds = Math.floor((aos - now) / 1000);
        
        const h = Math.floor(diffSeconds / 3600).toString().padStart(2, '0');
        const m = Math.floor((diffSeconds % 3600) / 60).toString().padStart(2, '0');
        const s = (diffSeconds % 60).toString().padStart(2, '0');
        
        timeEl.textContent = `${h}:${m}:${s}`;
        timeEl.style.color = "var(--accent)";
        
        detailsEl.innerHTML = `
            ${nextPass.satellite_name}<br>
            Max El: ${Math.round(nextPass.max_elevation_deg)}°
        `;
    }
}
