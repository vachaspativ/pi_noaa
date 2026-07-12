/**
 * Leaflet map implementation for pi_noaa.
 */

let map;
let alertLayer;
let featureMap = {}; // mapping alert.id -> Leaflet Layer

function initMap() {
    // Center fallback (e.g. geographic center of US)
    const lat = mapConfig.initial_center_lat || 39.8283;
    const lon = mapConfig.initial_center_lon || -98.5795;
    
    map = L.map('alert-map', {
        center: [lat, lon],
        zoom: mapConfig.initial_zoom || 5,
        minZoom: mapConfig.min_zoom || 3,
        maxZoom: mapConfig.max_zoom || 12,
        zoomControl: true
    });
    
    L.tileLayer(mapConfig.tile_url, {
        attribution: '© OpenStreetMap contributors',
        maxZoom: mapConfig.max_zoom || 12
    }).addTo(map);
    
    alertLayer = L.layerGroup().addTo(map);
}

function renderAlertPolygons(alerts) {
    if (!map) return;
    
    alertLayer.clearLayers();
    featureMap = {};
    const bounds = [];
    
    alerts.forEach(alert => {
        let geojson = alert.geometry;
        
        // If SAME RF alert (no geometry), try to look up county polygons
        if (!geojson && alert.source === 'same_rf' && typeof getCountyPolygons === 'function') {
            // Extract FIPS from area_desc (e.g. "2 FIPS areas: 017031,017032")
            // This is a bit hacky, a better way would be returning the raw fips_codes array in the UnifiedAlert
            // For now, let's assume we can parse it or getCountyPolygons handles it
            geojson = getCountyPolygons(alert); 
        }
        
        if (!geojson) return;
        
        const fillOpacity = mapConfig.alert_fill_opacity[alert.ui_level] || 0.2;
        const color = LEVEL_COLORS[alert.ui_level] || '#3b82f6';
        
        const layer = L.geoJSON(geojson, {
            style: {
                fillColor: color,
                fillOpacity: fillOpacity,
                color: color, 
                weight: mapConfig.alert_stroke_width_px || 2,
                opacity: mapConfig.alert_stroke_opacity || 0.85
            }
        });
        
        // Popup
        layer.bindPopup(buildAlertPopup(alert));
        
        // Animation
        if (alert.ui_level === 'critical' && mapConfig.animate_critical_polygons) {
            layer.eachLayer(l => {
                if (l.getElement) {
                    const el = l.getElement();
                    if (el) el.classList.add('pulse-polygon');
                }
            });
            // We also need to re-apply animation on zoom/pan because Leaflet recreates SVG elements
            map.on('zoomend moveend', () => {
                layer.eachLayer(l => {
                    if (l.getElement) {
                        const el = l.getElement();
                        if (el) el.classList.add('pulse-polygon');
                    }
                });
            });
        }
        
        layer.addTo(alertLayer);
        featureMap[alert.id] = layer;
        bounds.push(layer.getBounds());
    });
    
    // Auto fit
    if (mapConfig.auto_fit_alerts_on_load && bounds.length > 0) {
        const allBounds = bounds.reduce((a, b) => a.extend(b));
        map.fitBounds(allBounds, { 
            padding: [mapConfig.fit_bounds_padding || 40, mapConfig.fit_bounds_padding || 40],
            maxZoom: 8
        });
        // Only auto-fit on first load
        mapConfig.auto_fit_alerts_on_load = false;
    }
}

function buildAlertPopup(alert) {
    const color = LEVEL_COLORS[alert.ui_level];
    return `
        <div style="min-width: 200px;">
            <h3 style="margin-top:0; color:${color}; border-bottom:1px solid #ccc; padding-bottom:5px;">
                ${alert.event}
            </h3>
            <p><strong>Source:</strong> ${alert.source}</p>
            <p><strong>Area:</strong> ${alert.area_desc}</p>
            <p><strong>Expires:</strong> ${new Date(alert.expires).toLocaleString()}</p>
            <div style="max-height:150px; overflow-y:auto; margin-top:10px; font-size:0.9em; color:#555;">
                ${alert.description}
            </div>
        </div>
    `;
}

window.flyToAlert = function(alertId) {
    if (!map) return;
    const layer = featureMap[alertId];
    if (layer) {
        map.flyToBounds(layer.getBounds(), { duration: 1.5, maxZoom: 8 });
        layer.openPopup();
    }
};
