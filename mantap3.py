import os
import requests
import time
import streamlit as st
import folium
from streamlit.components.v1 import html
import base64
from datetime import datetime, timedelta
import pandas as pd
from dateutil import parser
import math
import firebase_admin
from firebase_admin import credentials, db, storage

# Inisialisasi Streamlit
st.set_page_config(page_title="Monitoring Kapal", page_icon="🚤", layout='wide')

# Fungsi untuk memeriksa keberadaan file
def check_file_exists(file_path):
    if not os.path.exists(file_path):
        st.error(f"File '{file_path}' tidak ditemukan di direktori aplikasi.")
        st.stop()
    else:
        st.success(f"File '{file_path}' ditemukan.")

# Periksa keberadaan file serviceAccountKey.json
check_file_exists('serviceAccountKey.json')

# Inisialisasi Firebase Admin SDK
def initialize_firebase():
    try:
        cred_path = 'serviceAccountKey.json'
        cred = credentials.Certificate(cred_path)
        firebase_admin.initialize_app(cred, {
            "databaseURL": "https://coba-53d06-default-rtdb.asia-southeast1.firebasedatabase.app/",
            "storageBucket": "coba-53d06.appspot.com"
        })
        st.success("Firebase berhasil diinisialisasi.")
    except firebase_admin.exceptions.FirebaseError as fe:
        st.error(f"Gagal menginisialisasi Firebase: {fe}")
        st.stop()
    except Exception as e:
        st.error(f"Terjadi kesalahan saat inisialisasi Firebase: {e}")
        st.stop()

# Panggil fungsi inisialisasi
initialize_firebase()

# Referensi ke Realtime Database dan Storage
firebase_db = db.reference()
firebase_storage = storage.bucket()

# URL gambar
atas = 'https://firebasestorage.googleapis.com/v0/b/coba-53d06.appspot.com/o/surface%2Fsurface.jpeg?alt=media'
bawah = 'https://firebasestorage.googleapis.com/v0/b/coba-53d06.appspot.com/o/underwater%2Funderwater.jpeg?alt=media'

# Buat persegi panjang dengan background
st.markdown(
    """
    <div style="background-color: #005EB8; padding: 20px; border-radius: 10px;">
        <h2 style="text-align: center; color: white;">Mavis Force - Universitas Negeri Yogyakarta</h2>
    </div>
    """,
    unsafe_allow_html=True
)

# Fungsi untuk memuat CSS
def load_css(file_name):
    if os.path.exists(file_name):
        with open(file_name) as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)
    else:
        st.warning(f"File '{file_name}' tidak ditemukan. Melanjutkan tanpa stylesheet khusus.")

load_css("style.css")

# Fungsi untuk mengkonversi gambar menjadi base64
def get_base64_image(image_file):
    try:
        with open(image_file, "rb") as f:
            return base64.b64encode(f.read()).decode()
    except FileNotFoundError:
        st.warning(f"File gambar '{image_file}' tidak ditemukan.")
        return ""

# Fungsi untuk membuat peta dengan Folium
def create_map(points):
    if len(points) > 0:
        last_point = points[-1]

        # Memastikan bahwa kunci latitude dan longitude ada
        center_lat = last_point.get("lat")
        center_lon = last_point.get("lon")

        if center_lat is None or center_lon is None:
            st.error("Tidak ada data latitude atau longitude untuk peta.")
            return None

        # Menyesuaikan zoom level agar area yang terlihat sekitar 25x25 meter
        zoom_level = 21

        gps_map = folium.Map(
            location=[center_lat, center_lon],
            zoom_start=zoom_level,
            max_zoom=50
        )

        # Menambahkan marker untuk setiap titik
        coordinates = []
        for index, point in enumerate(points):
            latitude = point.get("lat")
            longitude = point.get("lon")

            if latitude is None atau longitude is None:
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
                custom_icon_path = "kapal.png"  # Ganti dengan path gambar Anda
                base64_image = get_base64_image(custom_icon_path)
                heading = point.get("cog", 0)

                if base64_image:
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
                        icon=folium.Icon(color="red", icon="info-sign")
                    ).add_to(gps_map)
            else:
                folium.Marker(
                    location=[latitude, longitude],
                    popup=popup_content,
                    icon=folium.Icon(color="blue")
                ).add_to(gps_map)

            coordinates.append((latitude, longitude))

        # Menambahkan garis
        if len(coordinates) > 1:
            folium.PolyLine(locations=coordinates, color="blue", weight=2.5, opacity=1).add_to(gps_map)

        return gps_map
    else:
        return None

