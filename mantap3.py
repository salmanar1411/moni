import firebase_admin
from firebase_admin import credentials, db, storage
import streamlit as st
import folium
from streamlit.components.v1 import html
import time
import pandas as pd
import base64
from dateutil import parser
import math

st.set_page_config(page_title="Monitoring Kapal", page_icon="🚤", layout='wide')

# Inisialisasi Firebase Admin SDK
cred = credentials.Certificate("serviceAccountKey.json")  # Path to your service account key
firebase_admin.initialize_app(cred, {
    'databaseURL': 'https://coba-53d06-default-rtdb.asia-southeast1.firebasedatabase.app/',  # URL of your Firebase Realtime Database
    'storageBucket': 'coba-53d06.appspot.com'  # URL of your Firebase Storage bucket
})

# URL gambar di Firebase Storage
atas = 'surface/surface.jpeg'
bawah = 'underwater/underwater.jpeg'

# Buat persegi panjang dengan background
st.markdown(
    """
    <div style="background-color: #005EB8; padding: 20px; border-radius: 10px;">
        <h2 style="text-align: center;">Mavis Force - Universitas Negeri Yogyakarta</h2>
    </div>
    """,
    unsafe_allow_html=True
)

# Fungsi untuk mengkonversi gambar menjadi base64
def get_base64_image(image_file):
    with open(image_file, "rb") as f:
        return base64.b64encode(f.read()).decode()

# Fungsi untuk membuat peta dengan Folium
def create_map(points):
    if len(points) > 0:
        last_point = points[-1]

        center_lat = last_point.get("lat")  # Menggunakan 'lat' dari data
        center_lon = last_point.get("lon")  # Menggunakan 'lon' dari data

        if center_lat is None or center_lon is None:
            st.error("Tidak ada data latitude atau longitude untuk peta.")
            return None

        zoom_level = 21
        gps_map = folium.Map(location=[center_lat, center_lon], zoom_start=zoom_level, max_zoom=25)

        coordinates = []
        for index, point in enumerate(points):
            latitude = point.get("lat")
            longitude = point.get("lon")

            if latitude is None or longitude is None:
                continue

            popup_content = (
                f"Timestamp: {point['timestamp']}<br>"
                f"Latitude: {latitude}<br>"
                f"Longitude: {longitude}<br>"
                f"COG: {point['cog']}<br>"
                f"Speed (KPH): {point['speed_kph']}<br>"
                f"Speed (Knots): {point['speed_knots']}"
            )

            if index == len(points) - 1:
                custom_icon_path = "kapal.png"  # Ganti dengan path gambar ikon kapal Anda
                base64_image = get_base64_image(custom_icon_path)
                heading = point.get("cog", 0)

                icon_html = f"""
                <div style="transform: rotate({heading}deg); margin-left: -50px; margin-top: -50px;">
                    <img src="data:image/png;base64,{base64_image}" style="width:100px; height:100px;"/>
                </div>
                """
                folium.Marker(
                    location=[latitude, longitude],
                    popup=popup_content,
                    icon=folium.DivIcon(html=icon_html)
                ).add_to(gps_map)
            else:
                folium.Marker(
                    location=[latitude, longitude],
                    popup=popup_content,
                    icon=folium.Icon(color="blue")
                ).add_to(gps_map)

            coordinates.append((latitude, longitude))

        if len(coordinates) > 1:
            folium.PolyLine(locations=coordinates, color="blue", weight=2.5, opacity=1).add_to(gps_map)

        return gps_map
    else:
        return None

# Fungsi untuk menampilkan peta di Streamlit
def display_map(folium_map):
    map_html = folium_map._repr_html_()
    html(map_html, height=400, width=None)

# Fungsi untuk memperbarui gambar dari Firebase Storage
def get_updated_image_url(bucket_name, file_path):
    bucket = storage.bucket(bucket_name)
    blob = bucket.blob(file_path)
    expiration_time = int(time.time() + 60)  # Expire URL in 60 seconds
    url = blob.generate_signed_url(expiration_time=expiration_time)
    return url

# Fungsi untuk mengambil data dari Firebase Realtime Database
def fetch_data():
    try:
        ref = db.reference('info')
        info = ref.get()

        if not info or "counter" not in info:
            st.error("Counter tidak ditemukan di node 'info'.")
            return None, None

        counter = info.get("counter")
        folder = f"gps-points{str(counter).zfill(2)}"

        data_ref = db.reference(folder)
        data = data_ref.get()

        if not data:
            st.warning(f"Tidak ada data ditemukan di folder: {folder}")
            return counter, None

        return counter, data
    except Exception as e:
        st.error(f"Terjadi kesalahan saat mengambil data: {e}")
        return None, None

