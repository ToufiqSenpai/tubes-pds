import streamlit as st
from data import get_store_locations_cached

st.title("Store Locations")
st.dataframe(get_store_locations_cached())