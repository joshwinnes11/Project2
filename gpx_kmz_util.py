import zipfile
from fastkml import kml
import gpxpy
import pandas as pd

def gpx_to_df(file_name):
    # Load your GPX file
    gpx_file = open(file_name, 'r')

    # Parse the GPX file
    gpx = gpxpy.parse(gpx_file)

    # Create lists to store data
    latitude = []
    longitude = []
    elevation = []
    time = []

    # Iterate through all track points
    for track in gpx.tracks:
        for segment in track.segments:
            for point in segment.points:
                latitude.append(point.latitude)
                longitude.append(point.longitude)
                elevation.append(point.elevation)
                time.append(point.time)

    # Create a pandas DataFrame
    gpx_df = pd.DataFrame({
        'Latitude': latitude,
        'Longitude': longitude,
        'Elevation': elevation,
        'Time': time
    })

    return gpx_df

def extract_kml_from_kmz(kmz_file):
    with zipfile.ZipFile(kmz_file, 'r') as kmz:
        for file_name in kmz.namelist():
            if file_name.endswith('.kml'):
                with kmz.open(file_name) as kml_file:
                    return kml_file.read()

def parse_kml_to_dataframe(kml_data):
    k = kml.KML()
    k.from_string(kml_data)

    # Assuming that the data is within the first document and the first placemark set
    features = list(k.features())
    document = features[0]
    placemarks = list(document.features())
    
    # Create lists to store extracted data
    data = {'name': [], 'description': [], 'longitude': [], 'latitude': []}

    for placemark in placemarks:
        # Extract the placemark data
        if hasattr(placemark, 'geometry'):
            coords = list(placemark.geometry.coords)
            if coords:
                lon, lat = coords[0][:2]  # (longitude, latitude)
                data['longitude'].append(lon)
                data['latitude'].append(lat)
                data['name'].append(placemark.name)
                data['description'].append(placemark.description)

    # Step 3: Convert the extracted data to a DataFrame
    df = pd.DataFrame(data)
    return df
