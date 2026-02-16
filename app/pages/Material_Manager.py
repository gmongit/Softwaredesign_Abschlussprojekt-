import streamlit as st

st.title("🧪 Material Manager")
st.write("Hier kannst du zukünftig Werkstoffeigenschaften definieren.")

st.info("Aktuell wird in der Berechnung der Standard-k-Wert aus dem Structure Creator verwendet.")

# Beispielhafte Anzeige ohne Datenbank-Anbindung
st.text_input("Material Name", value="Standard Steel")
st.number_input("E-Modul (Beispiel)", value=210000)