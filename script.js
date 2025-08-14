document.addEventListener('DOMContentLoaded', () => {
    const startInput = document.getElementById('startInput');
    const destinationInput = document.getElementById('destinationInput');
    const findRouteButton = document.getElementById('findRouteButton');
    const userLocationButton = document.getElementById('userLocationButton');
    const resultsDiv = document.getElementById('results');
    const mapDiv = document.getElementById('map');

    let map;
    let currentRoutePolyline = null;
    let currentHazardMarkers = [];
    let currentSatelliteLayer = null;

    const API_BASE_URL = 'https://satwatch-backend.onrender.com';

    function initializeMap() {
        map = L.map(mapDiv).setView([20.5937, 78.9629], 5); 
        L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
            attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
        }).addTo(map);
    }

    function setUIState(isAnalyzing) {
        if (isAnalyzing) {
            findRouteButton.textContent = 'Analyzing...';
            findRouteButton.disabled = true;
            findRouteButton.classList.add('pulse-animation');
            resultsDiv.innerHTML = `<p class="text-[#cfe0e0] italic">Fetching route and analyzing safety... this may take a moment.</p>`;
        } else {
            findRouteButton.textContent = 'Find Route';
            findRouteButton.disabled = false;
            findRouteButton.classList.remove('pulse-animation');
        }
    }

    function displayError(message) {
        resultsDiv.innerHTML = `<p class="text-[#F3D9A1] font-bold">${message}</p>`;
    }
    
    function clearMapLayers() {
        if (currentRoutePolyline) map.removeLayer(currentRoutePolyline);
        currentHazardMarkers.forEach(marker => map.removeLayer(marker));
        currentHazardMarkers = [];
        if (currentSatelliteLayer) map.removeLayer(currentSatelliteLayer);
    }

    const performRouteAnalysis = async (startQuery, endQuery) => {
        if (!endQuery) {
            displayError("Please enter a destination.");
            return;
        }

        setUIState(true);
        clearMapLayers();

        let apiUrl;
        if (typeof startQuery === 'object' && startQuery.lat && startQuery.lon) {
            apiUrl = `${API_BASE_URL}/api/route?start_lat=${startQuery.lat}&start_lon=${startQuery.lon}&end=${encodeURIComponent(endQuery)}`;
        } else {
            apiUrl = `${API_BASE_URL}/api/route?start=${encodeURIComponent(startQuery)}&end=${encodeURIComponent(endQuery)}`;
        }
        
        try {
            const response = await fetch(apiUrl);

            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.error || 'An unknown error occurred on the server.');
            }

            const data = await response.json();
            
            currentRoutePolyline = L.polyline(data.route, { color: '#b7c6c6', weight: 5 }).addTo(map);
            
            currentSatelliteLayer = L.tileLayer(data.satelliteUrl, {
                attribution: 'NASA GIBS',
                opacity: 0.8
            }).addTo(map);

            let hazardsHtml = '';
            let safetyAssessmentHtml = `<p class="text-green-300 italic mb-4">Route appears clear. Travel is advised.</p>`;

            if (data.hazards.length > 0) {
                safetyAssessmentHtml = `<p class="text-yellow-400 italic mb-4">CAUTION: Hazards detected. Review details and proceed with care.</p>`;
                hazardsHtml = `<div class="mt-4 p-4 bg-[#F3D9A1] bg-opacity-10 rounded-lg border border-[#F3D9A1]">
                                <h4 class="text-lg font-bold text-[#F3D9A1]">Detected Hazards:</h4>
                                <ul class="list-disc list-inside mt-2 space-y-1">${data.hazards.map(h => 
                                    `<li class="text-white"><strong>${h.location_name}:</strong> ${h.details}</li>`).join('')}</ul>
                               </div>`;
                
                data.hazards.forEach(hazard => {
                    const marker = L.circleMarker(hazard.coords, {
                        radius: 8, color: '#F3D9A1', fillColor: '#F3D9A1', fillOpacity: 0.5
                    }).addTo(map);
                    marker.bindPopup(`<b>ALERT:</b> ${hazard.details}`).openPopup();
                    currentHazardMarkers.push(marker);
                });
            }
            
            map.fitBounds(new L.LatLngBounds(data.route), { padding: [50, 50] });
            
            resultsDiv.innerHTML = `
                <h3 class="text-2xl font-bold text-[#b7c6c6] mb-2">Route Analysis</h3>
                <p class="mb-1"><strong>From:</strong> ${data.startName}</p>
                <p class="mb-4"><strong>To:</strong> ${data.endName}</p>
                <p class="text-xl font-bold mb-2">Safety Assessment:</p>
                ${safetyAssessmentHtml}
                ${hazardsHtml}
            `;

        } catch (error) {
            console.error('Frontend error:', error);
            const errorMessage = error.message.includes('Failed to fetch') 
                ? 'Error: Could not connect to the backend server. Please ensure app.py is running and accessible.'
                : error.message;
            displayError(errorMessage);
        } finally {
            setUIState(false);
        }
    };

    findRouteButton.addEventListener('click', () => {
        performRouteAnalysis(startInput.value, destinationInput.value);
    });

    userLocationButton.addEventListener('click', () => {
        userLocationButton.textContent = 'Getting Location...';
        userLocationButton.disabled = true;

        if (navigator.geolocation) {
            navigator.geolocation.getCurrentPosition(
                (position) => {
                    const { latitude, longitude } = position.coords;
                    startInput.value = `Your Location (${latitude.toFixed(2)}, ${longitude.toFixed(2)})`;
                    userLocationButton.textContent = 'Use My Location';
                    userLocationButton.disabled = false;
                    if (destinationInput.value) {
                       performRouteAnalysis({ lat: latitude, lon: longitude }, destinationInput.value);
                    }
                },
                (error) => {
                    displayError(`Geolocation failed: ${error.message}`);
                    userLocationButton.textContent = 'Use My Location';
                    userLocationButton.disabled = false;
                }
            );
        } else {
            displayError("Geolocation is not supported by this browser.");
            userLocationButton.textContent = 'Use My Location';
            userLocationButton.disabled = false;
        }
    });

    initializeMap();

});
