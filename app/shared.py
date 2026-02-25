"""Gemeinsame UI-Funktionen für Creator und Optimizer."""

import streamlit as st
from core.db.case_store import case_store
from app.service.optimization_service import StructureValidation


def show_structure_status(v: StructureValidation) -> None:
    """Zeigt das Ergebnis einer StructureValidation als Streamlit-UI an."""
    if v.errors:
        st.error("**Fehler:** " + " | ".join(v.errors))
    elif v.warnings:
        st.warning("✅ Bereit | " + " | ".join(v.warnings))
    else:
        st.success("✅ Bereit")


PNG_EXPORT_SETTINGS = dict(format="png", width=1600, height=600, scale=2)


@st.dialog("Bild speichern")
def png_save_dialog(png_bytes: bytes, default_name: str = "struktur"):
    """Dialog-Popup zum Speichern eines PNG mit Dateinameneingabe."""
    name = st.text_input("Dateiname", value=default_name)
    st.download_button(
        label="📥 Herunterladen",
        data=png_bytes,
        file_name=f"{name}.png",
        mime="image/png",
        width='stretch',
    )


@st.dialog("Struktur speichern")
def structure_save_dialog(default_name: str = "Balken"):
    """Dialog-Popup zum Speichern der aktuellen Struktur."""
    name = st.text_input("Name", value=default_name)
    if st.button("💾 Speichern", type="primary", width='stretch'):
        structure = st.session_state.get("structure")
        if not structure:
            st.error("Keine Struktur vorhanden.")
        else:
            try:
                case_store.save_case(name, structure, st.session_state.history)
                st.success(f"'{name}' gespeichert.")
            except ValueError as e:
                st.error(str(e))


@st.dialog("GIF speichern")
def gif_save_dialog(gif_bytes: bytes, default_name: str = "optimierung"):
    """Dialog-Popup zum Speichern eines GIF mit Dateinameneingabe."""
    name = st.text_input("Dateiname", value=default_name)
    st.download_button(
        label="📥 Herunterladen",
        data=gif_bytes,
        file_name=f"{name}.gif",
        mime="image/gif",
        width='stretch',
    )
