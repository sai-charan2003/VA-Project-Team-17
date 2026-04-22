import streamlit as st
import plotly.express as px

st.write("App started/rerun")
if "map_key" not in st.session_state:
    st.session_state.map_key = {"selection": {"points": []}}

fig = px.scatter(x=[1, 2, 3], y=[1, 2, 3])
fig.update_traces(selected={"marker": {"color": "black"}}, unselected={"marker": {"opacity": 0.3}})
ev = st.plotly_chart(fig, on_select="rerun", key="map_key")

@st.dialog("My Dialog")
def show_dialog():
    st.write("Dialog is open")
    if st.button("Close inside"):
        st.session_state.map_key = {"selection": {"points": []}}
        st.rerun()

if ev and ev.selection.get("points"):
    st.write("Point selected!")
    show_dialog()
    # Try clearing immediately
    st.session_state.map_key = {"selection": {"points": []}}

