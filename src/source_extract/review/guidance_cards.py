"""Heuristic guidance cards for review sessions (LLM optional later)."""

from __future__ import annotations

import uuid
from typing import Any, Literal

from source_extract.review.export import isotherms_missing_temperature
from source_extract.review.session_persist import save_session

CardKind = Literal["note", "field_suggestion", "pitfall", "question"]


def make_card(
    *,
    kind: CardKind,
    title: str,
    body: str,
    rationale: str,
    evidence: list[dict[str, Any]] | None = None,
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "id": str(uuid.uuid4()),
        "kind": kind,
        "title": title,
        "body": body,
        "rationale": rationale,
        "evidence": evidence or [],
        "payload": payload or {},
        "status": "open",
    }


def build_context_pack(session: dict[str, Any]) -> dict[str, Any]:
    draft = session.get("draft") or {}
    phases = list(draft.get("phases") or [])
    unnamed = [p for p in phases if str(p).startswith("field-") or str(p).startswith("phase-")]
    missing_t = [
        str(p.get("id"))
        for p in draft.get("invariantPoints") or []
        if p.get("temperature_C") is None
    ]
    return {
        "system": session.get("system") or session.get("systemId"),
        "systemId": session.get("systemId"),
        "draftSource": session.get("draftSource"),
        "counts": {
            "boundaries": len(draft.get("boundaryCurves") or []),
            "isotherms": len(draft.get("isotherms") or []),
            "invariants": len(draft.get("invariantPoints") or []),
        },
        "unnamedFields": unnamed,
        "missingTemperatureIds": missing_t,
        "missingIsothermTemperatures": isotherms_missing_temperature(session),
    }


def heuristic_cards(context: dict[str, Any], max_questions: int = 5) -> list[dict[str, Any]]:
    cards: list[dict[str, Any]] = [
        make_card(
            kind="note",
            title="Draft — review required",
            body=(
                f"System {context.get('system')} was loaded for review. "
                "Verify field names, invariant temperatures, boundary arrows, and isotherms."
            ),
            rationale="Always shown when opening a draft.",
            evidence=[{"type": "counts", "value": context.get("counts")}],
        )
    ]
    unnamed = context.get("unnamedFields") or []
    if unnamed:
        cards.append(
            make_card(
                kind="field_suggestion",
                title="Unnamed fields present",
                body=f"Phases still labelled as placeholders: {', '.join(unnamed)}.",
                rationale="Automatic naming leaves placeholders when OCR cannot match a phase id.",
                evidence=[{"type": "phases", "value": unnamed}],
                payload={"unnamedFields": unnamed},
            )
        )
    missing = context.get("missingTemperatureIds") or []
    if missing:
        cards.append(
            make_card(
                kind="pitfall",
                title="Points without temperature",
                body=f"{len(missing)} invariant(s) lack temperature_C (e.g. {', '.join(missing[:5])}).",
                rationale="Labels may be missing or attached to the wrong junction.",
                evidence=[{"type": "pointIds", "value": missing[:20]}],
            )
        )
    missing_iso = context.get("missingIsothermTemperatures") or []
    if missing_iso:
        labels = ", ".join(
            f"#{m['index']}" + (f" ({m['field']})" if m.get("field") else "")
            for m in missing_iso[:8]
        )
        cards.append(
            make_card(
                kind="pitfall",
                title="Isotherms without temperature",
                body=(
                    f"{len(missing_iso)} isotherm(s) lack °C ({labels}). "
                    "Set temperature on each before Confirm."
                ),
                rationale="Confirmed diagrams require temperature_C on every isotherm.",
                evidence=[{"type": "isothermIndexes", "value": [m["index"] for m in missing_iso[:30]]}],
                payload={"missingIsothermTemperatures": missing_iso},
            )
        )
    cards.append(
        make_card(
            kind="pitfall",
            title="Boundary arrows may be unset",
            body="Cycle arrows on each boundary segment until they point toward falling temperature.",
            rationale="Auto drafts often omit temperature-direction arrows.",
        )
    )
    questions = [
        ("Are any heavy lines joins rather than field boundaries?", "Heavy non-boundary strokes."),
        ("Do any temperature labels belong to saddles rather than junctions?", "Common assignment error."),
    ]
    for title, rationale in questions[:max_questions]:
        cards.append(
            make_card(
                kind="question",
                title=title,
                body="Answer briefly if relevant; dismiss if not.",
                rationale=rationale,
            )
        )
    return cards


def refresh_guidance(session: dict[str, Any]) -> dict[str, Any]:
    context = build_context_pack(session)
    cards = heuristic_cards(context)
    session.setdefault("guidance", {"cards": [], "answers": []})
    kept = [c for c in session["guidance"].get("cards", []) if c.get("status") != "open"]
    session["guidance"]["cards"] = kept + cards
    save_session(session)
    return session


def update_card(
    session: dict[str, Any],
    *,
    card_id: str,
    status: str,
    answer: str | None = None,
) -> dict[str, Any]:
    if status not in {"accepted", "dismissed", "answered", "open"}:
        raise ValueError(f"Invalid card status: {status}")
    cards = session.setdefault("guidance", {"cards": [], "answers": []}).setdefault("cards", [])
    for card in cards:
        if card.get("id") != card_id:
            continue
        card["status"] = status
        if answer is not None:
            card["answer"] = answer
            session["guidance"].setdefault("answers", []).append(
                {"cardId": card_id, "answer": answer}
            )
        save_session(session)
        return session
    raise KeyError(card_id)
