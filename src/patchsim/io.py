"""Readers for candidate patches, gold patches and test outcomes."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

_PATCH_KEYS = ("patch", "model_patch", "diff")
_SYSTEM_KEYS = ("model", "system", "model_name_or_path")


@dataclass
class Candidate:
    """One candidate patch: the instance it is for, the system that wrote it and
    the unified diff."""

    instance_id: str
    system: str
    patch: str


def _read(path: str | Path) -> str:
    """The text of a UTF-8 file; a decoding error names the file."""
    try:
        return Path(path).read_text(encoding="utf-8")
    except UnicodeDecodeError as e:
        raise ValueError(f"{path}: not UTF-8 text (byte {e.start})") from e


def _records(path: str | Path) -> list[tuple[int, dict]]:
    """(line number, row) pairs of a JSONL file, or of a JSON file holding a list of
    objects (numbered by position, from 1). Malformed input raises ValueError naming
    the file and line."""
    text = _read(path)
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
    ``diff``). ``system`` overrides or fills in the system name. A missing or null
    diff is an empty patch; a diff that is not a string, or a second row for the
    same system and instance, raises ValueError naming the file and line."""
    out = []
    seen: dict[tuple[str, str], int] = {}
    for n, row in _records(path):
        _require(path, n, row, "instance_id")
        name = str(system or _first(row, _SYSTEM_KEYS, "candidate"))
        iid = str(row["instance_id"])
        key = next((k for k in _PATCH_KEYS if row.get(k) is not None), "patch")
        patch = row.get(key) or ""
        if not isinstance(patch, str):
            raise ValueError(f"{path}:{n}: '{key}' must be a string, got {type(patch).__name__}")
        if (name, iid) in seen:
            raise ValueError(
                f"{path}:{n}: duplicate candidate for system {name!r} and instance {iid!r} "
                f"(first at line {seen[(name, iid)]})"
            )
        seen[(name, iid)] = n
        out.append(Candidate(iid, name, patch))
    return out


def load_gold(path: str | Path) -> dict[str, str]:
    """Gold patches keyed by instance id, from JSONL or a JSON list with
    ``instance_id`` and ``patch`` (the SWE-bench dataset layout)."""
    out: dict[str, str] = {}
    for n, row in _records(path):
        _require(path, n, row, "instance_id", "patch")
        iid = str(row["instance_id"])
        if iid in out:
            raise ValueError(f"{path}:{n}: duplicate instance {iid!r}")
        if not isinstance(row["patch"], str):
            raise ValueError(f"{path}:{n}: 'patch' must be a string")
        out[iid] = row["patch"]
    return out


def load_outcomes(path: str | Path) -> dict[tuple[str | None, str], bool]:
    """Test-based outcomes keyed by (system or None, instance id).

    Accepts JSONL rows ``{"instance_id", "resolved", "model"?}`` or a JSON object
    with a ``resolved`` list of ids; in the second form the ids are resolved for
    every system and any other scored instance counts as unresolved (key system
    None, instance id '*' marks this).
    """
    text = _read(path).lstrip()
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
        key = (str(name) if name is not None else None, str(row["instance_id"]))
        if key in out:
            raise ValueError(f"{path}:{n}: duplicate outcome for {key[1]!r}")
        out[key] = _flag(path, n, row["resolved"])
    return out


def system_free(outcomes: dict[tuple[str | None, str], bool]) -> bool:
    """True when some outcome carries no system name and so applies to every system."""
    return any(k[0] is None for k in outcomes)


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
    """The outcome of one candidate: its own (system, instance) entry, else the
    system-free entry for the instance, else the default of a results-JSON list
    (unresolved), else None (unknown)."""
    for key in ((system, instance_id), (None, instance_id)):
        if key in outcomes:
            return outcomes[key]
    return outcomes.get((None, "*"))
