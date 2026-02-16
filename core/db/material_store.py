from dataclasses import dataclass
from tinydb import Query
from core.database import db_manager


@dataclass(slots=True)
class MaterialMeta:
    """Metadaten für ein gespeichertes Material."""
    name: str
    e_modul: float
    streckgrenze: float


class MaterialStore:
    """
    Store für Material-Daten.
    Name ist der eindeutige Schlüssel - jedes Material kann nur einmal existieren.
    """
    
    def __init__(self):
        self.table_name = 'materials'
    
    def _get_table(self):
        """Gibt Material-Tabelle zurück."""
        return db_manager.get_table(self.table_name)
    
    def save_material(self, name, e_modul, streckgrenze):
        """
        Speichert ein Material in der Datenbank.
        
        Args:
            name: Name des Materials (eindeutiger Schlüssel)
            e_modul: E-Modul in GPa
            streckgrenze: Streckgrenze in MPa
        
        Returns:
            name: Der Name des gespeicherten Materials
        
        Raises:
            ValueError: Wenn Material mit diesem Namen bereits existiert oder Name leer ist
        """
        table = self._get_table()
        Material = Query()
        
        name = str(name).strip()
        if not name:
            raise ValueError("Material-Name darf nicht leer sein!")
        
        existing = table.get(Material.name == name)
        
        if existing:
            raise ValueError(f"Material '{name}' existiert bereits! Bitte wähle einen anderen Namen.")
        
        doc = {
            "name": name,
            "e_modul": float(e_modul),
            "streckgrenze": float(streckgrenze),
        }
        
        table.insert(doc)
        
        return name
    
    def list_materials(self):
        """
        Listet alle gespeicherten Materialien auf.
        
        Returns:
            Liste von MaterialMeta Objekten, sortiert nach Name
        """
        table = self._get_table()
        docs = table.all()
        
        metas = []
        for d in docs:
            metas.append(
                MaterialMeta(
                    name=str(d.get("name", "")),
                    e_modul=float(d.get("e_modul", 0.0)),
                    streckgrenze=float(d.get("streckgrenze", 0.0)),
                )
            )
        
        metas.sort(key=lambda m: m.name)
        return metas
    
    def load_material(self, name):
        """
        Lädt ein Material aus der Datenbank.
        
        Args:
            name: Name des Materials
        
        Returns:
            MaterialMeta Objekt
        
        Raises:
            KeyError: Wenn Material nicht gefunden wurde
        """
        table = self._get_table()
        Material = Query()
        doc = table.get(Material.name == name)
        
        if doc is None:
            raise KeyError(f"Material '{name}' nicht gefunden!")
        
        return MaterialMeta(
            name=str(doc.get("name", "")),
            e_modul=float(doc.get("e_modul", 0.0)),
            streckgrenze=float(doc.get("streckgrenze", 0.0)),
        )
    
    def delete_material(self, name):
        """
        Löscht ein Material aus der Datenbank.
        
        Args:
            name: Name des zu löschenden Materials
        
        Returns:
            True wenn Material gelöscht wurde, False wenn nicht gefunden
        """
        table = self._get_table()
        Material = Query()
        removed = table.remove(Material.name == name)
        
        return len(removed) > 0


# Singleton-Instanz
material_store = MaterialStore()