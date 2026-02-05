import streamlit as st

st.set_page_config(
    page_title="Topologieoptimierung – Abschlussprojekt",
    layout="wide"
)

st.title("Topologieoptimierung – Abschlussprojekt")

st.markdown("""
Willkommen 👋  

Diese App ist Teil des Abschlussprojekts **Softwaredesign**.

👉 Nächster Schritt:
- Struktur erzeugen (MBB-Balken)
- Analyse durchführen
- Ergebnisse visualisieren
""")

st.sidebar.header("Steuerung")
st.sidebar.info("Noch keine Funktionen implementiert.")

st.success("Setup läuft – Streamlit ist startklar ✅")
