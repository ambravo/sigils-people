"""LDIF encoding and decoding (RFC 2849) and DN escaping (RFC 4514).

Standard library only. Two rules keep the output byte-identical on every run:

* A value is written as plain text only when RFC 2849's SAFE-STRING rules allow
  it. Anything else goes base64 (``attr:: ...``): a leading space, colon or
  ``<``; a trailing space; NUL, LF or CR; and every non-ASCII byte. RFC 2849
  does not allow raw UTF-8 in a plain value, so names such as ``刘`` or
  ``فاطمة`` are always base64 here.
* Lines are folded at 76 characters. Continuation lines start with one space.
  Output is ASCII only, so folding by character cannot split a UTF-8 sequence.
"""

from __future__ import annotations

import base64

MAX_LINE = 76

_SPACE, _COLON, _LESS = 0x20, 0x3A, 0x3C


def needs_base64(value: str) -> bool:
    """True when ``value`` cannot be written as a plain LDIF value."""
    data = value.encode("utf-8")
    if not data:
        return False
    if data[0] in (_SPACE, _COLON, _LESS) or data[-1] == _SPACE:
        return True
    return any(b == 0 or b == 10 or b == 13 or b > 127 for b in data)


def fold(line: str) -> str:
    """Fold one ASCII line to 76 characters, continuation lines start with a space."""
    if len(line) <= MAX_LINE:
        return line
    parts = [line[:MAX_LINE]]
    rest = line[MAX_LINE:]
    while rest:
        parts.append(" " + rest[: MAX_LINE - 1])
        rest = rest[MAX_LINE - 1 :]
    return "\n".join(parts)


def encode_attr(name: str, value: str) -> str:
    """One ``name: value`` pair, base64 and folded as needed. No trailing newline."""
    if needs_base64(value):
        encoded = base64.b64encode(value.encode("utf-8")).decode("ascii")
        return fold(f"{name}:: {encoded}")
    if value == "":
        return f"{name}:"
    return fold(f"{name}: {value}")


_DN_SPECIALS = ',+"\\<>;'


def escape_dn_value(value: str) -> str:
    """Escape one attribute value for use inside a DN (RFC 4514 section 2.4)."""
    out = []
    last = len(value) - 1
    for i, ch in enumerate(value):
        if ch in _DN_SPECIALS:
            out.append("\\" + ch)
        elif ch == "#" and i == 0:
            out.append("\\#")
        elif ch == " " and (i == 0 or i == last):
            out.append("\\ ")
        elif ch == "\x00":
            out.append("\\00")
        else:
            out.append(ch)
    return "".join(out)


def make_dn(rdns: list[tuple[str, str]]) -> str:
    """Build a DN from (attribute, value) pairs, leftmost first."""
    return ",".join(f"{attr}={escape_dn_value(value)}" for attr, value in rdns)


def parse_ldif(text: str) -> list[list[tuple[str, str]]]:
    """Parse LDIF into entries of (attribute, value) pairs, in file order.

    Enough of RFC 2849 for this project's output: comments, folding, base64
    values and blank-line separators. Change records are not supported.
    """
    logical: list[str] = []
    for raw in text.split("\n"):
        if raw.startswith("#"):
            continue
        if raw.startswith(" "):
            if not logical:
                raise ValueError("continuation line with nothing before it")
            logical[-1] += raw[1:]
        else:
            logical.append(raw)

    entries: list[list[tuple[str, str]]] = []
    current: list[tuple[str, str]] = []
    for line in logical:
        if line == "":
            if current:
                entries.append(current)
                current = []
            continue
        if ":" not in line:
            raise ValueError(f"not an LDIF line: {line!r}")
        name, _, rest = line.partition(":")
        if rest.startswith(":"):
            value = base64.b64decode(rest[1:].strip(), validate=True).decode("utf-8")
        else:
            value = rest[1:] if rest.startswith(" ") else rest
        current.append((name, value))
    if current:
        entries.append(current)
    # "version: 1" opens an LDIF file as a block of its own; it is not an entry.
    if entries and entries[0] == [("version", "1")]:
        entries.pop(0)
    return entries
