import streamlit as st
import streamlit_shadcn_ui as ui

with st.container(border=True):
    st.title("Book Store", text_alignment="center")
    ui.input(placeholder="Search for books...")
    
    ui.select(
        label="Sort by",
        options=["Relevance", "Price: Low to High", "Price: High to Low", "Newest"]
    )