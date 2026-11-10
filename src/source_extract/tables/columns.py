"""source_extract.tables.columns — Header coalesce, units, value alignment."""
from __future__ import annotations

import re
from typing import Any

_VALUE_KEY = re.compile(r"[^A-Za-z0-9]+")

# ``prop @ condition [unit]`` — density @ 25 C, Q @ 10 ppmv, Hf @ 298 K, S @ X=0, …
_AT_PHRASE = re.compile(
    r"(?P<prop>[A-Za-z][A-Za-z0-9_]*)\s*@\s*"
    r"(?P<cond>"
    r"X\s*=\s*[\d,.]+"
    r"|\d+\s*ppmv"
    r"|\d+(?:\.\d+)?\s*K"
    r"|25(?:\s*C)?"
    r"|100(?:\s*C)?"
    r"|298(?:\s*K)?"
    r"|500(?:\s*K)?"
    r"|20(?:\s*C)?"
    r"|T(?:MIN|MAX|[Bb])?"
    r"|T"
    r")"
    # Trailing unit words only (not bare C/K — those start the next column).
    r"(?:\s*(?P<tail>ppmv|ppm(?:\s*\((?:wt|mol)\))?|"
    r"atm/mol(?:\s*frac|/m3|/frac)?|joule/\(mol\s*K\)))?",
    re.IGNORECASE,
)
# Printed unit under a temperature column: ``T, K`` / ``T, C``.
_T_COMMA_UNIT = re.compile(r"\bT,\s*(?P<unit>K|C|F)\b", re.IGNORECASE)
_EQ_UNIT_GROUP = re.compile(r"\(([^)]+)\)\s*$")
_EQ_UNIT_PAIR = re.compile(
    r"([A-Za-z][A-Za-z0-9_]*)\s*-\s*([^,;]+)",
)
_TEMP_KEYS = frozenset(
    {"T", "Tc", "TB", "Tb", "TMIN", "TMAX", "Tmelt", "Tboil"}
)
_UNIT_ONLY = frozenset(
    {
        "k",
        "bar",
        "g/mol",
        "cm3/mol",
        "g/cm3",
        "g/ml",
        "kjoule/mol",
        "kjoule/kg",
        "btu/lb",
        "dynes/cm",
        "mm hg",
        "mmhg",
    }
)



