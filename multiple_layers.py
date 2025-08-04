
# app.py
# A Python web server that discovers multiple shapefiles in a 'data' directory
# and serves them as GeoJSON.
#
# --- Dependencies ---
# You'll need to install Flask, Flask-CORS, and GeoPandas:
# pip install Flask Flask-CORS geopandas
#
# --- Project Structure ---
# /your_project_folder
# |-- app.py (this file)
# |-- /templates
#     |-- index.html (the frontend file)
# |-- /data
#     |-- dataset_one.shp
#     |-- dataset_one.shx
#     |-- ...
#     |-- dataset_two.shp
#     |-- dataset_two.shx
#     |-- ... (and so on for all your shapefiles)
#
# --- Running the App ---
# 1. Place all your shapefile datasets into the 'data' directory.
# 2. Open your terminal, navigate to 'your_project_folder', and run:
#    python app.py
# 3. Open your web browser and go to http://127.0.0.1:5000

from flask import Flask, jsonify, render_template
from flask_cors import CORS
import geopandas as gpd
import os
import json
import traceback

# --- Configuration ---
SHAPEFILE_FOLDER = 'data'

FIELD_MAPPING = {
    'Ohio_County_Boundaries': {
        'name': 'County Name',
        'county_sea': 'County Seat'
    },
    'Ohio_Senate_Districts_2024_to_2032': {
        'district': 'Senate District #'
    },
    'Ohio_House_Districts_2024_to__2032': {
        'district': 'House District #'
    },
    'Ohio_Municipal_Boundaries': {
        'municipali': 'Municipality Name',
        'sq_mi': 'Area (square miles)'
    },
    'Ohio_Township_Boundaries': {
        'twp_name': 'Township Name',
        'sqmi_area': 'Area (square miles)'
    }
    # Add entries for your other shapefiles here.
    # 'Your_Layer_Name': { ... }
}

# --- Flask App Initialization ---
app = Flask(__name__, template_folder='templates')
CORS(app)

# --- Data Loading and Caching ---
# We use a dictionary to cache loaded GeoJSON data. The key will be the
# shapefile's base name (e.g., 'ne_110m_admin_0_countries') and the value
# will be the GeoJSON string. This avoids re-reading files from disk.
geodata_cache = {}

def discover_shapefiles(directory):
    """Scans a directory for .shp files and returns their base names."""
    shapefiles = []
    if not os.path.isdir(directory):
        print(f"Warning: Data directory '{directory}' not found.")
        return shapefiles

    for filename in os.listdir(directory):
        if filename.endswith('.shp'):
            # Return the name without the .shp extension
            shapefiles.append(os.path.splitext(filename)[0])
    print(f"Discovered shapefiles: {shapefiles}")
    return sorted(shapefiles) # Sort them alphabetically

# Discover available layers on startup
AVAILABLE_LAYERS = discover_shapefiles(SHAPEFILE_FOLDER)


for filename_key, field_details in FIELD_MAPPING.items():  # .items() gets both key and value
    # filename_key will be something like 'Ohio_County_Boundaries'
    # field_details will be the nested dictionary, like {'name': 'County Name', 'county_sea': 'County Seat'}

    # Construct the filename:
    filename = f"{filename_key}.txt"  # You can customize the extension or add a path

    print(f"Processing file: {filename}")
    print(f"  Mapping details: {field_details}")

    # Now you can open the file and do something with it
    # For example, let's create a placeholder file and write some data:
    try:
        with open(filename, 'w') as file:
            file.write(f"This file is for {filename_key}.\n")
            if field_details:
                file.write("Field mappings:\n")
                for original_field, display_name in field_details.items():
                    file.write(f"  - {original_field}: {display_name}\n")
            else:
                file.write("No specific field mappings defined.\n")
        print(f"  Successfully created/updated {filename}")
    except IOError as e:
        print(f"  Error writing to {filename}: {e}")


# --- API Routes ---
@app.route('/')
def index():
    """Serves the main HTML page for the map viewer."""
    return render_template('multilayer_index.html')

@app.route('/api/layers')
def get_layers():
    """Returns a list of available shapefile layer names."""
    return jsonify(AVAILABLE_LAYERS)

@app.route('/api/data/<layer_name>')
def get_geodata(layer_name):
    """
    Loads, caches, and returns GeoJSON for a specific shapefile.
    The <layer_name> in the URL corresponds to the shapefile's base name.
    """
    # Security: Check if the requested layer is in our list of discovered files.
    if layer_name not in AVAILABLE_LAYERS:
        return jsonify({"error": "Layer not found"}), 404

    # Check if the data is already in our cache
    if layer_name in geodata_cache:
        return app.response_class(
            response=geodata_cache[layer_name],
            status=200,
            mimetype='application/json'
        )

    # If not cached, load the file
    shapefile_path = os.path.join(SHAPEFILE_FOLDER, f"{layer_name}.shp")
    try:
        print(f"Loading '{layer_name}' from disk: {shapefile_path}")
        gdf = gpd.read_file(shapefile_path, encoding='utf-8')

        # Reproject to WGS84 (EPSG:4326) for web mapping
        gdf = gdf.to_crs(epsg=4326)

        # --- Apply Field Mapping and Filtering ---
        print(layer_name)
        mapping = FIELD_MAPPING.get(layer_name)

        # Convert to GeoJSON string
        geojson_string = gdf.to_json()
        geodata_json = json.loads(geojson_string)
        #geodata_json = gdf.to_json()

        # Apply mapping/dropping rules.
        if mapping:
            print(f"Applying custom field mapping for '{layer_name}'")
            title_field = mapping.get('__title__')

            for feature in geodata_json['features']:
                original_properties = feature['properties']
                new_properties = {}

                # Set the special 'Title' property for the frontend
                if title_field and title_field in original_properties:
                    new_properties['Title'] = original_properties[title_field]

                # Filter and rename other properties
                for original_key, new_key in mapping.items():
                    if original_key == '__title__':
                        continue
                    if original_key in original_properties:
                        new_properties[new_key] = original_properties[original_key]

                feature['properties'] = new_properties
        else:
            print(f"Warning: No field mapping found for '{layer_name}'. Showing all fields.")


        # Store in cache for future requests
        processed_json_string = json.dumps(geodata_json)
        geodata_cache[layer_name] = processed_json_string

        #geodata_cache[layer_name] = geodata_json
        file_name = layer_name
        try:
            with open(file_name, "w", encoding="utf-8") as file:
                file.write(processed_json_string)
            print(f"String successfully saved to '{file_name}'")
        except IOError as e:
            print(f"Error saving string to file: {e}")

        print(f"Successfully loaded and cached '{layer_name}'.")
        return app.response_class(
            response=processed_json_string,
            status=200,
            mimetype='application/json'
        )

    except Exception as e:
        print(f"CRITICAL ERROR loading shapefile '{layer_name}': {e}")
        traceback.print_exc()
        return jsonify({"error": f"Could not load data for layer: {layer_name}"}), 500

# --- Main Execution ---
if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
