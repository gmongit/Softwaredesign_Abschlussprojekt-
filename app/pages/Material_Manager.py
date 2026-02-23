import streamlit as st
from core.db.material_store import material_store


st.title("🧪 Material Manager")


@st.dialog("Material löschen")
def show_delete_dialog():
    materials = material_store.list_materials()
    if not materials:
        st.info("Keine Materialien vorhanden.")
        return
    to_delete = st.selectbox("Material auswählen", [m.name for m in materials])
    if st.button("🗑️ Löschen", type="primary", width='stretch'):
        material_store.delete_material(to_delete)
        st.rerun()


@st.dialog("Material bearbeiten")
def show_edit_dialog():
    materials = material_store.list_materials()
    if not materials:
        st.info("Keine Materialien vorhanden.")
        return
    to_edit = st.selectbox("Material auswählen", [m.name for m in materials])
    mat = next(m for m in materials if m.name == to_edit)

    new_name = st.text_input("Name", value=mat.name)
    e_modul = st.number_input("E-Modul in GPa", value=mat.e_modul)
    streckgrenze = st.number_input("Streckgrenze in MPa", value=mat.streckgrenze)
    dichte = st.number_input("Dichte in kg/m³", value=mat.dichte)

    if st.button("💾 Speichern", type="primary", width='stretch'):
        try:
            material_store.edit_material(to_edit, new_name, e_modul, streckgrenze, dichte)
            st.rerun()
        except (KeyError, ValueError) as e:
            st.error(str(e))


with st.form("material_form", clear_on_submit=True):
    name = st.text_input("Material-Name *", placeholder="z.B. Steel S235")
    e_modul = st.number_input("E-Modul in GPa", value=210.0)
    streckgrenze = st.number_input("Streckgrenze in MPa", value=235.0)
    dichte = st.number_input("Dichte in kg/m³", value=7850.0)

    col1, col2, col3 = st.columns(3)
    with col1:
        submitted = st.form_submit_button("✅ Hinzufügen", width='stretch')
    with col2:
        edit_clicked = st.form_submit_button("✏️ Bearbeiten", width='stretch')
    with col3:
        delete_clicked = st.form_submit_button("🗑️ Löschen", width='stretch')

if submitted:
    try:
        material_store.save_material(name, e_modul, streckgrenze, dichte)
        st.success(f"Material '{name}' gespeichert!")
    except ValueError as e:
        st.error(str(e))

if edit_clicked:
    show_edit_dialog()

if delete_clicked:
    show_delete_dialog()


st.markdown("---")
st.subheader("Alle Materialien")

materials = material_store.list_materials()

if materials:
    st.dataframe(
        [
            {
                "Name": m.name,
                "E-Modul (GPa)": m.e_modul,
                "Streckgrenze (MPa)": m.streckgrenze,
                "Dichte (kg/m³)": m.dichte,
            }
            for m in materials
        ],
        width='stretch',
        hide_index=True,
    )
    st.caption(f"📊 Gesamt: {len(materials)} Materialien")
else:
    st.info("Noch keine Materialien vorhanden.")