# Fungsi untuk menampilkan informasi Geo-tag
def generate_geotag_info(timestamp, lat, lon, speed_knots, cog):
    day_of_week = date_str = time_str = "-"
    if timestamp:
        try:
            timestamp = parser.parse(timestamp)
            days_of_week = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]
            day_of_week = days_of_week[timestamp.weekday()]
            date_str = timestamp.strftime("%d/%m/%Y")
            time_str = timestamp.strftime("%H:%M:%S")
        except Exception as e:
            st.error(f"Error parsing timestamp: {e}")

    coord_decimal = coord_minute = "-"
    if lat is not None:
        lat_deg = int(abs(lat))
        lat_min = (abs(lat) - lat_deg) * 60
        lon_deg = int(abs(lon))
        lon_min = (abs(lon) - lon_deg) * 60
        coord_decimal = f"{'S' if lat < 0 else 'N'} {lat_deg + lat_min/60:.5f}, {'W' if lon < 0 else 'E'} {lon_deg + lon_min/60:.5f}"

    speed_kph = speed_knots * 1.852 if speed_knots else "-"
    cog = cog if cog is not None else "-"

    return (
        f"Geo-tag Infos:\n"
        f"Day: {day_of_week}\n"
        f"Date: {date_str}\n"
        f"Time: {time_str}\n"
        f"Coordinate: [{coord_decimal}]\n"
        f"Speed Over Ground: {speed_knots:.0f} knots / {speed_kph:.0f} km/h\n"
        f"Course Over Ground: {cog:.2f}°"
    )

# Layout kolom untuk peta dan gambar
col1, col2 = st.columns(2)

def run_streamlit():
    info_ref = db.reference('info')
    info = info_ref.get()

    link = info.get('link', '')
    arena = info.get('arena', '')

    with st.container():
        with col1:
            st.header(f"Lintasan : {arena}")
            st.header("Position-Log : ")

            st.subheader("Floating Ball Set")
            table_placeholder = st.empty()

            col1a, col1b = st.columns(2)
            with col1a:
                st.subheader("Surface Image")
                surface_placeholder = st.empty()
                surgeo_placeholder = st.empty()

            with col1b:
                st.subheader("Underwater Image")
                underwater_placeholder = st.empty()
                undergeo_placeholder = st.empty()

        with col2:
            st.header("Boat Tracker")
            youtube_video_id = link
            embed_url = f"https://www.youtube.com/embed/{youtube_video_id}"

            maps_placeholder = st.empty()
            geotag_placeholder = st.empty()

            st.title("Live Streaming")
            st.markdown(f"""
                <div style="display: flex; justify-content: center;">
                    <iframe width="600" height="400" src="{embed_url}?autoplay=1&mute=1" 
                    frameborder="0" allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture" 
                    allowfullscreen></iframe>
                </div>
                """, unsafe_allow_html=True)

    while True:
        counter, data = fetch_data()
        if not data:
            continue

        gps_points = []
        position_data = []

        if data:
            position_raw = data.get("posisi")
            if position_raw:
                timestamp = str(position_raw.get('timestamp'))
                lat = position_raw.get('lat')
                lon = position_raw.get('lon')
                speed_knots = position_raw.get('speed_knots', 0)
                speed_kph = speed_knots * 1.852
                cog = position_raw.get('cog')

                position_data = [
                    {"Label": "Latitude", "Value": lat},
                    {"Label": "Longitude", "Value": lon},
                    {"Label": "Speed (Knots)", "Value": speed_knots},
                    {"Label": "Speed (KPH)", "Value": speed_kph},
                    {"Label": "COG", "Value": cog},
                    {"Label": "Timestamp", "Value": timestamp}
                ]

                gps_points = data.get("gps_data", [])

        table_placeholder.table(pd.DataFrame(position_data))

        if gps_points:
            folium_map = create_map(gps_points)
            if folium_map:
                maps_placeholder.write(folium_map, unsafe_allow_html=True)

        geotag_info = generate_geotag_info(timestamp, lat, lon, speed_knots, cog)
        geotag_placeholder.text(geotag_info)

        # Perbarui URL gambar dari Firebase Storage
        bucket_name = "your-storage-bucket-url"
        surface_image_url = get_updated_image_url(bucket_name, atas)
        underwater_image_url = get_updated_image_url(bucket_name, bawah)

        # Tampilkan gambar di Streamlit
        surface_placeholder.image(surface_image_url, use_column_width=True)
        underwater_placeholder.image(underwater_image_url, use_column_width=True)

        time.sleep(2)

run_streamlit()
