import zipfile
from fastkml import kml
import gpxpy
import pandas as pd

### Functions for reading in the data

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


### Preprocessing Functions

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
    
    gpx_data = get_dist_time(gpx_data)
    
    return gpx_data, kmz_data

from haversine import haversine

def get_dist_time(df):
    # Shift latitude and longitude columns for previous points
    df.drop_duplicates()
    
    df['Latitude_Shifted'] = df['Latitude'].shift()
    df['Longitude_Shifted'] = df['Longitude'].shift()

    # Calculate distances
    df['Distance'] = df.apply(
        lambda row: haversine(
            (row['Latitude'], row['Longitude']),
            (row['Latitude_Shifted'], row['Longitude_Shifted'])
        ) * 1000 if not pd.isna(row['Latitude_Shifted']) else 0,
        axis=1
    )

    # Calculate time differences
    df['Time_Diff'] = df['Time'].diff().dt.total_seconds()

    # Calculate speeds
    df['Speed'] = df['Distance'] / df['Time_Diff']
    df['Speed'].fillna(0, inplace=True)  # Set speed to 0 for the first row
    df['Speed_MPH'] = df['Speed']*2.2369362920544
    df['Time_Diff'].fillna(0,inplace=True)

    # Drop the temporary shifted columns
    df.drop(['Latitude_Shifted', 'Longitude_Shifted'], axis=1, inplace=True)
    
    df['Time'] = pd.to_datetime(df['Time'], errors = 'coerce').dt.tz_localize(None)
    df.dropna(subset=['Time'], inplace = True)
    
    df = df[df['Name']!='pre_lift_1']
    df = df[df['Speed']<45]

    return df

### Functions for adding things to and plotting the maps

import folium
def add_staypionts(df_stay_location, foliumMap):
    
    df_stay_location['datetime'] = df_stay_location['datetime'].dt.tz_localize(None)
    
    for lat, lng, datetime, leave_time in zip(df_stay_location['lat'], df_stay_location['lng'], df_stay_location['datetime'], df_stay_location['leaving_datetime']):
        folium.CircleMarker(
        location=[lat, lng],
        tooltip = leave_time-datetime,
        radius=10,
        weight=2,
        color='red'  # Use a fixed color since we're focusing on one day
    ).add_to(foliumMap)

import matplotlib.pyplot as plt
import matplotlib as mpl
import folium
from branca.element import Template, MacroElement
import base64
from io import BytesIO

import matplotlib.pyplot as plt
import matplotlib as mpl
import folium
from branca.element import Template, MacroElement
import base64
from io import BytesIO

def add_speed_heatmap(df_gpx, foliumMap):
    df = df_gpx.drop(labels=['Time'], axis=1)

    min_speed, max_speed = df['Speed_MPH'].min(), df['Speed_MPH'].max()
    norm = plt.Normalize(vmin=min_speed, vmax=max_speed)
    colormap = plt.cm.get_cmap("inferno")

    for idx, row in df.iterrows():
        folium.CircleMarker(
            location=(row['Latitude'], row['Longitude']),
            radius=2,
            color=mpl.colors.to_hex(colormap(norm(row['Speed_MPH']))),
            fill=False,
            fill_color=mpl.colors.to_hex(colormap(norm(row['Speed_MPH']))),
            fill_opacity=0.2,
        ).add_to(foliumMap)

    # Generate the vertical color scale image
    fig, ax = plt.subplots(figsize=(0.5, 4))  # Taller and narrower figure
    cb = mpl.colorbar.ColorbarBase(ax, cmap=colormap, norm=norm, orientation='vertical')
    cb.set_label('Speed (MPH)')

    # Save the image to a BytesIO object
    buf = BytesIO()
    fig.savefig(buf, format='png', bbox_inches='tight', dpi=100)
    buf.seek(0)
    encoded = base64.b64encode(buf.read()).decode('utf-8')
    buf.close()

    # HTML template for the vertical legend
    legend_html = f'''
    <div style="
    position: fixed;
    bottom: 50px;
    left: 50px;
    width: 100px;
    height: 600px;
    z-index:9999;
    font-size:14px;
    background-color: rgba(255, 255, 255, 0.8);
    padding: 10px;
    border-radius: 5px;
    text-align: center;
    ">
    <b>Speed Legend (mph)</b><br>
    <img src="data:image/png;base64,{encoded}" alt="Legend">
    </div>
    '''

    macro = MacroElement()
    macro._template = Template(legend_html)
    foliumMap.get_root().add_child(macro)

    return foliumMap


