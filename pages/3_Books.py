import streamlit as st
from data.dataset import get_books

st.title("Books")
st.dataframe(get_books())