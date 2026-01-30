import streamlit as st
import pandas as pd
import sys
import os
import urllib.parse
import folium
from streamlit_folium import st_folium

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from data.dataset import get_store_locations

st.set_page_config(layout="wide")
st.title("Store Locator")

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
IMAGE_PATH = os.path.join(BASE_DIR, "toko_buku.png")

df = get_store_locations()

st.markdown("""
<style>
div[data-testid="stTextInput"] label {
        display: none;
    }
    
div[data-testid="stTextInput"] {
    position: relative;
}

div[data-testid="stTextInput"]::before {
    content: "";
    position: absolute;
    left: 14px;
    top: 50%;
    width: 16px;
    height: 16px;
    transform: translateY(-60%);
    background: url("data:image/svg+xml;utf8,\
<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='%239ca3af' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'>\
<circle cx='11' cy='11' r='8'/>\
<line x1='21' y1='21' x2='16.65' y2='16.65'/>\
</svg>") no-repeat center;

}
div[data-testid="stTextInput"] input {
    padding-left: 40px;
    border-radius: 24px;
}

.store-card > div[data-testid="stContainer"] {
    height: 260px;
    display: flex;
    flex-direction: column;
    justify-content: space-between;
}

</style>
""", unsafe_allow_html=True)

search = st.text_input(
    label="",
    placeholder="Cari Toko atau Lokasi"
)

if search:
    mask = (
        df["name"].str.contains(search, case=False, na=False) |
        df["address"].str.contains(search, case=False, na=False)
    )
    df = df[mask]

st.write(f"Menampilkan {len(df)} toko")

st.subheader("Store Distribution Map")

m = folium.Map(
    location=[-2.5, 118],
    zoom_start=5,
    tiles="OpenStreetMap"
)

for _, row in df.iterrows():
    if pd.notna(row["latitude"]) and pd.notna(row["longitude"]):
        try:
            lat = float(row["latitude"])
            lon = float(row["longitude"])

            folium.Marker(
                location=[lat, lon],
                popup=f"<b>{row['name']}</b><br>{row['address']}",
                icon=folium.Icon(color="blue", icon="location-dot", prefix="fa")
            ).add_to(m)

        except:
            pass

st_folium(m, use_container_width=True, height=300)

cols = st.columns(2)

i = 0
for i in range(0, len(df), 2):
    cols = st.columns(2)

    for j in range(2):
        if i + j >= len(df):
            break

        row = df.iloc[i + j]

        with cols[j]:
            st.markdown('<div class="store-card">', unsafe_allow_html=True)

            with st.container(border=True):
                c1, c2 = st.columns([1, 3])

                with c1:
                    st.image(IMAGE_PATH, use_container_width=True)

                with c2:
                    st.markdown(f"**{row['name']}**")
                    st.write(row["address"])

                    query = f"{row['name']} {row['address']}"
                    maps_url = (
                        "https://www.google.com/maps/search/?api=1&query="
                        + urllib.parse.quote(query)
                    )

                    st.markdown(
                        f"""
                        <a href="{maps_url}" target="_blank">
                            Jelajahi toko ini →
                        </a>
                        """,
                        unsafe_allow_html=True
                    )

            st.markdown('</div>', unsafe_allow_html=True)

    i += 1