from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional
from uuid import uuid4

from tinydb import TinyDB, Query

from core.io.structure_codec import structure_from_dict, structure_to_dict
from core.model.structure import Structure


@dataclass(slots=True)
class CaseMeta:
    case_id: str
    name: str
    created_at: str


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _history_to_dict(history: Any) -> Optional[dict[str, Any]]:
    if history is None:
        return None

    required = ("mass_fraction", "removed_per_iter", "active_nodes", "max_displacement")
    if not all(hasattr(history, k) for k in required):
        return None

    return {
        "mass_fraction": list(history.mass_fraction),
        "removed_per_iter": list(history.removed_per_iter),
        "active_nodes": list(history.active_nodes),
        "max_displacement": list(history.max_displacement),
    }


def _history_from_dict(data: Optional[dict[str, Any]]) -> Any:
    if data is None:
        return None

    try:
        from core.optimization.energy_based_optimizer import OptimizationHistory
    except Exception:
        return data

    return OptimizationHistory(
        mass_fraction=list(data.get("mass_fraction", [])),
        removed_per_iter=list(data.get("removed_per_iter", [])),
        active_nodes=list(data.get("active_nodes", [])),
        max_displacement=list(data.get("max_displacement", [])),
    )


class CaseStore:
    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)

    def _open(self) -> TinyDB:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        return TinyDB(self.db_path)

    def save_case(self, name: str, structure: Structure, history: Any = None) -> str:
        case_id = uuid4().hex
        doc = {
            "case_id": case_id,
            "name": str(name).strip() or "unnamed",
            "created_at": _now_iso(),
            "structure": structure_to_dict(structure),
            "history": _history_to_dict(history),
        }

        with self._open() as db:
            db.insert(doc)

        return case_id

    def list_cases(self) -> list[CaseMeta]:
        with self._open() as db:
            docs = db.all()

        metas: list[CaseMeta] = []
        for d in docs:
            metas.append(
                CaseMeta(
                    case_id=str(d.get("case_id", "")),
                    name=str(d.get("name", "")),
                    created_at=str(d.get("created_at", "")),
                )
            )

        metas.sort(key=lambda m: m.created_at, reverse=True)
        return metas

    def load_case(self, case_id: str) -> tuple[Structure, Any]:
        q = Query()
        with self._open() as db:
            doc = db.get(q.case_id == case_id)

        if doc is None:
            raise KeyError(f"Case not found: {case_id}")

        structure = structure_from_dict(doc["structure"])
        history = _history_from_dict(doc.get("history"))
        return structure, history

    def delete_case(self, case_id: str) -> bool:
        q = Query()
        with self._open() as db:
            removed = db.remove(q.case_id == case_id)
        return len(removed) > 0
