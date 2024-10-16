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


def data_preprocessing(gpx_file_name, kmz_file_path):
    
    gpx_data = gpx_to_df(gpx_file_name)
    kml_data = extract_kml_from_kmz(kmz_file_path)
    kmz_data = parse_kml_to_dataframe(kml_data)

    
    kmz_data.drop('description', axis=1, inplace=True)
    kmz_data.columns = ['Name', 'Longitude', 'Latitude']
    
    kmz_data = pd.merge(kmz_data[['Name', 'Longitude', 'Latitude']], gpx_data, how = 'left', on=['Longitude', 'Latitude'])
    kmz_data.drop_duplicates(inplace=True)
    
    kmz_data['time_elapsed'] = kmz_data["Time"].diff(periods=-1)
    #kmz_data['Elevation_Change'] = (kmz_data['Elevation'].diff(periods=-11))
    kmz_data['end_time'] = kmz_data['Time']-kmz_data['time_elapsed']
    kmz_data['time_elapsed'] = kmz_data['end_time']-kmz_data['Time']
    
    gpx_data = gpx_data.merge(kmz_data[['Name', 'Time']], how='left', on='Time')
    
    gpx_data['Time'] = gpx_data['Time'].apply(lambda x: x + pd.Timedelta(hours=12) if x.hour < 8 else x)
    kmz_data['time_elapsed'] = kmz_data['time_elapsed'].apply(lambda x: x+pd.Timedelta(hours=24) if x < pd.Timedelta(0) else x)
    
    gpx_data.fillna(method='ffill', axis=0, inplace=True)
    gpx_data.fillna(value = 'pre_lift_1', inplace = True)
    
    return gpx_data, kmz_data


