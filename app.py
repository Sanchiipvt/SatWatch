import os
import datetime
import math
import xml.etree.ElementTree as ET
from flask import Flask, request, jsonify
from flask_cors import CORS
from geopy.geocoders import Nominatim
import requests

# Initialize the Flask app and enable Cross-Origin Resource Sharing (CORS)
app = Flask(__name__)
CORS(app)

# Initialize the geolocator with a custom user agent
geolocator = Nominatim(user_agent="satwatch-route-analyzer/1.0")
# Define standard headers for external API requests
HEADERS = {'User-Agent': 'satwatch-route-analyzer/1.0'}

# Securely get the OpenWeatherMap API key from the server's environment variables.
OPENWEATHERMAP_API_KEY = os.environ.get('OPENWEATHERMAP_API_KEY')

# A dictionary of predefined local advisories for high-risk areas
MOCK_LOCAL_ADVISORIES = {
    "Kufri": {
        'coords': [31.1005, 77.2658],
        'details': 'Heavy Snowfall Warning: Kufri and surrounding areas experience heavy snow, leading to frequent road blockages. Check road status before travel. Only 4x4 vehicles with snow chains are recommended.',
        'location_name': 'Kufri, Himachal Pradesh'
    },
    "Shimla": {
        'coords': [31.1048, 77.1734],
        'details': 'Road Advisory: Heavy snowfall in winter. Main roads can be treacherous. During monsoon, risk of landslides is high. Drive with caution.',
        'location_name': 'Shimla, Himachal Pradesh'
    },
    "Himachal Pradesh": {
        'coords': [31.7104, 76.9325],
        'details': 'General Advisory for Himachal: The state is prone to landslides and flash floods during monsoon (July-Sept) and heavy snowfall in winter (Dec-Feb). Always check local weather and road conditions.',
        'location_name': 'Himachal Pradesh'
    },
    "Jammu": {
        'coords': [32.7266, 74.8570],
        'details': 'Landslide & Security Advisory: The Jammu-Srinagar highway (NH44) is prone to frequent closures due to landslides, especially near Ramban. Follow all security advisories and travel only during daylight hours.',
        'location_name': 'Jammu Region, J&K'
    },
    "Ladakh": {
        'coords': [34.1526, 77.5771],
        'details': 'High-Altitude & Weather Advisory: Risk of acute mountain sickness. Roads like Zoji La & Rohtang Pass are closed in winter. Expect extreme cold and limited facilities. Acclimatize properly before travel.',
        'location_name': 'Ladakh Union Territory'
    },
    "Kedarnath": {
        'coords': [30.7352, 79.0669],
        'details': 'Mountain Route Advisory: Seasonal road closures and heavy landslides reported. Travel is **NOT ADVISED** at this time.',
        'location_name': 'Rudraprayag district, Uttarakhand'
    },
    "Joshimath": {
        'coords': [30.5656, 79.5645],
        'details': 'Severe Land Subsidence Warning: This area is experiencing significant land sinking. Many structures are unsafe. Non-essential travel is strongly discouraged.',
        'location_name': 'Joshimath, Chamoli, Uttarakhand'
    },
    "Assam": {
        'coords': [26.1445, 91.7362],
        'details': 'Monsoon Flood Alert: The Brahmaputra river regularly causes widespread flooding during the monsoon season (June-September). Check current conditions before travel.',
        'location_name': 'Assam River Plains'
    },
    "Bihar": {
        'coords': [25.5941, 85.1376],
        'details': 'Severe Flood Risk: The Kosi and Ganges rivers can cause extensive and rapid flooding during monsoon season. Travel to northern districts may be disrupted.',
        'location_name': 'Northern Bihar'
    },
    "Kerala": {
        'coords': [10.8505, 76.2711],
        'details': 'Flood Warning: Monsoon season has caused local flooding. Some low-lying areas are impassable. Check local reports.',
        'location_name': 'Kerala, India'
    },
    "Mumbai": {
        'coords': [19.0760, 72.8777],
        'details': 'Cyclone Advisory: Heavy winds and storm surge expected. Travel to coastal areas is not advised.',
        'location_name': 'Mumbai Coastline'
    },
    "Odisha": {
        'coords': [19.8135, 85.8312],
        'details': 'Cyclone Alert Zone: This coastal region is highly susceptible to cyclones, especially from May-June and October-November. Monitor weather reports for cyclone warnings.',
        'location_name': 'Puri, Odisha Coast'
    },
    "Sundarbans": {
        'coords': [21.9497, 88.8533],
        'details': 'Storm Surge & Cyclone Warning: This low-lying delta region is extremely vulnerable to storm surges from cyclones in the Bay of Bengal. Follow all official advisories.',
        'location_name': 'Sundarbans Delta, West Bengal'
    }
}


def haversine(lat1, lon1, lat2, lon2):
    """Calculates the distance between two geographical points in kilometers."""
    R = 6371
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c

def fetch_local_advisories(end_loc_name):
    """Checks if the destination name matches a predefined high-risk area."""
    local_hazards = []
    for loc_name, advisory in MOCK_LOCAL_ADVISORIES.items():
        if loc_name.lower() in end_loc_name.lower():
            local_hazards.append(advisory)
            break
    return local_hazards

