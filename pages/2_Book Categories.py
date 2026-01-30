import streamlit as st
from data.dataset import get_book_categories

st.title("Book Categories")
st.dataframe(get_book_categories())