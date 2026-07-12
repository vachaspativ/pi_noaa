/**
 * Handles offline lookup of county polygons from bundled GeoJSON
 * for SAME RF alerts (which only provide FIPS codes).
 */

let countyGeoJSON = null;
let isLoadingCounties = false;

// We try to load this in the background once so it's ready if a SAME alert hits
async function loadCountyData() {
    if (countyGeoJSON || isLoadingCounties) return;
    
    isLoadingCounties = true;
    try {
        // This file is served statically
        const res = await fetch('/static/data/geo/us_counties_simplified.geojson');
        if (res.ok) {
            countyGeoJSON = await res.json();
            console.log("Offline county polygons loaded.");
        }
    } catch (e) {
        console.error("Failed to load county GeoJSON", e);
    }
    isLoadingCounties = false;
}

// Call on startup
document.addEventListener('DOMContentLoaded', loadCountyData);

/**
 * Given a SAMEAlert with a list of FIPS codes, returns a GeoJSON FeatureCollection
 * of those matching counties so Leaflet can draw them.
 */
function getCountyPolygons(alert) {
    if (!countyGeoJSON || !countyGeoJSON.features) {
        console.warn("County GeoJSON not loaded yet. Cannot draw SAME polygons.");
        return null;
    }
    
    // Fallback if the FIPS string isn't an array yet (depends on how alert merger sends it)
    let fipsList = [];
    if (alert.area_desc && alert.area_desc.includes("FIPS")) {
        // e.g. "2 FIPS areas: 017031,017032"
        const parts = alert.area_desc.split(":");
        if (parts.length > 1) {
            fipsList = parts[1].split(",").map(s => s.trim());
        }
    } else if (alert.fips_codes) {
        fipsList = alert.fips_codes;
    }
    
    if (fipsList.length === 0) return null;
    
    const matchedFeatures = countyGeoJSON.features.filter(f => {
        const featureFips = f.properties.GEOID;
        return fipsList.includes(featureFips);
    });
    
    if (matchedFeatures.length === 0) return null;
    
    return {
        type: "FeatureCollection",
        features: matchedFeatures
    };
}