def fetch_and_check_gdacs_alerts(route_points):
    """Fetches and parses real-time global disaster alerts from GDACS."""
    detected_hazards = []
    gdacs_url = "https://www.gdacs.org/rss.aspx?format=geo&alertlevel=Orange,Red"
    try:
        response = requests.get(gdacs_url, timeout=10, headers=HEADERS)
        response.raise_for_status()
        root = ET.fromstring(response.content)
        ns = {'georss': 'http://www.georss.org/georss'}

        for item in root.findall('.//item'):
            title = item.find('title').text
            point_elem = item.find('georss:point', ns)
            if point_elem is not None:
                lat, lon = map(float, point_elem.text.split())
                for route_point in route_points:
                    if haversine(route_point[0], route_point[1], lat, lon) < 50:
                        detected_hazards.append({'coords': [lat, lon], 'details': title, 'location_name': "Near your route"})
                        break
    except Exception as e:
        print(f"Error fetching/parsing GDACS data: {e}")
    return detected_hazards

def fetch_weather_alerts(route_points):
    """Fetches real-time weather alerts from OpenWeatherMap for key points on the route."""
    if not OPENWEATHERMAP_API_KEY:
        print("Skipping weather check: OpenWeatherMap API key not set.")
        return []

    weather_hazards = []
    points_to_check = [route_points[0], route_points[len(route_points)//2], route_points[-1]]
    
    for point in points_to_check:
        lat, lon = point
        weather_url = f"https://api.openweathermap.org/data/2.5/weather?lat={lat}&lon={lon}&appid={OPENWEATHERMAP_API_KEY}"
        try:
            response = requests.get(weather_url, timeout=5)
            response.raise_for_status()
            data = response.json()
            if data.get('weather') and 200 <= data['weather'][0]['id'] < 800:
                weather_hazards.append({
                    'coords': point,
                    'details': f"Weather Alert: {data['weather'][0]['description']}",
                    'location_name': data.get('name', "Along your route")
                })
        except Exception as e:
            print(f"Error fetching OpenWeatherMap data: {e}")
    return weather_hazards

def get_satellite_url(hazard_type=None):
    """Generates a dynamic NASA GIBS satellite imagery URL based on hazard type."""
    date_today = datetime.date.today().isoformat()
    if hazard_type and ('fire' in hazard_type.lower() or 'wildfire' in hazard_type.lower()):
        return f"https://gibs.earthdata.nasa.gov/wmts/epsg4326/best/VIIRS_SNPP_Thermal_Anomalies_375m_All/default/{date_today}/250m/{{z}}/{{y}}/{{x}}.png"
    return f"https://gibs.earthdata.nasa.gov/wmts/epsg4326/best/MODIS_Terra_CorrectedReflectance_TrueColor/default/{date_today}/250m/{{z}}/{{y}}/{{x}}.jpg"

@app.route('/api/route', methods=['GET'])
def analyze_route():
    """Main API endpoint to analyze a route and return hazards."""
    start_loc_name = request.args.get('start', '')
    end_loc_name = request.args.get('end', '')
    start_lat = request.args.get('start_lat')
    start_lon = request.args.get('start_lon')

    try:
        if start_loc_name:
            start_loc = geolocator.geocode(start_loc_name)
            if not start_loc: return jsonify({'error': 'Could not find start location'}), 404
            start_coords = [start_loc.longitude, start_loc.latitude]
            start_name = start_loc.address
        elif start_lat and start_lon:
            start_coords = [float(start_lon), float(start_lat)]
            start_name = "Your Current Location"
        else:
            return jsonify({'error': 'Start location not provided'}), 400

        end_loc = geolocator.geocode(end_loc_name)
        if not end_loc: return jsonify({'error': 'Could not find destination'}), 404
        end_coords = [end_loc.longitude, end_loc.latitude]
        end_name = end_loc.address
    except Exception as e:
        return jsonify({'error': f'Geocoding error: {str(e)}'}), 500

    osrm_url = f"http://router.project-osrm.org/route/v1/driving/{start_coords[0]},{start_coords[1]};{end_coords[0]},{end_coords[1]}?overview=full&geometries=geojson"
    try:
        osrm_response = requests.get(osrm_url)
        osrm_response.raise_for_status()
        osrm_data = osrm_response.json()
    except Exception as e:
        return jsonify({'error': 'Could not fetch route from routing service.'}), 500
    
    if 'routes' not in osrm_data or not osrm_data['routes']:
        return jsonify({'error': 'Could not find a route between locations'}), 404

    route_points = [[p[1], p[0]] for p in osrm_data['routes'][0]['geometry']['coordinates']]

    local_hazards = fetch_local_advisories(end_name)
    gdacs_hazards = fetch_and_check_gdacs_alerts(route_points)
    weather_hazards = fetch_weather_alerts(route_points)
    all_hazards = local_hazards + gdacs_hazards + weather_hazards
    
    satellite_url = get_satellite_url(all_hazards[0]['details'] if all_hazards else None)

    return jsonify({
        'startName': start_name,
        'endName': end_name,
        'route': route_points,
        'hazards': all_hazards,
        'satelliteUrl': satellite_url
    })
