import streamlit as st
from data import get_books_cached

st.title("Books")
st.dataframe(get_books_cached())