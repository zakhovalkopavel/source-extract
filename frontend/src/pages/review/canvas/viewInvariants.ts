import type { SessionView } from '../types';

/** Invariants live as ``view.invariants`` (SE) or ``view.points`` (diagram-review). */
export function viewInvariants(view: SessionView | undefined): NonNullable<SessionView['invariants']> {
  if (!view) return [];
  const inv = view.invariants;
  if (inv && inv.length) return inv;
  return view.points || [];
}
