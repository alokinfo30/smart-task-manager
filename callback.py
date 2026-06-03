import streamlit as st
import urllib.parse

st.set_page_config(page_title="Logging in...", layout="centered")

# Capture Auth0 query parameters (code, state)
q_params = urllib.parse.urlencode(st.query_params)

# Redirect back to the main app root with the parameters intact
# This allows app.py to finalize the Auth0 Interactive Login
redirect_url = f"/?{q_params}" if q_params else "/"
st.markdown(f'<meta http-equiv="refresh" content="0; url={redirect_url.replace("&", "&amp;")}">', unsafe_allow_html=True)