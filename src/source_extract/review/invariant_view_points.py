"""Build view-model invariant points for the review canvas."""

from __future__ import annotations

from typing import Any, Callable

from source_extract.review.invariant_compound_lookup import enrich_invariant_from_tag


def _node_label_by_invariant(session: dict[str, Any]) -> dict[str, str]:
    """Map draft invariant id → atlas node label (I1, I2, …)."""
    out: dict[str, str] = {}
    for node in session.get("nodes") or []:
        if (node.get("kind") or "") != "invariant":
            continue
        inv_id = node.get("invariant")
        label = node.get("label")
        if not inv_id or not label:
            continue
        key = str(inv_id)
        text = str(label)
        out[key] = text
        # Also index lower-case for cas-* mismatches after edits
        out.setdefault(key.lower(), text)
    return out


def build_ternary_invariant_points(
    session: dict[str, Any],
    *,
    components: list[str],
    origin: tuple[float, float],
    wt_to_image: Callable[[list[float]], list[float]],
) -> list[dict[str, Any]]:
    """Pixel invariants for the SPA.

    Always place from ``liquid_wt`` → current calibration (same as the live overlay /
    diagram-review). Atlas ``sources[].pixel`` may be stored-space or page-space; using
    it as page coords pushed many markers outside the triangle.
    """
    del origin  # placement is wt-driven
    labels = _node_label_by_invariant(session)
    points: list[dict[str, Any]] = []
    for inv in session["draft"].get("invariantPoints", []) or []:
        inv_id = str(inv["id"])
        wt = [float(inv["liquid_wt"][c]) for c in components]
        src = (inv.get("sources") or [{}])[0]
        pix = wt_to_image(wt)

        temperature = inv.get("temperature_C")
        notation = inv.get("notation") or src.get("notation")
        enrich = enrich_invariant_from_tag(inv_id)
        if enrich:
            notation = notation or enrich.get("notation") or enrich.get("compoundId")
            if temperature is None and enrich.get("temperature_C") is not None:
                temperature = enrich["temperature_C"]

        label = labels.get(inv_id) or labels.get(inv_id.lower()) or notation or inv_id
        points.append(
            {
                "id": inv_id,
                "kind": "invariant",
                "label": label,
                "notation": notation,
                "reaction": inv.get("reaction"),
                "phases": list(inv.get("phases") or []),
                "temperature_C": temperature,
                "composition": {c: inv["liquid_wt"][c] for c in components},
                "wt": wt,
                "pixel": pix,
                "pagePixel": src.get("pixel"),
                "provenance": session["provenance"].get("points", {}).get(inv_id, "auto"),
            }
        )
    return points
