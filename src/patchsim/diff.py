"""Parse unified diffs into files, hunks and touched positions in the original file."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

_HUNK_RE = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@ ?(.*)$")
_DEF_RE = re.compile(r"^\s*(?:async\s+)?def\s+([A-Za-z_]\w*)")


@dataclass
class Hunk:
    """One hunk. ``lines`` holds (tag, text) with tag in {' ', '-', '+'}."""

    old_start: int
    old_len: int
    new_start: int
    new_len: int
    header: str = ""
    lines: list[tuple[str, str]] = field(default_factory=list)


@dataclass
class FilePatch:
    """All hunks for one file. ``path`` is the post-patch path, or the old one for deletions."""

    old_path: str | None
    new_path: str | None
    hunks: list[Hunk] = field(default_factory=list)

    @property
    def path(self) -> str:
        return self.new_path if self.new_path is not None else (self.old_path or "")

    @property
    def added(self) -> list[str]:
        return [t for h in self.hunks for tag, t in h.lines if tag == "+"]

    @property
    def removed(self) -> list[str]:
        return [t for h in self.hunks for tag, t in h.lines if tag == "-"]

    def added_new_lines(self) -> list[int]:
        """Line numbers, in the post-patch file, of the added lines."""
        out = []
        for h in self.hunks:
            new_no = h.new_start if h.new_len else h.new_start + 1
            for tag, _ in h.lines:
                if tag == "+":
                    out.append(new_no)
                if tag != "-":
                    new_no += 1
        return out

    def touched_positions(self) -> set[int]:
        """Positions in the original file touched by this patch.

        Original line ``n`` is position ``2n``; the gap after original line ``k``
        (where a pure insertion lands) is position ``2k + 1``. A block of changed
        lines between two context lines touches the positions of its removed lines,
        or, if it removes nothing, the single gap where its added lines go.
        """
        out: set[int] = set()
        for h in self.hunks:
            old_no = h.old_start
            removed: list[int] = []
            added = False
            gap = h.old_start - 1
            for tag, _ in [*h.lines, (" ", "")]:
                if tag == " ":
                    if removed:
                        out.update(2 * n for n in removed)
                    elif added:
                        out.add(2 * gap + 1)
                    removed, added = [], False
                    gap = old_no
                    old_no += 1
                elif tag == "-":
                    removed.append(old_no)
                    old_no += 1
                elif tag == "+":
                    added = True
        return out

    def changed_functions(self) -> set[str]:
        """Names of Python functions enclosing changed lines, read from the patch alone.

        For each changed line the name is the closest preceding ``def`` line inside
        the hunk (context, removed or added), falling back to the function named in
        the hunk header. This is a heuristic: nested functions and decorators that
        precede a ``def`` are not resolved, and lines outside any visible function
        are skipped.
        """
        names: set[str] = set()
        for h in self.hunks:
            m = _DEF_RE.match(h.header)
            current = m.group(1) if m else None
            for tag, text in h.lines:
                m = _DEF_RE.match(text)
                if m:
                    current = m.group(1)
                if tag in "+-" and current is not None:
                    names.add(current)
        return names


@dataclass
class Patch:
    files: list[FilePatch] = field(default_factory=list)

    @property
    def paths(self) -> set[str]:
        return {f.path for f in self.files}

    def by_path(self) -> dict[str, FilePatch]:
        return {f.path: f for f in self.files}

    @property
    def n_added(self) -> int:
        return sum(len(f.added) for f in self.files)

    @property
    def n_removed(self) -> int:
        return sum(len(f.removed) for f in self.files)

    def without_new_files(self, keep: set[str]) -> tuple[Patch, list[str]]:
        """A copy without the files this patch creates (no old path), except those in
        ``keep``; also returns the dropped paths. Used to set aside scratch scripts
        that agents add to a repository and leave in their final diff."""
        kept, dropped = [], []
        for f in self.files:
            if f.old_path is None and f.path not in keep:
                dropped.append(f.path)
            else:
                kept.append(f)
        return Patch(kept), sorted(dropped)


@dataclass
class AppliedFile:
    """A file patch applied to its pre-patch text, with the line numbers (from 1)
    of the removed lines in ``pre`` and of the added lines in ``post``, taken from
    where each hunk actually matched."""

    pre: str
    post: str
    removed_lines: list[int]
    added_lines: list[int]


def apply_file_patch_lines(
    source: str, fp: FilePatch, max_offset: int | None = None
) -> AppliedFile | None:
    """Apply the hunks of ``fp`` to ``source``; see :func:`apply_file_patch`.

    Returns the pre- and post-patch text and the changed line numbers, or None
    if some hunk matches nowhere.
    """
    src = source.splitlines()
    out: list[str] = []
    removed: list[int] = []
    added: list[int] = []
    pos = 0
    for h in fp.hunks:
        old = [t for tag, t in h.lines if tag != "+"]
        want = max(h.old_start - 1, pos)
        limit = len(src) if max_offset is None else max_offset
        found = None
        for d in range(0, limit + 1):
            for at in (want - d, want + d) if d else (want,):
                window = src[at : at + len(old)]
                if pos <= at <= len(src) - len(old) and all(
                    a.rstrip() == b.rstrip() for a, b in zip(window, old, strict=True)
                ):
                    found = at
                    break
            if found is not None:
                break
        if found is None:
            return None
        out += src[pos:found]
        old_no = found
        for tag, t in h.lines:
            if tag != "+":
                old_no += 1
            if tag != "-":
                out.append(t)
            if tag == "-":
                removed.append(old_no)
            elif tag == "+":
                added.append(len(out))
        pos = found + len(old)
    out += src[pos:]
    return AppliedFile(source, "\n".join(out) + ("\n" if out else ""), removed, added)


def apply_file_patch(source: str, fp: FilePatch, max_offset: int | None = None) -> str | None:
    """Apply the hunks of ``fp`` to ``source`` and return the post-patch text.

    Each hunk is placed where its context and removed lines match the source
    exactly (trailing whitespace ignored), at the stated line or at the nearest
    offset from it, searching up to ``max_offset`` lines either way (default: the
    whole file). Returns None if some hunk matches nowhere. No fuzz is applied.
    """
    applied = apply_file_patch_lines(source, fp, max_offset)
    return None if applied is None else applied.post


def _strip_prefix(p: str) -> str | None:
    p = p.split("\t", 1)[0].strip()
    if p == "/dev/null":
        return None
    if p.startswith(("a/", "b/")):
        return p[2:]
    return p


def _starts_file(lines: list[str], i: int) -> bool:
    """True when line i begins a new file even inside a hunk whose line counts are
    too large, as hand-written and model-written diffs often have: a ``diff --git``
    line, or a ``---``/``+++`` pair followed by a hunk header."""
    line = lines[i]
    if line.startswith("diff --git "):
        return True
    return (
        line.startswith("--- ")
        and i + 2 < len(lines)
        and lines[i + 1].startswith("+++ ")
        and lines[i + 2].startswith("@@ ")
    )


def parse_diff(text: str) -> Patch:
    """Parse a unified diff (git or plain) into a :class:`Patch`.

    Binary files and mode-only changes produce a file entry with no hunks.
    Malformed hunk bodies stop at the first line that is not ' ', '-', '+' or '\\'.
    """
    patch = Patch()
    cur: FilePatch | None = None
    hunk: Hunk | None = None
    old_left = new_left = 0
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        if hunk is not None and (old_left > 0 or new_left > 0) and not _starts_file(lines, i):
            if line.startswith("\\"):
                i += 1
                continue
            tag = line[:1] if line else " "
            if tag in (" ", "-", "+"):
                hunk.lines.append((tag, line[1:]))
                if tag != "+":
                    old_left -= 1
                if tag != "-":
                    new_left -= 1
                i += 1
                continue
            hunk = None
        if line.startswith("diff --git "):
            parts = line.split()
            a = _strip_prefix(parts[2]) if len(parts) > 2 else None
            b = _strip_prefix(parts[3]) if len(parts) > 3 else None
            cur = FilePatch(a, b)
            patch.files.append(cur)
            hunk = None
        elif line.startswith("new file mode") and cur is not None and not cur.hunks:
            cur.old_path = None
        elif line.startswith("deleted file mode") and cur is not None and not cur.hunks:
            cur.new_path = None
        elif line.startswith("--- ") and i + 1 < len(lines) and lines[i + 1].startswith("+++ "):
            old = _strip_prefix(line[4:])
            new = _strip_prefix(lines[i + 1][4:])
            if cur is None or cur.hunks:
                cur = FilePatch(old, new)
                patch.files.append(cur)
            else:
                cur.old_path, cur.new_path = old, new
            i += 2
            continue
        elif line.startswith("@@"):
            m = _HUNK_RE.match(line)
            if m and cur is not None:
                os_, ol, ns, nl, hdr = m.groups()
                hunk = Hunk(
                    int(os_),
                    int(ol) if ol is not None else 1,
                    int(ns),
                    int(nl) if nl is not None else 1,
                    hdr.strip(),
                )
                # A zero-length old side means the hunk inserts after line old_start.
                if hunk.old_len == 0:
                    hunk.old_start += 1
                cur.hunks.append(hunk)
                old_left, new_left = hunk.old_len, hunk.new_len
        i += 1
    patch.files = _merge_sections(patch.files)
    return patch


def _merge_sections(files: list[FilePatch]) -> list[FilePatch]:
    """One entry per path: the hunks of later sections that name an earlier path
    are added to the first section for it and sorted by original line, so a
    candidate that edits one file in several ``diff --git`` sections is scored
    and applied as one file patch. The first section's old and new paths are kept."""
    merged: dict[str, FilePatch] = {}
    for f in files:
        first = merged.get(f.path)
        if first is None:
            merged[f.path] = f
        else:
            first.hunks.extend(f.hunks)
            first.hunks.sort(key=lambda h: h.old_start)
    return list(merged.values())
