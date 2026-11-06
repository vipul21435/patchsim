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


def _records(path: str | Path) -> list[tuple[int, dict]]:
    """(line number, row) pairs of a JSONL file, or of a JSON file holding a list of
    objects (numbered by position, from 1). Malformed input raises ValueError naming
    the file and line."""
    text = Path(path).read_text(encoding="utf-8")
    stripped = text.lstrip()
    if stripped.startswith("["):
        try:
            data = json.loads(text)
        except json.JSONDecodeError as e:
            raise ValueError(f"{path}:{e.lineno}: {e.msg}") from e
        if not all(isinstance(r, dict) for r in data):
            raise ValueError(f"{path}: expected a list of objects")
        return list(enumerate(data, 1))
    rows = []
    for n, line in enumerate(text.splitlines(), 1):
        if line.strip():
            try:
                row = json.loads(line)
            except json.JSONDecodeError as e:
                raise ValueError(f"{path}:{n}: {e.msg}") from e
            if not isinstance(row, dict):
                raise ValueError(f"{path}:{n}: expected a JSON object")
            rows.append((n, row))
    return rows


def _require(path: str | Path, n: int, row: dict, *keys: str) -> None:
    for k in keys:
        if row.get(k) is None:
            raise ValueError(f"{path}:{n}: missing '{k}'")


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
    for n, row in _records(path):
        _require(path, n, row, "instance_id")
        name = system or _first(row, _SYSTEM_KEYS, "candidate")
        out.append(Candidate(str(row["instance_id"]), str(name), str(_first(row, _PATCH_KEYS, ""))))
    return out


def load_gold(path: str | Path) -> dict[str, str]:
    """Gold patches keyed by instance id, from JSONL or a JSON list with
    ``instance_id`` and ``patch`` (the SWE-bench dataset layout)."""
    out = {}
    for n, row in _records(path):
        _require(path, n, row, "instance_id", "patch")
        out[str(row["instance_id"])] = str(row["patch"])
    return out


def load_outcomes(path: str | Path) -> dict[tuple[str | None, str], bool]:
    """Test-based outcomes keyed by (system or None, instance id).

    Accepts JSONL rows ``{"instance_id", "resolved", "model"?}`` or a JSON object
    with a ``resolved`` list of ids; in the second form the ids are resolved for
    every system and any other scored instance counts as unresolved (key system
    None, instance id '*' marks this).
    """
    text = Path(path).read_text(encoding="utf-8").lstrip()
    if text.startswith("{") and "\n{" not in text.strip():
        try:
            data = json.loads(text)
        except json.JSONDecodeError as e:
            raise ValueError(f"{path}:{e.lineno}: {e.msg}") from e
        if isinstance(data, dict) and isinstance(data.get("resolved"), list):
            out: dict[tuple[str | None, str], bool] = {(None, "*"): False}
            out.update({(None, str(i)): True for i in data["resolved"]})
            return out
    out = {}
    for n, row in _records(path):
        _require(path, n, row, "instance_id", "resolved")
        name = _first(row, _SYSTEM_KEYS)
        out[(str(name) if name is not None else None, str(row["instance_id"]))] = _flag(
            path, n, row["resolved"]
        )
    return out


def _flag(path: str | Path, n: int, value: object) -> bool:
    """A resolved flag: JSON true/false, or the numbers 0 and 1. Strings such as
    "false" are rejected rather than read as true."""
    if isinstance(value, bool):
        return value
    if isinstance(value, int) and value in (0, 1):
        return bool(value)
    raise ValueError(f"{path}:{n}: 'resolved' must be true, false, 0 or 1, got {value!r}")


def outcome_for(
    outcomes: dict[tuple[str | None, str], bool], system: str, instance_id: str
) -> bool | None:
    for key in ((system, instance_id), (None, instance_id)):
        if key in outcomes:
            return outcomes[key]
    return outcomes.get((None, "*"))
