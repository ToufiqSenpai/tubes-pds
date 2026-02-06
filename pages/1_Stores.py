import streamlit as st
import pandas as pd
import os
import urllib.parse
import folium
from streamlit_folium import st_folium
from folium.plugins import MarkerCluster
from data.dataset import get_store_locations

def clean_dataset(df):
    df["name"] = df["name"].astype(str)
    df["address"] = df["address"].astype(str)

    df["name"] = df["name"].str.replace(r"\*+", "", regex=True)

    df["name"] = df["name"].str.strip()
    df["address"] = df["address"].str.strip()

    df["name"] = df["name"].str.title()

    df["latitude"] = pd.to_numeric(df["latitude"], errors="coerce")
    df["longitude"] = pd.to_numeric(df["longitude"], errors="coerce")

    df = df.dropna(subset=["latitude", "longitude"])
    df = df.drop_duplicates(subset=["name", "address"])

    return df


st.set_page_config(layout="wide")
st.title("Store Locator")

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
IMAGE_PATH = os.path.join(BASE_DIR, "toko.png")

df = clean_dataset(get_store_locations())

search = st.text_input("Cari Toko atau Lokasi",key="search_box")
query = st.session_state.search_box

if query:
    df_name = df[df["name"].str.contains(query, case=False, na=False)]

    if len(df_name) > 0:
        df = df_name
    else:
        df = df[df["address"].str.contains(query, case=False, na=False)]

st.subheader("Store Distribution Map")

with st.expander("📌 Petunjuk Penggunaan"):
    st.write("""
• Cari toko melalui kolom pencarian  
• Ganti tampilan peta melalui tab  
• Klik titik lokasi untuk melihat alamat toko
""")

tab1, tab2, tab3 = st.tabs([
    "Peta Biasa",
    "Marker Cluster",
    "Zoom Otomatis"
])

with tab1:
    m = folium.Map(location=[-2.5, 118], zoom_start=5)

    for _, row in df.iterrows():
        folium.Marker(
            [row["latitude"], row["longitude"]],
            popup=f"{row['name']} - {row['address']}",
            icon=folium.Icon(color="blue", icon="info-sign")
        ).add_to(m)

    with st.expander("ℹ\u2004Panduan Peta"):
        st.write("""
        • Setiap titik menunjukkan satu toko  
        • Gunakan scroll mouse untuk zoom  
        • Geser peta untuk melihat area lain
        """)

    st_folium(m, width="stretch", height=300, key="map_tab1")

with tab2:
    m = folium.Map(location=[-2.5, 118], zoom_start=5)
    cluster = MarkerCluster().add_to(m)

    for _, row in df.iterrows():
        folium.Marker(
            [row["latitude"], row["longitude"]],
            popup=f"{row['name']} - {row['address']}"
        ).add_to(cluster)

    with st.expander("ℹ\u2004Panduan Clusterr"):
        st.write("""
        • Lingkaran angka menunjukkan kumpulan toko  
        • Klik lingkaran untuk memperbesar area  
        • Marker akan terpisah saat zoom mendekat
        """)

        
    st_folium(m, width="stretch", height=300, key="map_tab2")

with tab3:
    m = folium.Map(zoom_start=5)

    bounds = []

    for _, row in df.iterrows():
        lat, lon = row["latitude"], row["longitude"]

        popup_text = f"""
        <b>{row['name']}</b><br>
        {row['address']}
        """

        folium.Marker(
            [lat, lon],
            popup=folium.Popup(popup_text, max_width=300)
            icon=folium.Icon(color="blue", icon="info-sign")
        ).add_to(m)

        bounds.append([lat, lon])

    if bounds:
        m.fit_bounds(bounds)
        
    with st.expander("ℹ\u2004Panduan Zoom Otomatis"):
        st.write("""
        • Peta otomatis fokus ke hasil pencarian  
        • Cocok untuk melihat persebaran toko di area tertentu
        """)
 
        
    st_folium(m, width="stretch", height=300, key="map_tab3")

st.subheader("Daftar Toko")

for i in range(0, len(df), 2):
    cols = st.columns(2)

    for j in range(2):
        if i + j >= len(df):
            break

        row = df.iloc[i + j]

        with cols[j]:
            with st.container(border=True):
                c1, c2 = st.columns([1, 3])

                with c1:
                    st.image(IMAGE_PATH, use_container_width=True)

                with c2:
                    st.write(f"**{row['name']}**")
                    st.write(row["address"])

                    query = f"{row['name']} {row['address']}"
                    maps_url = (
                        "https://www.google.com/maps/search/?api=1&query="
                        + urllib.parse.quote(query)
                    )

                    st.link_button("Jelajahi toko ini", maps_url)