# Fungsi untuk menampilkan peta di Streamlit
def display_map(folium_map):
    map_html = folium_map._repr_html_()
    html(map_html, height=500, width=700)

# Fungsi untuk memperbarui gambar dari Firebase Storage dengan cache-busting
def get_updated_image_url(base_url):
    timestamp = int(time.time())
    return f"{base_url}&t={timestamp}"

# Fungsi untuk mengambil data dari Firebase menggunakan firebase_admin
def fetch_data():
    try:
        if firebase_db is None:
            st.error("Koneksi ke Firebase tidak tersedia.")
            return None, None

        # Ambil data dari node 'info' untuk mendapatkan counter
        info = firebase_db.child("info").get()
        if info is None or "counter" not in info:
            st.error("Counter tidak ditemukan di node 'info'. Periksa konfigurasi Firebase.")
            return None, None

        counter = info.get("counter")
        folder = f"gps-points{str(counter).zfill(2)}"

        # Ambil data dari folder yang sesuai
        data = firebase_db.child(folder).get()

        if data is None:
            st.warning(f"Tidak ada data ditemukan di folder: {folder}")
            return counter, None

        return counter, data
    except firebase_admin.exceptions.FirebaseError as fe:
        st.error(f"Terjadi kesalahan saat mengambil data dari Firebase: {fe}")
        return None, None
    except Exception as e:
        st.error(f"Terjadi kesalahan saat mengambil data: {e}")
        return None, None

# Fungsi untuk menghasilkan informasi geotag
def generate_geotag_info(timestamp, lat, lon, speed_knots, cog):
    day_of_week = "-"
    date_str = "-"
    time_str = "-"
    
    if timestamp is None or timestamp == '' or timestamp == 'None':
        timestamp = "-"
    else:
        try:
            timestamp = parser.parse(timestamp)
            days_of_week = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]
            day_of_week = days_of_week[timestamp.weekday()]
            date_str = timestamp.strftime("%d/%m/%Y")
            time_str = timestamp.strftime("%H:%M:%S")
        except Exception as e:
            st.error(f"Error parsing timestamp: {e}")

    if lat is None atau lon is None:
        coord_decimal = "-"
    else:
        lat_deg = int(abs(lat))
        lat_min = (abs(lat) - lat_deg) * 60
        lon_deg = int(abs(lon))
        lon_min = (abs(lon) - lon_deg) * 60
        coord_decimal = f"{'S' if lat < 0 else 'N'} {lat_deg + lat_min/60:.5f}, {'W' if lon < 0 else 'E'} {lon_deg + lon_min/60:.5f}"

    if speed_knots is None:
        speed_knots = "-"
        speed_kph = "-"
    else:
        speed_kph = speed_knots * 1.852

    if cog is None:
        cog = "-"

    geotag_info = (
        f"Geo-tag Infos:\n"
        f"Day: {day_of_week}\n"
        f"Date: {date_str}\n"
        f"Time: {time_str}\n"
        f"Coordinate: [{coord_decimal}]\n"
        f"Speed Over Ground: {speed_knots} knots / {speed_kph} km/h\n"
        f"Course Over Ground: {cog}°"
    )

    return geotag_info

# Membuat layout kolom untuk peta dan gambar
col1, col2 = st.columns(2, gap="small")
gps_points = []
position_data = []

