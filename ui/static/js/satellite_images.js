/**
 * satellite_images.js
 * Fetches satellite imagery metadata and handles multi-layer UI toggling.
 */

let allImages = [];
let currentImageSet = null;

async function initSatelliteImages() {
    try {
        const res = await fetch('/api/images');
        const data = await res.json();
        
        allImages = data.images || [];
        const selector = document.getElementById('pass-selector');
        
        if (allImages.length === 0) {
            return;
        }
        
        // Populate selector
        selector.innerHTML = '';
        allImages.forEach((img, idx) => {
            const opt = document.createElement('option');
            opt.value = idx;
            // img.id might be "NOAA 15_20260712_101500"
            const dateStr = new Date(img.captured_at).toLocaleString();
            opt.textContent = `${img.satellite_name} - ${dateStr}`;
            selector.appendChild(opt);
        });
        
        selector.addEventListener('change', (e) => {
            const idx = parseInt(e.target.value, 10);
            renderImageSet(allImages[idx]);
        });
        
        // Render the most recent by default
        renderImageSet(allImages[0]);
        
    } catch (e) {
        console.error("Failed to load satellite images", e);
    }
}

function renderImageSet(imgSet) {
    currentImageSet = imgSet;
    const imgEl = document.getElementById('satellite-image-display');
    const placeholder = document.getElementById('image-placeholder');
    const controls = document.getElementById('layer-controls');
    
    // Check if there are any products
    // We expect products to be in imgSet object except 'id', 'satellite_name', 'captured_at'
    
    const standardKeys = ['id', 'satellite_name', 'captured_at', 'thumb'];
    const layers = Object.keys(imgSet).filter(k => !standardKeys.includes(k));
    
    if (layers.length === 0) {
        imgEl.style.display = 'none';
        placeholder.style.display = 'block';
        controls.style.display = 'none';
        return;
    }
    
    placeholder.style.display = 'none';
    imgEl.style.display = 'inline-block';
    controls.style.display = 'flex';
    
    // Clear old buttons
    controls.innerHTML = '';
    
    // Pick default layer (prefer msa, then mcir, then first)
    let defaultLayer = layers.includes('msa') ? 'msa' : 
                       layers.includes('mcir') ? 'mcir' : layers[0];
                       
    // Create buttons for each layer
    layers.forEach(layer => {
        const btn = document.createElement('button');
        btn.textContent = layer.toUpperCase();
        btn.className = 'btn btn-sm';
        btn.style.padding = '4px 8px';
        btn.style.cursor = 'pointer';
        btn.style.background = layer === defaultLayer ? 'var(--color-info)' : '#444';
        btn.style.color = 'white';
        btn.style.border = 'none';
        btn.style.borderRadius = '4px';
        
        btn.onclick = () => {
            // Update image source
            const path = imgSet[layer];
            const filename = path.split('/').pop().split('\\').pop(); // extract filename from absolute path
            imgEl.src = `/api/images/${filename}`;
            
            // Update button styles
            Array.from(controls.children).forEach(c => c.style.background = '#444');
            btn.style.background = 'var(--color-info)';
        };
        
        controls.appendChild(btn);
    });
    
    // Load default layer
    const path = imgSet[defaultLayer];
    const filename = path.split('/').pop().split('\\').pop();
    imgEl.src = `/api/images/${filename}`;
}

// Hook into the main init process
if (typeof init === 'function') {
    const origInit = init;
    init = async function() {
        await origInit();
        await initSatelliteImages();
    }
} else {
    document.addEventListener('DOMContentLoaded', initSatelliteImages);
}
