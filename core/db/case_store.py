from dataclasses import dataclass
from datetime import datetime, timezone
from tinydb import Query

from core.db.database import db_manager
from core.io.structure_codec import structure_from_dict, structure_to_dict
from core.model.structure import Structure


@dataclass(slots=True)
class CaseMeta:    
    """Metadaten für einen gespeicherten Case."""
    name: str
    created_at: str


def _now_iso():
    """Gibt jetzigen Zeitpunkt als ISO_String zurück"""
    return datetime.now(timezone.utc).isoformat()


def _history_to_dict(history):
    """Konvertiert OptimizationHistory zu dict."""
    if history is None:
        return None

    required = ("mass_fraction", "removed_per_iter", "active_nodes", "max_displacement")
    if not all(hasattr(history, k) for k in required):
        return None

    return {
        "mass_fraction": list(history.mass_fraction),
        "removed_per_iter": list(history.removed_per_iter),
        "removed_nodes_per_iter": [list(x) for x in getattr(history, "removed_nodes_per_iter", [])],
        "active_nodes": list(history.active_nodes),
        "max_displacement": list(history.max_displacement),
    }


def _history_from_dict(data):
    """Rekonstruiert OptimizationHistory aus dict."""
    if data is None:
        return None

    try:
        from core.optimization.energy_based_optimizer import OptimizationHistory
    except Exception:
        return data

    return OptimizationHistory(
        mass_fraction=list(data.get("mass_fraction", [])),
        removed_per_iter=list(data.get("removed_per_iter", [])),
        removed_nodes_per_iter=[list(x) for x in data.get("removed_nodes_per_iter", [])],
        active_nodes=list(data.get("active_nodes", [])),
        max_displacement=list(data.get("max_displacement", [])),
    )


class CaseStore:
    """
    Store für Case-Daten (Strukturen mit History).
    Name ist der eindeutige Schlüssel - jeder Case kann nur einmal existieren.
    """
    
    def __init__(self):
        """Initialisiert den CaseStore."""
        self.table_name = 'cases'
    
    def _get_table(self):
        """Gibt die Cases-Tabelle zurück."""
        return db_manager.get_table(self.table_name)
    
    def save_case(self, name, structure, history=None):
        """
        Speichert einen Case in der Datenbank.
        
        Args:
            name: Name des Cases (eindeutiger Schlüssel)
            structure: Structure Objekt
            history: Optionale OptimizationHistory
        
        Returns:
            name: Der Name des gespeicherten Cases
        
        Raises:
            ValueError: Wenn Case mit diesem Namen bereits existiert
        """
        table = self._get_table()
        Case = Query()

        name = str(name).strip()
        if not name:
            raise ValueError("Case-Name darf nicht leer sein!")
        
        # Prüfe ob Case schon existiert
        existing = table.get(Case.name == name)
        
        if existing:
            raise ValueError(f"Case '{name}' existiert bereits! Bitte wähle einen anderen Namen.")
        
        doc = {
            "name": str(name).strip() or "unnamed",
            "created_at": _now_iso(),
            "structure": structure_to_dict(structure),
            "history": _history_to_dict(history),
        }
        
        table.insert(doc)
        
        return name
    
    def rename_case(self, old_name, new_name):
        """
        Benennt einen Case um.
        
        Args:
            old_name: Aktueller Name des Cases
            new_name: Neuer Name des Cases
        
        Returns:
            new_name: Der neue Name des Cases
        
        Raises:
            KeyError: Wenn alter Name nicht gefunden wurde
            ValueError: Wenn neuer Name bereits existiert
        """
        table = self._get_table()
        Case = Query()
        
        # Prüfe ob alter Case existiert
        old_doc = table.get(Case.name == old_name)
        if old_doc is None:
            raise KeyError(f"Case '{old_name}' nicht gefunden!")
        
        # Prüfe ob neuer Name schon existiert
        new_exists = table.get(Case.name == new_name)
        if new_exists:
            raise ValueError(f"Case '{new_name}' existiert bereits! Bitte wähle einen anderen Namen.")
        
        # Update: Ändere nur den Namen, behalte alles andere
        table.update({'name': str(new_name).strip()}, Case.name == old_name)
        
        return new_name

    def list_cases(self):
        """
        Listet alle gespeicherten Cases auf.
        
        Returns:
            Liste von CaseMeta Objekten, sortiert nach Erstellungsdatum (neueste zuerst)
        """
        table = self._get_table()
        docs = table.all()
        
        metas = []
        for d in docs:
            metas.append(
                CaseMeta(
                    name=str(d.get("name", "")),
                    created_at=str(d.get("created_at", "")),
                )
            )
        
        metas.sort(key=lambda m: m.created_at, reverse=True)
        return metas

    def load_case(self, name):
        """
        Lädt einen Case aus der Datenbank.
        
        Args:
            name: Name des Cases
        
        Returns:
            (structure, history): Tuple mit Structure und OptimizationHistory
        
        Raises:
            KeyError: Wenn Case nicht gefunden wurde
        """
        table = self._get_table()
        Case = Query()
        doc = table.get(Case.name == name)
        
        if doc is None:
            raise KeyError(f"Case '{name}' nicht gefunden!")

        doc = dict(doc)
        structure = structure_from_dict(doc["structure"])
        history = _history_from_dict(doc.get("history"))
        
        return structure, history

    def delete_case(self, name):
        """
        Löscht einen Case aus der Datenbank.
        
        Args:
            name: Name des zu löschenden Cases
        
        Returns:
            True wenn Case gelöscht wurde, False wenn nicht gefunden
        """
        table = self._get_table()
        Case = Query()
        removed = table.remove(Case.name == name)
        
        return len(removed) > 0
    
    def case_exists(self, name):
        """
        Prüft ob ein Case existiert.
        
        Args:
            name: Name des Cases
        
        Returns:
            True wenn Case existiert, False sonst
        """
        table = self._get_table()
        Case = Query()
        return table.contains(Case.name == name)


# Singleton-Instanz
case_store = CaseStore()