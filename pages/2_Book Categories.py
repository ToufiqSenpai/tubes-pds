import streamlit as st
from data import get_book_categories_cached

st.title("Book Categories")
st.dataframe(get_book_categories_cached())