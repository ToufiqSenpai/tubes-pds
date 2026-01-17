import streamlit as st
from streamlit_chat import message

message("Hello! I'm your assistant. How can I help you today?", key="assistant_1")
message("I need help with my order.", is_user=True, key="user_1")

with st.container():
  st.text_input(key="input_1", label="", placeholder="Type message here...")