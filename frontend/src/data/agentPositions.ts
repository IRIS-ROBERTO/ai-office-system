/**
 * agentPositions.ts
 * Canonical spatial data for all 12 agents.
 * Single source of truth used by both:
 *   - officeStore.ts  → default spawn positions
 *   - OfficeLayout.tsx → where furniture is drawn
 *
 * Canvas: 1440 × 810
 *   Dev Studio   : x=0–636
 *   NEXUS Corridor: x=636–744
 *   Creative HQ  : x=744–1440
 *   Work Area    : y=38–480
 *   Boardroom    : y=490–810  (full-width)
 */

export interface Position { x: number; y: number; }

// ─── Role → desk center position ─────────────────────────────────────────────
// Agent visual anchor is approx desk_x + 55, desk_y + 53 (sitting at desk).
export const DESK_POSITIONS: Record<string, Position> = {
  // ── Dev Studio ──────────────────────────────────────────────────────────────
  planner:    { x: 290, y: 120 },  // ATLAS — team-lead desk (larger, center)
  frontend:   { x:  75, y: 232 },  // PIXEL — row A left
  backend:    { x: 218, y: 232 },  // FORGE — row A center
  qa:         { x: 361, y: 232 },  // SHERLOCK — row A right
  security:   { x: 145, y: 358 },  // AEGIS — row B left
  docs:       { x: 288, y: 358 },  // LORE  — row B center
  // ── Creative HQ ─────────────────────────────────────────────────────────────
  research:   { x: 840, y: 120 },  // ORACLE — team-lead desk (left)
  strategy:   { x: 1010, y: 120 }, // MAVEN  — team-lead desk (right)
  content:    { x: 822, y: 232 },  // NOVA   — row A left
  seo:        { x: 963, y: 232 },  // APEX   — row A center
  social:     { x: 1105, y: 232 }, // PULSE  — row A right
  analytics:  { x: 963, y: 358 },  // PRISM  — row B center
};

// ─── Boardroom meeting seats (12 chairs around conference table) ──────────────
// Table: oval centered at (720, 635), semi-axes ±310 horizontal, ±55 vertical
// Dev agents sit at the top edge; Marketing agents at the bottom edge.
export const MEETING_SEATS: Record<string, Position> = {
  // Top row — Dev team  (y ≈ 580)
  planner:    { x: 480, y: 577 },
  frontend:   { x: 580, y: 572 },
  backend:    { x: 680, y: 570 },
  qa:         { x: 760, y: 570 },
  security:   { x: 860, y: 572 },
  docs:       { x: 960, y: 577 },
  // Bottom row — Marketing team  (y ≈ 700)
  research:   { x: 480, y: 703 },
  strategy:   { x: 580, y: 708 },
  content:    { x: 680, y: 710 },
  seo:        { x: 760, y: 710 },
  social:     { x: 860, y: 708 },
  analytics:  { x: 960, y: 703 },
};

// ─── NEXUS corridor waypoints ─────────────────────────────────────────────────
// Agents pass through the NEXUS corridor (x=636–744) when crossing between
// their work zone and the boardroom, creating natural movement arcs.
export const NEXUS_WAYPOINTS: Record<'dev' | 'marketing' | 'orchestrator', Position> = {
  dev:       { x: 660, y: 420 },  // Dev side enters NEXUS from the left
  marketing: { x: 724, y: 420 },  // Marketing side enters NEXUS from the right
  orchestrator: { x: 690, y: 380 }, // Senior orchestrator owns the corridor spine
};

/** Returns the NEXUS corridor waypoint for a given team. */
export function getNexusWaypoint(team: 'dev' | 'marketing' | 'orchestrator'): Position {
  return NEXUS_WAYPOINTS[team];
}

// ─── Helpers ──────────────────────────────────────────────────────────────────
function matchRole(role: string, record: Record<string, Position>): Position | null {
  const lower = role.toLowerCase();
  for (const [key, pos] of Object.entries(record)) {
    if (lower.includes(key)) return pos;
  }
  return null;
}

export function getDeskPosition(role: string): Position | null {
  return matchRole(role, DESK_POSITIONS);
}

export function getMeetingPosition(role: string): Position | null {
  return matchRole(role, MEETING_SEATS);
}