def _clean_header_latex(header_line: str) -> str:
    """Strip common OCR/LaTeX noise from a header line before tokenization."""
    text = header_line
    text = text.replace(r"^\circ", "")
    text = re.sub(r"\\circ", "", text)
    text = re.sub(r"\\text\{?\s*C\}?", "C", text)
    text = re.sub(r"\\text\{([^}]*)\}", r"\1", text)
    text = text.replace("{", " ").replace("}", " ")
    text = re.sub(r"@\s*", "@ ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def coalesce_header_labels(header_line: str | None) -> list[tuple[str, str | None]]:
    """Tokenize a header line into ``(label, unit_hint)`` pairs.

    Merges ``prop @ condition`` into one label. ``T, K`` / ``T, C`` become label
    ``T`` with the matching unit hint.
    """
    if not header_line:
        return []
    text = _clean_header_latex(header_line)

    t_unit_hints: list[str | None] = []

    def _store_t(match: re.Match[str]) -> str:
        unit = match.group("unit").upper()
        if unit == "C":
            unit = "°C"
        t_unit_hints.append(unit)
        return f" __TUNIT{len(t_unit_hints) - 1}__ "

    text = _T_COMMA_UNIT.sub(_store_t, text)

    placeholders: list[str] = []

    def _store_at(match: re.Match[str]) -> str:
        prop = match.group("prop")
        cond = re.sub(r"\s+", " ", match.group("cond").strip())
        tail = match.groupdict().get("tail") or ""
        tail = re.sub(r"\s+", " ", tail.strip())
        if re.fullmatch(r"25", cond, re.IGNORECASE):
            cond = "25 C"
        elif re.fullmatch(r"25\s*C", cond, re.IGNORECASE):
            cond = "25 C"
        elif re.fullmatch(r"100", cond, re.IGNORECASE):
            cond = "100 C"
        elif re.fullmatch(r"100\s*C", cond, re.IGNORECASE):
            cond = "100 C"
        elif re.fullmatch(r"298", cond, re.IGNORECASE):
            cond = "298 K"
        elif re.fullmatch(r"500", cond, re.IGNORECASE):
            cond = "500 K"
        elif re.fullmatch(r"20", cond, re.IGNORECASE):
            cond = "20 C"
        label = f"{prop} @ {cond}"
        if tail and tail.lower() not in cond.lower():
            label = f"{label} {tail}"
        placeholders.append(label)
        return f" __AT{len(placeholders) - 1}__ "

    text = _AT_PHRASE.sub(_store_at, text)
    tokens: list[tuple[str, str | None]] = []
    for tok in text.split():
        m_at = re.fullmatch(r"__AT(\d+)__", tok)
        m_t = re.fullmatch(r"__TUNIT(\d+)__", tok)
        if m_at:
            tokens.append((placeholders[int(m_at.group(1))], None))
        elif m_t:
            tokens.append(("T", t_unit_hints[int(m_t.group(1))]))
        else:
            tokens.append((tok, None))
    return tokens


def header_tokens(header_line: str | None) -> list[str]:
    """Split an OCR header line into column labels (``@`` conditions coalesced)."""
    return [label for label, _unit in coalesce_header_labels(header_line)]


def columns_from_header(header_line: str | None) -> list[dict[str, str | None]]:
    """Return ordered ``[{key, header, unit}, …]`` from an OCR header line.

    Identity columns are always ``id``, ``formula``, ``name``. Remaining header
    tokens (after NO/FORMULA/NAME) become value columns; duplicate labels get
    ``_2``, ``_3``, … key suffixes. Unit hints from ``T, K`` / ``T, C`` are set
    here; equation-based units are filled by ``attach_column_units``.
    """
    tokens = coalesce_header_labels(header_line)
    i = 0
    while i < len(tokens):
        label, _hint = tokens[i]
        low = re.sub(r"[^a-z]", "", label.lower())
        if i < 3 and low in {"no", "mo", "n0", "formula", "name"}:
            i += 1
            continue
        break
    value_labels = tokens[i:]

    columns: list[dict[str, str | None]] = [
        {"key": "id", "header": "NO", "unit": None},
        {"key": "formula", "header": "FORMULA", "unit": None},
        {"key": "name", "header": "NAME", "unit": None},
    ]
    seen: dict[str, int] = {}
    for label, unit_hint in value_labels:
        key = _value_column_key(label)
        n = seen.get(key, 0) + 1
        seen[key] = n
        if n > 1:
            key = f"{key}_{n}"
        columns.append({"key": key, "header": label, "unit": unit_hint})
    return columns


def _value_column_key(label: str) -> str:
    """``g/mol`` → ``g_mol``; ``density @ 25 C`` → ``density_at_25_C``."""
    text = label.strip()
    text = re.sub(r"\s*@\s*", "_at_", text)
    key = _VALUE_KEY.sub("_", text).strip("_")
    if not key:
        return "value"
    if key.isupper() and len(key) <= 8:
        return key
    if re.fullmatch(r"[A-Za-z]\d*", key):
        return key  # A, B, C, …
    return key


def parse_equation_units(equation: str | None) -> dict[str, str]:
    """Parse trailing ``(density - g/ml, T - K)`` footnotes into a name→unit map."""
    if not equation:
        return {}
    match = _EQ_UNIT_GROUP.search(equation.strip())
    if not match:
        return {}
    out: dict[str, str] = {}
    for pair in _EQ_UNIT_PAIR.finditer(match.group(1)):
        name = pair.group(1).strip()
        unit = pair.group(2).strip()
        out[name] = unit
        out[name.lower()] = unit
    return out


def _looks_like_unit(label: str) -> bool:
    low = label.strip().lower().replace(" ", "")
    if "/" in low:
        return True
    return low in _UNIT_ONLY


def attach_column_units(
    columns: list[dict[str, str | None]],
    equation: str | None,
) -> list[dict[str, str | None]]:
    """Fill ``unit`` on each column dict from the header label and equation footnote."""
    eq_units = parse_equation_units(equation)
    out: list[dict[str, str | None]] = []
    for col in columns:
        key = str(col["key"])
        label = str(col.get("header") or key)
        preset = col.get("unit")
        unit: str | None = preset if preset else None
        if key in ("id", "formula", "name") or key.startswith("value_extra_"):
            unit = None
        elif unit:
            pass  # keep T, C / T, K hint from coalesce
        elif _looks_like_unit(label):
            unit = label
        else:
            at = re.match(r"^(.+?)\s*@\s*(.+)$", label)
            if at:
                prop = at.group(1).strip()
                unit = (
                    eq_units.get(prop)
                    or eq_units.get(prop.lower())
                    or eq_units.get(prop.replace("_", ""))
                )
            elif key in _TEMP_KEYS or label in _TEMP_KEYS:
                unit = eq_units.get("T") or eq_units.get("t") or "K"
            elif key in eq_units:
                unit = eq_units[key]
            elif label in eq_units:
                unit = eq_units[label]
            else:
                unit = None
        # Unit-named headers (Debye, Angstrom) are themselves the unit.
        if unit is None and label.lower() in {"debye", "angstrom", "ångstrom"}:
            unit = label
        out.append({"key": key, "header": label, "unit": unit})
    return out


def column_keys(columns: list[dict[str, str | None]] | list[str]) -> list[str]:
    """Row-field keys in order (supports legacy string-list columns)."""
    if not columns:
        return []
    if isinstance(columns[0], str):
        return list(columns)  # type: ignore[arg-type]
    return [str(c["key"]) for c in columns]  # type: ignore[index]


def align_values(values: list[Any], n_cols: int) -> list[Any]:
    """Fit a parser ``values`` list to ``n_cols`` header slots.

    Missing cells are ``None`` (printed ``-``). OCR sometimes inserts an extra
    leading dash, e.g. ``- - - - - - - 1.020`` for 6 blanks + density → strip
    surplus leading nulls so the trailing number lands on the last column
    instead of inventing ``value_extra_*``.
    """
    if n_cols <= 0:
        return []
    vals = list(values)
    while len(vals) > n_cols and vals and vals[0] is None:
        vals.pop(0)
    if len(vals) < n_cols:
        vals.extend([None] * (n_cols - len(vals)))
    elif len(vals) > n_cols:
        # Still long after stripping leading nulls: keep the rightmost n_cols
        # when the overflow head is empty, else keep left-aligned head.
        head = vals[:-n_cols]
        if all(v is None for v in head):
            vals = vals[-n_cols:]
        else:
            vals = vals[:n_cols]
    return vals


def expand_row(
    row: dict[str, Any],
    columns: list[dict[str, str | None]] | list[str],
    *,
    keep_debug: bool = False,
) -> dict[str, Any]:
    """Map a parser row (``no`` + ``values``) onto named columns."""
    keys = column_keys(columns)
    value_cols = [c for c in keys if c not in ("id", "formula", "name")]
    values = align_values(list(row.get("values") or []), len(value_cols))
    out: dict[str, Any] = {
        "id": row.get("no"),
        "formula": row.get("formula"),
        "name": row.get("name"),
    }
    for i, col in enumerate(value_cols):
        out[col] = values[i] if i < len(values) else None
    if keep_debug:
        if row.get("sourcePage") is not None:
            out["sourcePage"] = row["sourcePage"]
        if row.get("raw"):
            out["raw"] = row["raw"]
        if row.get("formulaRaw") and row.get("formulaRaw") != row.get("formula"):
            out["formulaRaw"] = row["formulaRaw"]
        if row.get("unparsedTail"):
            out["unparsedTail"] = row["unparsedTail"]
    return out