def run_streamlit():
    info = firebase_db.child("info").get()

    link = info.get('link', '')
    arena = info.get('arena', '')

    # Debug: Tampilkan link dan arena
    st.write(f"Link: {link}, Arena: {arena}")

    previous_folder = None 

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

            youtube_video_id = link  # Ganti dengan ID video YouTube Anda
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

        if data is None:
            time.sleep(0.5)
            continue

        current_folder = f"gps-points{str(counter).zfill(2)}"

        if current_folder != previous_folder:
            position_data.clear()
            previous_folder = current_folder

        gps_points.clear()

        if data:
            position_raw = data.get("posisi") 
            if position_raw:
                timestamp = str(position_raw.get('timestamp'))
                lat = position_raw.get('lat')
                lon = position_raw.get('lon')
                speed_knots = position_raw.get('speed_knots', 0)
                speed_kph = speed_knots * 1.852
                cog = position_raw.get('cog', 0)

                if lat is not None and lon is not None:
                    position_data.append({
                        "timestamp": timestamp,
                        "lat": lat, 
                        "lon": lon, 
                        "speed_kph": speed_kph,
                        "speed_knots": speed_knots,
                        "cog": cog
                    })

                    geotag_info = generate_geotag_info(timestamp, lat, lon, speed_knots, cog)
                    
                    with geotag_placeholder:
                        st.text(geotag_info)

            # Proses setiap titik GPS
            for key, gps_raw_int in data.items():
                if key.startswith('bola'):
                    if isinstance(gps_raw_int, dict):
                        timestamp = str(gps_raw_int.get('timestamp'))
                        lat = gps_raw_int.get('lat')
                        lon = gps_raw_int.get('lon')
                        speed_knots = gps_raw_int.get('speed_knots', 0)
                        speed_kph = speed_knots * 1.852
                        cog = gps_raw_int.get('cog', 0)

                        try:
                            lat = float(lat) if lat is not None else None
                            lon = float(lon) if lon is not None else None
                        except ValueError:
                            continue

                        if lat is not None and lon is not None:
                            gps_lat = f"{'S' if lat < 0 else 'N'} {abs(lat):.5f}"
                            gps_lon = f"{'W' if lon < 0 else 'E'} {abs(lon):.5f}"

                            gps_points.append({
                                "ID": key,
                                "timestamp": timestamp,
                                "coordinate": f"{gps_lat}, {gps_lon}", 
                                "speed_kph": speed_kph,
                                "speed_knots": speed_knots,
                                "cog": cog
                            })

                if key.startswith('underwater'):
                    if isinstance(gps_raw_int, dict):
                        timestamp = str(gps_raw_int.get('timestamp'))
                        lat = gps_raw_int.get('lat')
                        lon = gps_raw_int.get('lon')
                        speed_knots = gps_raw_int.get('speed_knots', 0)
                        speed_kph = speed_knots * 1.852
                        cog = gps_raw_int.get('cog', 0)

                        try:
                            lat = float(lat) if lat is not None else None
                            lon = float(lon) if lon is not None else None
                        except ValueError:
                            continue

                        if lat is not None and lon is not None:
                            geotag_info = generate_geotag_info(timestamp, lat, lon, speed_knots, cog)
                            with undergeo_placeholder:
                                st.text(geotag_info)

                if key.startswith('surface'):
                    if isinstance(gps_raw_int, dict):
                        timestamp = str(gps_raw_int.get('timestamp'))
                        lat = gps_raw_int.get('lat')
                        lon = gps_raw_int.get('lon')
                        speed_knots = gps_raw_int.get('speed_knots', 0)
                        speed_kph = speed_knots * 1.852
                        cog = gps_raw_int.get('cog', 0)

                        try:
                            lat = float(lat) if lat is not None else None
                            lon = float(lon) if lon is not None else None
                        except ValueError:
                            continue

                        if lat is not None and lon is not None:
                            geotag_info = generate_geotag_info(timestamp, lat, lon, speed_knots, cog)
                            with surgeo_placeholder:
                                st.text(geotag_info)

        # Membuat tabel
        tabel = pd.DataFrame(gps_points)

        # Mengupdate tabel di Streamlit
        with table_placeholder:
            if len(gps_points) > 0:
                if len(gps_points) > 10:
                    tabel = pd.DataFrame(gps_points[-10:])

                tabel = tabel[['ID', 'timestamp', 'coordinate', 'speed_kph', 'speed_knots', 'cog']]
                st.table(tabel.reset_index(drop=True))
            else:
                st.write("No data available")

        # Pembaruan peta
        valid_points = [point for point in position_data if point['lat'] is not None and point['lon'] is not None]
        folium_map = create_map(valid_points)

        if folium_map is not None:
            with maps_placeholder:
                display_map(folium_map)

        # Pembaruan gambar dengan cache-busting
        with underwater_placeholder:
            underwater_img_url = get_updated_image_url(bawah)
            st.image(underwater_img_url, use_column_width=True)

        with surface_placeholder:
            surface_img_url = get_updated_image_url(atas)
            st.image(surface_img_url, use_column_width=True)

        time.sleep(0.5)

# Jalankan aplikasi Streamlit
run_streamlit()
