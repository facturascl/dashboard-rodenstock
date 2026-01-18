# streamlitecharts.py
from streamlit_echarts import st_echarts

def stecharts(option, height="600px", key=None):
    return st_echarts(option, height=height, key=key)
