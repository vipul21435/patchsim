"""Readers for candidate patches, gold patches and test outcomes."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

_PATCH_KEYS = ("patch", "model_patch", "diff")
_SYSTEM_KEYS = ("model", "system", "model_name_or_path")


@dataclass
class Candidate:
    instance_id: str
    system: str
    patch: str


def _records(path: str | Path) -> list[dict]:
    """Rows of a JSONL file, or of a JSON file holding a list of objects."""
    text = Path(path).read_text(encoding="utf-8")
    stripped = text.lstrip()
    if stripped.startswith("["):
        data = json.loads(text)
        if not all(isinstance(r, dict) for r in data):
            raise ValueError(f"{path}: expected a list of objects")
        return data
    rows = []
    for n, line in enumerate(text.splitlines(), 1):
        if line.strip():
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError as e:
                raise ValueError(f"{path}:{n}: {e.msg}") from e
    return rows


def _first(row: dict, keys: tuple[str, ...], default: object = None) -> object:
    for k in keys:
        if k in row and row[k] is not None:
            return row[k]
    return default


def load_candidates(path: str | Path, system: str | None = None) -> list[Candidate]:
    """Candidates from JSONL with ``instance_id``, a system name (``model``,
    ``system`` or ``model_name_or_path``) and a diff (``patch``, ``model_patch`` or
    ``diff``). ``system`` overrides or fills in the system name."""
    out = []
    for row in _records(path):
        name = system or _first(row, _SYSTEM_KEYS, "candidate")
        out.append(Candidate(str(row["instance_id"]), str(name), str(_first(row, _PATCH_KEYS, ""))))
    return out


def load_gold(path: str | Path) -> dict[str, str]:
    """Gold patches keyed by instance id, from JSONL or a JSON list with
    ``instance_id`` and ``patch`` (the SWE-bench dataset layout)."""
    return {str(r["instance_id"]): str(r["patch"]) for r in _records(path)}


def load_outcomes(path: str | Path) -> dict[tuple[str | None, str], bool]:
    """Test-based outcomes keyed by (system or None, instance id).

    Accepts JSONL rows ``{"instance_id", "resolved", "model"?}`` or a JSON object
    with a ``resolved`` list of ids; in the second form the ids are resolved for
    every system and any other scored instance counts as unresolved (key system
    None, instance id '*' marks this).
    """
    text = Path(path).read_text(encoding="utf-8").lstrip()
    if text.startswith("{") and "\n{" not in text.strip():
        data = json.loads(text)
        if isinstance(data, dict) and isinstance(data.get("resolved"), list):
            out: dict[tuple[str | None, str], bool] = {(None, "*"): False}
            out.update({(None, str(i)): True for i in data["resolved"]})
            return out
    out = {}
    for row in _records(path):
        name = _first(row, _SYSTEM_KEYS)
        out[(str(name) if name is not None else None, str(row["instance_id"]))] = bool(
            row["resolved"]
        )
    return out


def outcome_for(
    outcomes: dict[tuple[str | None, str], bool], system: str, instance_id: str
) -> bool | None:
    for key in ((system, instance_id), (None, instance_id)):
        if key in outcomes:
            return outcomes[key]
    return outcomes.get((None, "*"))
