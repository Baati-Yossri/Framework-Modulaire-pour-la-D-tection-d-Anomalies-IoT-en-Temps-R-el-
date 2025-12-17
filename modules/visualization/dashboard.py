import streamlit as st
import pandas as pd
import time
import os

st.set_page_config(page_title="IoT Sentinel", layout="wide", page_icon="🛡️")
BUFFER_FILE = "/app/data/viz_buffer.csv"

# CSS
st.markdown("""
<style>
    .stMetric { background-color: #f0f2f6; padding: 10px; border-radius: 5px; }
    div[data-testid="stMetricValue"] { font-size: 24px; }
</style>
""", unsafe_allow_html=True)

st.title("🛡️ IoT Sentinel : Monitoring Industriel")


def get_data():
    if not os.path.exists(BUFFER_FILE): return pd.DataFrame()
    try:
        df = pd.read_csv(BUFFER_FILE, on_bad_lines='skip')

        # --- Conversion Sécurisée ---
        # 1. Date
        if 'timestamp' in df.columns:
            df['timestamp'] = pd.to_datetime(df['timestamp'], format='%Y-%m-%d %H:%M:%S', errors='coerce')

        # 2. Nombres (Score et Capteurs)
        numeric_cols = ['score', 'temp', 'humidity', 'smoke', 'co', 'lpg']
        for c in numeric_cols:
            if c in df.columns:
                df[c] = pd.to_numeric(df[c], errors='coerce').fillna(0.0)

        return df
    except:
        return pd.DataFrame()


def highlight_anomalies(row):
    styles = [''] * len(row)
    if row.get('status') == 'ANOMALY':
        if 'status' in row.index:
            styles[row.index.get_loc('status')] = 'color: red; font-weight: bold;'
        if row.get('cause') in row.index:
            styles[row.index.get_loc(row['cause'])] = 'background-color: #ffcccc; color: #990000; font-weight: bold;'
    return styles


placeholder = st.empty()

while True:
    df = get_data()

    with placeholder.container():
        if df.empty:
            st.info("📡 En attente de données...")
        else:
            df = df.dropna(subset=['device_id'])
            if not df.empty:
                last_row = df.iloc[-1]

                # Stats 1h
                now = pd.Timestamp.now()
                # Vérification que timestamp est bien une date valide
                if pd.api.types.is_datetime64_any_dtype(df['timestamp']):
                    recent_anomalies = len(
                        df[(df['timestamp'] > (now - pd.Timedelta(hours=1))) & (df['status'] == 'ANOMALY')])
                else:
                    recent_anomalies = 0

                # KPIs
                k1, k2, k3, k4 = st.columns(4)
                k1.metric("Device", str(last_row.get('device_id', '?')))

                temp = float(last_row.get('temp', 0))
                k2.metric("Température", f"{temp:.1f} °C", delta="HOT" if temp > 50 else "OK", delta_color="inverse")

                score = float(last_row.get('score', 0))
                status = str(last_row.get('status', 'NORMAL'))
                k3.metric("État", status, delta=f"Score: {score:.2f}",
                          delta_color="inverse" if status == 'ANOMALY' else "normal")

                k4.metric("Anomalies (1h)", recent_anomalies)

                st.divider()

                # Graphes & Tableau
                c1, c2 = st.columns([2, 1])
                with c1:
                    st.subheader("Graphique Score")
                    if 'timestamp' in df.columns and 'score' in df.columns:
                        # On s'assure que le timestamp est l'index pour un beau graphique temporel
                        chart_data = df.set_index('timestamp')['score'].tail(50)
                        st.line_chart(chart_data, height=250)

                with c2:
                    st.subheader("Top Pannes")
                    if recent_anomalies > 0:
                        st.bar_chart(df[df['status'] == 'ANOMALY']['device_id'].value_counts(), height=250)
                    else:
                        st.success("Système stable")

                st.subheader("Flux de Données")
                recent = df.tail(10).sort_index(ascending=False)
                cols = ['timestamp', 'device_id', 'status', 'temp', 'humidity', 'smoke', 'co', 'lpg', 'cause']
                cols_ok = [c for c in cols if c in df.columns]

                try:
                    st.dataframe(recent[cols_ok].style.apply(highlight_anomalies, axis=1).format(
                        {'temp': "{:.1f}", 'score': "{:.2f}"}), use_container_width=True)
                except:
                    st.dataframe(recent[cols_ok], use_container_width=True)

    time.sleep(2)