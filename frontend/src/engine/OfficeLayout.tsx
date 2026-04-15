/**
 * AI Office System — Elite Office Layout v2
 *
 * Three distinct architectural zones rendered in WebGL via PixiJS:
 *   Dev Studio    — Cyberpunk tech noir  (electric blue)
 *   Creative HQ   — Vibrant creative hub (violet / pink)
 *   NEXUS Corridor — Command spine       (gold hologram)
 *
 * Bottom section — BOARDROOM: Full-width conference room shared by both teams.
 *
 * Agent furniture is drawn AT the canonical positions from agentPositions.ts,
 * so agents always spawn sitting at their desks.
 */
import React, { useCallback, useEffect, useRef } from 'react';
import { Stage, Graphics, Text, useTick } from '@pixi/react';
import * as PIXI from 'pixi.js';
import { useOfficeStore } from '../state/officeStore';
import AgentSprite from '../components/agents/AgentSprite';
import TaskBubble from '../components/agents/TaskBubble';

// ─── Canvas & zone geometry ───────────────────────────────────────────────────
export const CANVAS_W = 1440;
export const CANVAS_H = 810;

export const DEV_ZONE  = { x: 0,   y: 0, w: 636,  h: CANVAS_H };
export const CORR_ZONE = { x: 636, y: 0, w: 108,  h: CANVAS_H };
export const MKT_ZONE  = { x: 744, y: 0, w: 696,  h: CANVAS_H };

/** Work area occupies y = 0 → WORK_BOTTOM. Boardroom below. */
const WORK_BOTTOM = 488;
/** Boardroom strip: y = BOARD_TOP → CANVAS_H */
const BOARD_TOP   = 490;

// ─── Colour palette ───────────────────────────────────────────────────────────
const C_DEV_BG     = 0x060b14;
const C_DEV_GRID   = 0x0d2137;
const C_DEV_ACCENT = 0x00c8ff;
const C_MKT_BG     = 0x0d0718;
const C_MKT_GRID   = 0x1d0b30;
const C_MKT_ACCENT = 0xb144ff;
const C_CORR_BG    = 0x03030a;
const C_GOLD       = 0xfbbf24;
const C_BOARD_BG   = 0x07070f;

// ─── Shared drawing helpers ───────────────────────────────────────────────────
function drawPlant(g: PIXI.Graphics, x: number, y: number, scale = 1) {
  g.beginFill(0x2d1818, 1);
  g.lineStyle(1, 0x4a2020, 0.8);
  g.drawRoundedRect(x - 14 * scale, y, 28 * scale, 30 * scale, 4);
  g.endFill();
  g.lineStyle(2 * scale, 0x1a4a20, 0.9);
  g.moveTo(x, y); g.lineTo(x, y - 30 * scale);
  for (let i = 0; i < 4; i++) {
    const a = (i / 4) * Math.PI;
    g.beginFill(0x1a6a20, 0.7);
    g.lineStyle(0);
    g.drawEllipse(x + Math.cos(a) * 18 * scale, y - 20 * scale - i * 8 * scale, 14 * scale, 8 * scale);
    g.endFill();
  }
}

/** Draw a standard dev workstation (110 × 54) with dual monitors. */
function drawDevDesk(g: PIXI.Graphics, x: number, y: number) {
  g.beginFill(0x0d2137, 0.9);
  g.lineStyle(1, C_DEV_ACCENT, 0.3);
  g.drawRoundedRect(x, y, 110, 54, 5);
  g.endFill();
  // Left monitor
  g.beginFill(0x020a12, 0.98);
  g.lineStyle(1, C_DEV_ACCENT, 0.5);
  g.drawRoundedRect(x + 4, y - 50, 44, 34, 3);
  g.endFill();
  g.beginFill(C_DEV_ACCENT, 0.06);
  g.drawRoundedRect(x + 6, y - 48, 40, 30, 2);
  g.endFill();
  for (let i = 0; i < 4; i++) {
    g.beginFill([C_DEV_ACCENT, 0x00ff88, 0xfbbf24, 0xff6b6b][i], 0.3);
    g.drawRoundedRect(x + 7, y - 46 + i * 7, 18 + (i * 4) % 14, 4, 1);
    g.endFill();
  }
  // Right monitor
  g.beginFill(0x020a12, 0.98);
  g.lineStyle(1, C_DEV_ACCENT, 0.5);
  g.drawRoundedRect(x + 62, y - 50, 44, 34, 3);
  g.endFill();
  g.beginFill(C_DEV_ACCENT, 0.04);
  g.drawRoundedRect(x + 64, y - 48, 40, 30, 2);
  g.endFill();
  // Monitor stands
  g.lineStyle(1.5, C_DEV_GRID, 0.8);
  g.moveTo(x + 26, y - 16); g.lineTo(x + 26, y);
  g.moveTo(x + 84, y - 16); g.lineTo(x + 84, y);
  // Keyboard
  g.beginFill(0x091624, 1);
  g.lineStyle(0.5, C_DEV_ACCENT, 0.2);
  g.drawRoundedRect(x + 10, y + 36, 86, 14, 2);
  g.endFill();
}

/** ATLAS team-lead desk — wider, triple monitor, holographic status display. */
function drawDevLeaderDesk(g: PIXI.Graphics, x: number, y: number) {
  // Desk surface (wider)
  g.beginFill(0x0a1e30, 0.95);
  g.lineStyle(1.5, C_DEV_ACCENT, 0.55);
  g.drawRoundedRect(x, y, 180, 64, 8);
  g.endFill();
  // Inlaid accent stripe
  g.beginFill(C_DEV_ACCENT, 0.06);
  g.drawRoundedRect(x + 4, y + 56, 172, 4, 2);
  g.endFill();
  // Three monitors
  const monW = 50, monH = 38;
  for (let m = 0; m < 3; m++) {
    const mx = x + 6 + m * 58;
    g.beginFill(0x010810, 0.98);
    g.lineStyle(1.2, C_DEV_ACCENT, 0.55);
    g.drawRoundedRect(mx, y - 52, monW, monH, 3);
    g.endFill();
    g.beginFill(C_DEV_ACCENT, 0.07);
    g.drawRoundedRect(mx + 2, y - 50, monW - 4, monH - 4, 2);
    g.endFill();
    g.lineStyle(1.5, C_DEV_GRID, 0.8);
    g.moveTo(mx + 25, y - 14); g.lineTo(mx + 25, y);
    // Code/data on screen
    for (let li = 0; li < 3; li++) {
      g.beginFill([C_DEV_ACCENT, 0x00ff88, 0xfbbf24][m], 0.35);
      g.drawRoundedRect(mx + 3, y - 48 + li * 10, 20 + li * 6, 5, 1);
      g.endFill();
    }
  }
  // Holographic name plate
  g.beginFill(C_DEV_ACCENT, 0.08);
  g.lineStyle(1, C_DEV_ACCENT, 0.5);
  g.drawRoundedRect(x + 130, y + 8, 44, 22, 4);
  g.endFill();
  g.lineStyle(0.5, C_DEV_ACCENT, 0.3);
  g.moveTo(x + 136, y + 15); g.lineTo(x + 168, y + 15);
  g.moveTo(x + 136, y + 22); g.lineTo(x + 158, y + 22);
  // Leader tag
  g.beginFill(C_GOLD, 0.15);
  g.lineStyle(1, C_GOLD, 0.6);
  g.drawRoundedRect(x + 4, y + 8, 38, 14, 3);
  g.endFill();
  // Keyboard (wide)
  g.beginFill(0x091624, 1);
  g.lineStyle(0.5, C_DEV_ACCENT, 0.2);
  g.drawRoundedRect(x + 10, y + 46, 120, 14, 2);
  g.endFill();
}

/** Standard marketing workstation — widescreen + tablet. */
function drawMktDesk(g: PIXI.Graphics, x: number, y: number) {
  g.beginFill(0x1a0a28, 0.88);
  g.lineStyle(1, C_MKT_ACCENT, 0.3);
  g.drawRoundedRect(x, y, 120, 54, 10);
  g.endFill();
  // Widescreen monitor
  g.beginFill(0x08020f, 0.98);
  g.lineStyle(1.5, C_MKT_ACCENT, 0.5);
  g.drawRoundedRect(x + 4, y - 50, 112, 42, 4);
  g.endFill();
  g.beginFill(C_MKT_ACCENT, 0.05);
  g.drawRoundedRect(x + 6, y - 48, 108, 38, 3);
  g.endFill();
  // Creative content placeholder
  g.beginFill(0xec4899, 0.35); g.drawCircle(x + 30, y - 28, 12); g.endFill();
  g.beginFill(C_MKT_ACCENT, 0.35); g.drawRoundedRect(x + 50, y - 44, 58, 28, 4); g.endFill();
  // Monitor stand
  g.lineStyle(2, C_MKT_GRID, 0.8);
  g.moveTo(x + 60, y - 8); g.lineTo(x + 60, y);
  // Stylus pad
  g.beginFill(0x12082a, 1);
  g.lineStyle(0.5, C_MKT_ACCENT, 0.2);
  g.drawRoundedRect(x + 8, y + 36, 70, 14, 3);
  g.endFill();
}

/** ORACLE / MAVEN team-lead desk — dual displays + analytics panel. */
function drawMktLeaderDesk(g: PIXI.Graphics, x: number, y: number) {
  g.beginFill(0x150923, 0.95);
  g.lineStyle(1.5, C_MKT_ACCENT, 0.55);
  g.drawRoundedRect(x, y, 170, 64, 10);
  g.endFill();
  g.beginFill(C_MKT_ACCENT, 0.06);
  g.drawRoundedRect(x + 4, y + 56, 162, 4, 2);
  g.endFill();
  // Main widescreen
  g.beginFill(0x06010e, 0.98);
  g.lineStyle(1.5, C_MKT_ACCENT, 0.55);
  g.drawRoundedRect(x + 4, y - 52, 118, 44, 4);
  g.endFill();
  g.beginFill(C_MKT_ACCENT, 0.06);
  g.drawRoundedRect(x + 6, y - 50, 114, 40, 3);
  g.endFill();
  // Abstract chart on main screen
  const barH = [18, 28, 22, 36, 25, 30, 20];
  barH.forEach((bh, i) => {
    const col = [C_MKT_ACCENT, 0xec4899, 0xfbbf24, C_MKT_ACCENT, 0xa855f7, C_MKT_ACCENT, 0xec4899][i];
    g.beginFill(col, 0.45);
    g.drawRoundedRect(x + 8 + i * 15, y - 14 - bh, 11, bh, 2);
    g.endFill();
  });
  // Side analytics screen
  g.beginFill(0x06010e, 0.98);
  g.lineStyle(1, C_MKT_ACCENT, 0.45);
  g.drawRoundedRect(x + 128, y - 48, 38, 40, 3);
  g.endFill();
  g.beginFill(0xec4899, 0.3); g.drawCircle(x + 147, y - 30, 12); g.endFill();
  g.lineStyle(0.5, C_MKT_ACCENT, 0.3);
  g.drawCircle(x + 147, y - 30, 16);
  // Monitor stand
  g.lineStyle(2, C_MKT_GRID, 0.8);
  g.moveTo(x + 65, y - 8); g.lineTo(x + 65, y);
  // Leader tag
  g.beginFill(C_GOLD, 0.12);
  g.lineStyle(1, C_GOLD, 0.6);
  g.drawRoundedRect(x + 4, y + 8, 38, 14, 3);
  g.endFill();
  // Keyboard
  g.beginFill(0x0e0520, 1);
  g.lineStyle(0.5, C_MKT_ACCENT, 0.2);
  g.drawRoundedRect(x + 10, y + 46, 110, 14, 3);
  g.endFill();
}

// ─── DEV STUDIO Background ────────────────────────────────────────────────────
const DevBackground: React.FC = () => {
  const draw = useCallback((g: PIXI.Graphics) => {
    g.clear();

    // Base fill (work area only)
    g.beginFill(C_DEV_BG);
    g.drawRect(DEV_ZONE.x, DEV_ZONE.y, DEV_ZONE.w, CANVAS_H);
    g.endFill();

    // Hex-grid floor (isometric feel)
    const HEX = 36;
    g.lineStyle(0.5, C_DEV_GRID, 0.55);
    for (let row = 0; row < 22; row++) {
      for (let col = 0; col < 22; col++) {
        const ox = col * HEX * 1.5;
        const oy = row * HEX * 0.866 + (col % 2 === 0 ? 0 : HEX * 0.433);
        if (ox > DEV_ZONE.w + 10 || oy > WORK_BOTTOM) continue;
        for (let i = 0; i < 6; i++) {
          const a1 = (Math.PI / 180) * (60 * i);
          const a2 = (Math.PI / 180) * (60 * (i + 1));
          const r = HEX * 0.5;
          g.moveTo(ox + r * Math.cos(a1), oy + r * Math.sin(a1));
          g.lineTo(ox + r * Math.cos(a2), oy + r * Math.sin(a2));
        }
      }
    }

    // Work area floor accent
    g.lineStyle(1.5, C_DEV_ACCENT, 0.12);
    g.moveTo(DEV_ZONE.x, WORK_BOTTOM);
    g.lineTo(DEV_ZONE.x + DEV_ZONE.w, WORK_BOTTOM);

    // ─── Server Rack Cluster (top-right) ─────────────────────────────────────
    const RACK_X = DEV_ZONE.w - 106, RACK_Y = 52;
    // Rack 1
    g.beginFill(0x0a1a28, 1);
    g.lineStyle(1.5, C_DEV_ACCENT, 0.35);
    g.drawRoundedRect(RACK_X, RACK_Y, 80, 200, 4);
    g.endFill();
    for (let si = 0; si < 8; si++) {
      const sy = RACK_Y + 12 + si * 23;
      g.beginFill(0x0d2a3a, 1);
      g.lineStyle(0.5, C_DEV_ACCENT, 0.2);
      g.drawRoundedRect(RACK_X + 6, sy, 66, 17, 2);
      g.endFill();
      const col = si % 3 === 0 ? 0x00ff88 : si % 3 === 1 ? C_DEV_ACCENT : C_GOLD;
      g.beginFill(col, 0.85);
      g.drawCircle(RACK_X + 70, sy + 8, 2.5);
      g.endFill();
    }
    // Rack 2 (second unit)
    const R2X = RACK_X - 90;
    g.beginFill(0x0a1a28, 1);
    g.lineStyle(1.5, C_DEV_ACCENT, 0.25);
    g.drawRoundedRect(R2X, RACK_Y, 80, 160, 4);
    g.endFill();
    for (let si = 0; si < 6; si++) {
      const sy = RACK_Y + 12 + si * 23;
      g.beginFill(0x0d2a3a, 1);
      g.lineStyle(0.5, C_DEV_ACCENT, 0.15);
      g.drawRoundedRect(R2X + 6, sy, 66, 17, 2);
      g.endFill();
    }
    // Rack cable conduit
    g.lineStyle(2, C_DEV_ACCENT, 0.1);
    g.moveTo(R2X + 80, RACK_Y + 80); g.lineTo(RACK_X, RACK_Y + 80);

    // ─── ATLAS — team leader desk ─────────────────────────────────────────────
    // Desk x=200, y=65 → agent at (290, 120)
    drawDevLeaderDesk(g, 200, 65);
    // Halo marker (status LED strip on desk edge)
    g.beginFill(C_DEV_ACCENT, 0.15);
    g.drawRoundedRect(200, 62, 180, 4, 2);
    g.endFill();

    // ─── Regular Dev Desks — Row A (y=180) ───────────────────────────────────
    // PIXEL (x=75, y=232) → desk x=20, y=180
    drawDevDesk(g, 20, 180);
    // FORGE (x=218, y=232) → desk x=163, y=180
    drawDevDesk(g, 163, 180);
    // SHERLOCK (x=361, y=232) → desk x=306, y=180
    drawDevDesk(g, 306, 180);

    // ─── Regular Dev Desks — Row B (y=305) ───────────────────────────────────
    // AEGIS (x=145, y=358) → desk x=90, y=305
    drawDevDesk(g, 90, 305);
    // LORE (x=288, y=358) → desk x=233, y=305
    drawDevDesk(g, 233, 305);
    // Standing desk / spare station for collab
    g.beginFill(0x0d2137, 0.7);
    g.lineStyle(1, C_DEV_ACCENT, 0.18);
    g.drawRoundedRect(390, 305, 90, 42, 4);
    g.endFill();
    g.beginFill(0x020a12, 0.85);
    g.lineStyle(1, C_DEV_ACCENT, 0.3);
    g.drawRoundedRect(394, 258, 82, 46, 3);
    g.endFill();
    g.beginFill(C_DEV_ACCENT, 0.08);
    g.drawRoundedRect(396, 260, 78, 42, 2);
    g.endFill();

    // ─── Dev Collab whiteboard (left wall) ────────────────────────────────────
    const WBA_X = 2, WBA_Y = 400;
    g.beginFill(0x0d1a26, 0.92);
    g.lineStyle(1.5, C_DEV_ACCENT, 0.4);
    g.drawRoundedRect(WBA_X, WBA_Y, 180, 78, 4);
    g.endFill();
    // Diagram on whiteboard
    g.lineStyle(1, C_DEV_ACCENT, 0.35);
    g.drawCircle(WBA_X + 30, WBA_Y + 36, 18);
    g.moveTo(WBA_X + 48, WBA_Y + 36); g.lineTo(WBA_X + 68, WBA_Y + 36);
    g.beginFill(0x00ff88, 0.3);
    g.drawRoundedRect(WBA_X + 68, WBA_Y + 24, 40, 24, 3);
    g.endFill();
    g.moveTo(WBA_X + 108, WBA_Y + 36); g.lineTo(WBA_X + 128, WBA_Y + 36);
    g.beginFill(C_GOLD, 0.25);
    g.drawRoundedRect(WBA_X + 128, WBA_Y + 26, 36, 20, 3);
    g.endFill();
    g.lineStyle(1, 0xffffff, 0.08);
    g.moveTo(WBA_X + 6, WBA_Y + 65); g.lineTo(WBA_X + 100, WBA_Y + 65);
    g.moveTo(WBA_X + 6, WBA_Y + 71); g.lineTo(WBA_X + 70, WBA_Y + 71);

    // ─── Dev large code review screen ────────────────────────────────────────
    const SCR_X = 2, SCR_Y = 390;
    g.beginFill(0x03111d, 0.95);
    g.lineStyle(1.5, C_DEV_ACCENT, 0.4);
    g.drawRoundedRect(SCR_X + 185, SCR_Y - 90, 400, 80, 5);
    g.endFill();
    for (let li = 0; li < 4; li++) {
      const lineW = 60 + li * 50;
      const lineColor = [C_DEV_ACCENT, 0x00ff88, 0xfbbf24, 0xff6b6b][li];
      g.beginFill(lineColor, 0.3);
      g.drawRoundedRect(SCR_X + 198 + (li % 2) * 20, SCR_Y - 82 + li * 17, lineW, 7, 2);
      g.endFill();
    }

    // ─── Plants ───────────────────────────────────────────────────────────────
    drawPlant(g, 490, 415);
    drawPlant(g, 600, 415);

    // ─── Top label bar ────────────────────────────────────────────────────────
    g.beginFill(C_DEV_ACCENT, 0.06);
    g.drawRect(0, 0, DEV_ZONE.w, 38);
    g.endFill();
    g.lineStyle(1, C_DEV_ACCENT, 0.3);
    g.moveTo(0, 38); g.lineTo(DEV_ZONE.w, 38);
  }, []);

  return <Graphics draw={draw} />;
};

// ─── CREATIVE HQ Background ───────────────────────────────────────────────────
const MktBackground: React.FC = () => {
  const draw = useCallback((g: PIXI.Graphics) => {
    g.clear();

    g.beginFill(C_MKT_BG);
    g.drawRect(MKT_ZONE.x, MKT_ZONE.y, MKT_ZONE.w, CANVAS_H);
    g.endFill();

    // Diagonal stripe floor
    g.lineStyle(0.6, C_MKT_GRID, 0.5);
    const STRIPE = 42;
    for (let i = -20; i < 60; i++) {
      const ox = MKT_ZONE.x + i * STRIPE;
      const maxY = Math.min(WORK_BOTTOM, CANVAS_H);
      g.moveTo(ox, 0); g.lineTo(ox + maxY, maxY);
    }

    g.lineStyle(1.5, C_MKT_ACCENT, 0.1);
    g.moveTo(MKT_ZONE.x, WORK_BOTTOM);
    g.lineTo(MKT_ZONE.x + MKT_ZONE.w, WORK_BOTTOM);

    // ─── ORACLE team-lead desk (left) ─────────────────────────────────────────
    // ORACLE agent at (840, 120) → desk x=760, y=65
    drawMktLeaderDesk(g, 760, 65);
    g.beginFill(C_MKT_ACCENT, 0.12);
    g.drawRoundedRect(760, 62, 170, 4, 2);
    g.endFill();

    // ─── MAVEN team-lead desk (right) ─────────────────────────────────────────
    // MAVEN agent at (1010, 120) → desk x=930, y=65
    drawMktLeaderDesk(g, 930, 65);
    g.beginFill(C_MKT_ACCENT, 0.12);
    g.drawRoundedRect(930, 62, 170, 4, 2);
    g.endFill();

    // Leader separator between the two
    g.lineStyle(1, C_GOLD, 0.2);
    g.moveTo(928, 65); g.lineTo(928, 130);

    // ─── Regular Marketing Desks — Row A (y=180) ─────────────────────────────
    // NOVA (822, 232) → desk x=762, y=180
    drawMktDesk(g, 762, 180);
    // APEX (963, 232) → desk x=903, y=180
    drawMktDesk(g, 903, 180);
    // PULSE (1105, 232) → desk x=1045, y=180
    drawMktDesk(g, 1045, 180);
    // Extra: PULSE extended collab desk
    g.beginFill(0x1a0a28, 0.7);
    g.lineStyle(1, C_MKT_ACCENT, 0.18);
    g.drawRoundedRect(1175, 180, 100, 42, 8);
    g.endFill();

    // ─── Regular Marketing Desks — Row B (y=305) ─────────────────────────────
    // PRISM (963, 358) → desk x=903, y=305
    drawMktDesk(g, 903, 305);
    // Spare collab desk
    g.beginFill(0x1a0a28, 0.65);
    g.lineStyle(1, C_MKT_ACCENT, 0.15);
    g.drawRoundedRect(762, 305, 100, 42, 8);
    g.endFill();
    g.beginFill(0x06010e, 0.85);
    g.lineStyle(1, C_MKT_ACCENT, 0.25);
    g.drawRoundedRect(766, 260, 92, 42, 3);
    g.endFill();

    // ─── Concept / Mood Board (right wall) ────────────────────────────────────
    const MB_X = MKT_ZONE.x + MKT_ZONE.w - 170, MB_Y = 55;
    g.beginFill(0x120820, 0.95);
    g.lineStyle(1.5, C_MKT_ACCENT, 0.4);
    g.drawRoundedRect(MB_X, MB_Y, 155, 280, 6);
    g.endFill();
    const cardColors = [0xec4899, 0xa855f7, 0xf97316, 0x10b981, 0x3b82f6, 0xfbbf24, 0xef4444, 0x06b6d4];
    const cardPos: [number, number][] = [
      [8, 12], [84, 12], [8, 94], [84, 94],
      [34, 172], [8, 238], [84, 188], [46, 250],
    ];
    cardPos.forEach(([cx, cy], idx) => {
      const cw = 56 + (idx % 2) * 14, ch = 66 + (idx % 3) * 10;
      g.beginFill(cardColors[idx % 8], 0.2);
      g.lineStyle(1, cardColors[idx % 8], 0.5);
      g.drawRoundedRect(MB_X + cx, MB_Y + cy, cw, ch, 3);
      g.endFill();
      g.lineStyle(0);
      g.beginFill(cardColors[idx % 8], 0.5);
      g.drawRoundedRect(MB_X + cx + 4, MB_Y + cy + ch - 18, cw - 8, 5, 1);
      g.drawRoundedRect(MB_X + cx + 4, MB_Y + cy + ch - 10, (cw - 8) * 0.6, 4, 1);
      g.endFill();
      g.beginFill(0xffffff, 0.7);
      g.drawCircle(MB_X + cx + cw / 2, MB_Y + cy + 5, 3);
      g.endFill();
    });

    // ─── Analytics wall display ────────────────────────────────────────────────
    const AW_X = MKT_ZONE.x + 10, AW_Y = 55, AW_W = 140, AW_H = 200;
    g.beginFill(0x08021a, 0.95);
    g.lineStyle(2, C_MKT_ACCENT, 0.5);
    g.drawRoundedRect(AW_X, AW_Y, AW_W, AW_H, 6);
    g.endFill();
    g.beginFill(C_MKT_ACCENT, 0.04);
    g.drawRoundedRect(AW_X + 2, AW_Y + 2, AW_W - 4, AW_H / 2, 4);
    g.endFill();
    // Donut chart
    g.lineStyle(8, C_MKT_ACCENT, 0.5);
    g.drawCircle(AW_X + 50, AW_Y + 75, 28);
    g.lineStyle(8, 0xec4899, 0.5);
    g.arc(AW_X + 50, AW_Y + 75, 28, 0, Math.PI * 1.2);
    g.lineStyle(0);
    g.beginFill(0x08021a, 1);
    g.drawCircle(AW_X + 50, AW_Y + 75, 16);
    g.endFill();
    g.beginFill(C_MKT_ACCENT, 0.9);
    g.drawCircle(AW_X + 50, AW_Y + 75, 5);
    g.endFill();
    // Mini bar chart
    [0.5, 0.8, 0.6, 0.9, 0.65].forEach((h, i) => {
      const bx = AW_X + 85 + i * 10;
      const bh = h * 40;
      const col = [C_MKT_ACCENT, 0xec4899, 0xa855f7, C_MKT_ACCENT, 0xfbbf24][i];
      g.beginFill(col, 0.5);
      g.drawRoundedRect(bx, AW_Y + 115 - bh, 7, bh, 1);
      g.endFill();
    });
    // Trend line
    g.lineStyle(1.5, C_GOLD, 0.6);
    g.moveTo(AW_X + 8, AW_Y + 165);
    [22, 18, 28, 15, 25, 10, 20, 8, 14, 6].forEach((py, i) => {
      g.lineTo(AW_X + 8 + (i + 1) * 12, AW_Y + 165 - py);
    });

    // ─── Large presentation screen (bottom left of mkt zone) ─────────────────
    const PS_X = MKT_ZONE.x + 160, PS_Y = 388;
    g.beginFill(0x08021a, 0.95);
    g.lineStyle(2, C_MKT_ACCENT, 0.5);
    g.drawRoundedRect(PS_X, PS_Y, 420, 90, 8);
    g.endFill();
    g.beginFill(C_MKT_ACCENT, 0.04);
    g.drawRoundedRect(PS_X + 2, PS_Y + 2, 416, 42, 6);
    g.endFill();
    [0.4, 0.7, 0.55, 0.9, 0.65, 0.8, 0.5, 0.75].forEach((h, i) => {
      const bx = PS_X + 40 + i * 44, by = PS_Y + 85;
      const bh = h * 65;
      const col = [C_MKT_ACCENT, 0xec4899, 0xa855f7, C_MKT_ACCENT][i % 4];
      g.beginFill(col, 0.5);
      g.drawRoundedRect(bx, by - bh, 25, bh, 3);
      g.endFill();
      g.beginFill(col, 0.9);
      g.drawCircle(bx + 12, by - bh, 3.5);
      g.endFill();
    });

    // ─── Plants ───────────────────────────────────────────────────────────────
    drawPlant(g, MKT_ZONE.x + 600, 415);
    drawPlant(g, MKT_ZONE.x + 650, 415);

    // ─── Top label bar ────────────────────────────────────────────────────────
    g.beginFill(C_MKT_ACCENT, 0.06);
    g.drawRect(MKT_ZONE.x, 0, MKT_ZONE.w, 38);
    g.endFill();
    g.lineStyle(1, C_MKT_ACCENT, 0.3);
    g.moveTo(MKT_ZONE.x, 38); g.lineTo(MKT_ZONE.x + MKT_ZONE.w, 38);
  }, []);

  return <Graphics draw={draw} />;
};

// ─── NEXUS Corridor ───────────────────────────────────────────────────────────
const CorrBackground: React.FC = () => {
  const draw = useCallback((g: PIXI.Graphics) => {
    g.clear();
    const CX = CORR_ZONE.x + CORR_ZONE.w / 2;

    g.beginFill(C_CORR_BG);
    g.drawRect(CORR_ZONE.x, CORR_ZONE.y, CORR_ZONE.w, CANVAS_H);
    g.endFill();

    // Side borders
    g.lineStyle(1.5, C_DEV_ACCENT, 0.22);
    g.moveTo(CORR_ZONE.x, 0); g.lineTo(CORR_ZONE.x, WORK_BOTTOM);
    g.lineStyle(1.5, C_MKT_ACCENT, 0.22);
    g.moveTo(CORR_ZONE.x + CORR_ZONE.w, 0);
    g.lineTo(CORR_ZONE.x + CORR_ZONE.w, WORK_BOTTOM);

    // Central spine
    g.lineStyle(1, C_GOLD, 0.18);
    g.moveTo(CX, 0); g.lineTo(CX, WORK_BOTTOM);

    // Command node platform
    const NODE_Y = CANVAS_H / 2 - 90;
    g.beginFill(0x0d0b00, 0.95);
    g.lineStyle(2, C_GOLD, 0.55);
    g.drawRoundedRect(CORR_ZONE.x + 8, NODE_Y, CORR_ZONE.w - 16, 90, 8);
    g.endFill();

    // Nested hologram rings
    g.lineStyle(1.5, C_GOLD, 0.5);
    g.drawCircle(CX, NODE_Y + 45, 22);
    g.lineStyle(0.8, C_GOLD, 0.28);
    g.drawCircle(CX, NODE_Y + 45, 32);
    g.lineStyle(0.4, C_GOLD, 0.14);
    g.drawCircle(CX, NODE_Y + 45, 40);

    // Core
    g.lineStyle(0);
    g.beginFill(C_GOLD, 0.85);
    g.drawCircle(CX, NODE_Y + 45, 5);
    g.endFill();
    g.beginFill(C_GOLD, 0.15);
    g.drawCircle(CX, NODE_Y + 45, 12);
    g.endFill();

    // Tick marks on ring
    for (let i = 0; i < 8; i++) {
      const a = (Math.PI * 2 * i) / 8;
      const r1 = 22, r2 = 28;
      g.lineStyle(1, C_GOLD, 0.35);
      g.moveTo(CX + r1 * Math.cos(a), NODE_Y + 45 + r1 * Math.sin(a));
      g.lineTo(CX + r2 * Math.cos(a), NODE_Y + 45 + r2 * Math.sin(a));
    }

    // NEXUS label bar
    g.beginFill(C_GOLD, 0.06);
    g.drawRect(CORR_ZONE.x, 0, CORR_ZONE.w, 38);
    g.endFill();
  }, []);

  return <Graphics draw={draw} />;
};

// ─── BOARDROOM (full-width bottom strip) ─────────────────────────────────────
const TABLE_CX = CANVAS_W / 2;   // 720
const TABLE_CY = BOARD_TOP + 140; // 630
const TABLE_A  = 305;             // horizontal semi-axis
const TABLE_B  = 56;              // vertical semi-axis

const Boardroom: React.FC = () => {
  const draw = useCallback((g: PIXI.Graphics) => {
    g.clear();

    // ── Background ──────────────────────────────────────────────────────────
    g.beginFill(C_BOARD_BG, 0.98);
    g.drawRect(0, BOARD_TOP, CANVAS_W, CANVAS_H - BOARD_TOP);
    g.endFill();

    // Top separator
    g.lineStyle(3, C_GOLD, 0.55);
    g.moveTo(0, BOARD_TOP); g.lineTo(CANVAS_W, BOARD_TOP);
    g.lineStyle(1, C_GOLD, 0.15);
    g.moveTo(0, BOARD_TOP + 4); g.lineTo(CANVAS_W, BOARD_TOP + 4);

    // Diamond tile floor
    const TILE = 52;
    g.lineStyle(0.5, 0x111128, 1);
    for (let row = 0; row <= 7; row++) {
      for (let col = 0; col <= 28; col++) {
        const tx = col * TILE;
        const ty = BOARD_TOP + row * TILE;
        g.moveTo(tx + TILE / 2, ty);
        g.lineTo(tx + TILE, ty + TILE / 2);
        g.lineTo(tx + TILE / 2, ty + TILE);
        g.lineTo(tx, ty + TILE / 2);
        g.closePath();
      }
    }

    // ── Conference Table ────────────────────────────────────────────────────
    // Outer glow layers
    g.lineStyle(4, C_GOLD, 0.08);
    g.drawEllipse(TABLE_CX, TABLE_CY, TABLE_A + 28, TABLE_B + 28);
    g.lineStyle(2, C_GOLD, 0.04);
    g.drawEllipse(TABLE_CX, TABLE_CY, TABLE_A + 48, TABLE_B + 48);

    // Table surface (dark executive wood)
    g.beginFill(0x0c1408, 0.99);
    g.lineStyle(2.5, C_GOLD, 0.65);
    g.drawEllipse(TABLE_CX, TABLE_CY, TABLE_A, TABLE_B);
    g.endFill();

    // Wood grain detail
    g.lineStyle(0.8, 0x172010, 0.45);
    for (let k = -4; k <= 4; k++) {
      g.drawEllipse(TABLE_CX + k * 4, TABLE_CY + k * 1.5, TABLE_A * 0.88, TABLE_B * 0.65);
    }

    // Table center hologram pad
    g.beginFill(C_GOLD, 0.07);
    g.lineStyle(1, C_GOLD, 0.4);
    g.drawEllipse(TABLE_CX, TABLE_CY, 90, 28);
    g.endFill();
    g.lineStyle(0.5, C_GOLD, 0.25);
    g.drawEllipse(TABLE_CX, TABLE_CY, 60, 18);
    g.beginFill(C_GOLD, 0.7);
    g.drawCircle(TABLE_CX, TABLE_CY, 4);
    g.endFill();
    g.beginFill(C_GOLD, 0.12);
    g.drawCircle(TABLE_CX, TABLE_CY, 10);
    g.endFill();

    // Holo cross lines on pad
    g.lineStyle(0.8, C_GOLD, 0.2);
    g.moveTo(TABLE_CX - 85, TABLE_CY); g.lineTo(TABLE_CX + 85, TABLE_CY);
    g.moveTo(TABLE_CX, TABLE_CY - 24); g.lineTo(TABLE_CX, TABLE_CY + 24);

    // ── Chairs — top row (Dev team, y ≈ 575) ────────────────────────────────
    const TOP_Y = TABLE_CY - TABLE_B - 30;
    const SEAT_XS = [480, 572, 664, 776, 868, 960];
    for (const sx of SEAT_XS) {
      g.beginFill(0x101830, 0.97);
      g.lineStyle(1.2, C_DEV_ACCENT, 0.4);
      g.drawRoundedRect(sx - 17, TOP_Y - 2, 34, 24, 5);
      g.endFill();
      // Chair back
      g.beginFill(0x0d1428, 0.95);
      g.lineStyle(0.8, C_DEV_ACCENT, 0.25);
      g.drawRoundedRect(sx - 14, TOP_Y - 18, 28, 16, 4);
      g.endFill();
    }

    // ── Chairs — bottom row (Marketing team, y ≈ 700) ────────────────────────
    const BOT_Y = TABLE_CY + TABLE_B + 6;
    for (const sx of SEAT_XS) {
      g.beginFill(0x180d28, 0.97);
      g.lineStyle(1.2, C_MKT_ACCENT, 0.4);
      g.drawRoundedRect(sx - 17, BOT_Y, 34, 24, 5);
      g.endFill();
      g.beginFill(0x150a22, 0.95);
      g.lineStyle(0.8, C_MKT_ACCENT, 0.25);
      g.drawRoundedRect(sx - 14, BOT_Y + 24, 28, 16, 4);
      g.endFill();
    }

    // ── Whiteboard (left wall) ───────────────────────────────────────────────
    const WB_X = 20, WB_Y = BOARD_TOP + 18;
    g.beginFill(0xf0f0f8, 0.06);
    g.lineStyle(2, 0x666688, 0.6);
    g.drawRoundedRect(WB_X, WB_Y, 210, 150, 5);
    g.endFill();
    // Mounting bracket
    g.beginFill(0x444466, 0.6);
    g.drawRect(WB_X + 90, WB_Y, 30, 5);
    g.endFill();
    // Drawn content
    for (let li = 0; li < 6; li++) {
      const lw = 50 + li * 22;
      const col = [C_DEV_ACCENT, C_MKT_ACCENT, C_GOLD, 0xef4444, 0x22c55e, C_DEV_ACCENT][li];
      g.lineStyle(1.5, col, 0.55);
      g.moveTo(WB_X + 12, WB_Y + 22 + li * 18);
      g.lineTo(WB_X + 12 + lw, WB_Y + 22 + li * 18);
    }
    // Architecture diagram
    g.lineStyle(1, C_GOLD, 0.5);
    g.drawCircle(WB_X + 175, WB_Y + 55, 24);
    g.lineStyle(1, C_DEV_ACCENT, 0.35);
    g.drawRoundedRect(WB_X + 158, WB_Y + 92, 34, 22, 3);
    g.lineStyle(1, C_GOLD, 0.3);
    g.moveTo(WB_X + 175, WB_Y + 79); g.lineTo(WB_X + 175, WB_Y + 92);
    // Side legend
    g.beginFill(C_MKT_ACCENT, 0.25); g.drawCircle(WB_X + 16, WB_Y + 128, 6); g.endFill();
    g.beginFill(C_DEV_ACCENT, 0.25); g.drawCircle(WB_X + 36, WB_Y + 128, 6); g.endFill();
    g.beginFill(C_GOLD, 0.25);       g.drawCircle(WB_X + 56, WB_Y + 128, 6); g.endFill();

    // ── Presentation Screen (right wall) ────────────────────────────────────
    const PS_X = CANVAS_W - 230, PS_Y = BOARD_TOP + 18;
    g.beginFill(0x04040e, 0.97);
    g.lineStyle(2.5, C_MKT_ACCENT, 0.65);
    g.drawRoundedRect(PS_X, PS_Y, 210, 150, 6);
    g.endFill();
    g.beginFill(0x04040e, 1);
    g.lineStyle(1, C_MKT_ACCENT, 0.2);
    g.drawRoundedRect(PS_X + 4, PS_Y + 4, 202, 142, 4);
    g.endFill();
    // KPI dashboard on screen
    // Top numbers
    const kpis = ['98.2%', '↑14K', '2.1M', '∞ ops'];
    kpis.forEach((_, i) => {
      const kx = PS_X + 12 + i * 48;
      const col = [0x22c55e, C_DEV_ACCENT, C_MKT_ACCENT, C_GOLD][i];
      g.beginFill(col, 0.15);
      g.lineStyle(1, col, 0.4);
      g.drawRoundedRect(kx, PS_Y + 10, 40, 26, 3);
      g.endFill();
      g.beginFill(col, 0.7);
      g.drawCircle(kx + 20, PS_Y + 23, 3);
      g.endFill();
    });
    // Bar chart
    [0.55, 0.82, 0.64, 0.95, 0.72, 0.88, 0.5].forEach((h, i) => {
      const bx = PS_X + 14 + i * 27;
      const bh = h * 80;
      const col = [C_MKT_ACCENT, 0xec4899, C_GOLD, C_DEV_ACCENT, C_MKT_ACCENT, 0x22c55e, 0xec4899][i];
      g.beginFill(col, 0.5);
      g.lineStyle(0);
      g.drawRoundedRect(bx, PS_Y + 135 - bh, 19, bh, 2);
      g.endFill();
      g.beginFill(col, 0.9);
      g.drawCircle(bx + 9, PS_Y + 135 - bh, 3);
      g.endFill();
    });

    // ── Coffee / water station (between whiteboard & table) ──────────────────
    const CF_X = 248, CF_Y = BOARD_TOP + 30;
    g.beginFill(0x0f0f1a, 0.9);
    g.lineStyle(1, C_GOLD, 0.3);
    g.drawRoundedRect(CF_X, CF_Y, 60, 44, 6);
    g.endFill();
    // Coffee machine
    g.beginFill(0x181828, 1);
    g.lineStyle(1, C_GOLD, 0.5);
    g.drawRoundedRect(CF_X + 4, CF_Y + 4, 24, 32, 3);
    g.endFill();
    g.beginFill(C_GOLD, 0.6); g.drawCircle(CF_X + 16, CF_Y + 18, 5); g.endFill();
    g.beginFill(C_GOLD, 0.2); g.drawCircle(CF_X + 16, CF_Y + 18, 9); g.endFill();
    // Water carafe
    g.beginFill(0x0a1520, 0.9);
    g.lineStyle(1, C_DEV_ACCENT, 0.4);
    g.drawRoundedRect(CF_X + 34, CF_Y + 10, 20, 28, 3);
    g.endFill();
    g.beginFill(C_DEV_ACCENT, 0.2);
    g.drawRoundedRect(CF_X + 36, CF_Y + 12, 16, 14, 2);
    g.endFill();

    // ── Decorative corner plants ─────────────────────────────────────────────
    drawPlant(g, 250, BOARD_TOP + 230, 1.1);
    drawPlant(g, CANVAS_W - 250, BOARD_TOP + 230, 1.1);

    // ── Status / activity monitors flanking whiteboard ────────────────────────
    // Left mini monitor
    g.beginFill(0x08081a, 0.95);
    g.lineStyle(1.5, C_DEV_ACCENT, 0.4);
    g.drawRoundedRect(WB_X + 218, WB_Y, 70, 60, 4);
    g.endFill();
    for (let li = 0; li < 5; li++) {
      const lw = 20 + li * 6;
      g.beginFill(C_DEV_ACCENT, 0.3);
      g.drawRoundedRect(WB_X + 224, WB_Y + 8 + li * 10, lw, 5, 1);
      g.endFill();
    }

    // Right mini monitor
    g.beginFill(0x08081a, 0.95);
    g.lineStyle(1.5, C_MKT_ACCENT, 0.4);
    g.drawRoundedRect(PS_X - 78, PS_Y, 70, 60, 4);
    g.endFill();
    for (let li = 0; li < 4; li++) {
      const lw = 14 + li * 8;
      g.beginFill(C_MKT_ACCENT, 0.3);
      g.drawRoundedRect(PS_X - 72, PS_Y + 10 + li * 12, lw, 6, 1);
      g.endFill();
    }
  }, []);

  return <Graphics draw={draw} />;
};

// ─── Zone Labels ──────────────────────────────────────────────────────────────
const ZoneLabels: React.FC = () => {
  const devStyle = new PIXI.TextStyle({
    fontFamily: '"JetBrains Mono", "SF Mono", monospace',
    fontSize: 11,
    fill: '#66dfff',
    letterSpacing: 6,
    fontWeight: '700',
  });
  const mktStyle = new PIXI.TextStyle({
    fontFamily: '"JetBrains Mono", "SF Mono", monospace',
    fontSize: 11,
    fill: '#cc88ff',
    letterSpacing: 6,
    fontWeight: '700',
  });
  const orchStyle = new PIXI.TextStyle({
    fontFamily: 'monospace',
    fontSize: 8,
    fill: '#d4a017',
    letterSpacing: 2,
    fontWeight: '700',
  });
  const boardStyle = new PIXI.TextStyle({
    fontFamily: '"JetBrains Mono", "SF Mono", monospace',
    fontSize: 10,
    fill: '#d4a017',
    letterSpacing: 5,
    fontWeight: '700',
  });
  return (
    <>
      <Text text="DEV STUDIO"  style={devStyle}   x={20}                          y={11} />
      <Text text="CREATIVE HQ" style={mktStyle}   x={MKT_ZONE.x + 20}            y={11} />
      <Text text="NEXUS"       style={orchStyle}   x={CORR_ZONE.x + CORR_ZONE.w / 2} y={14} anchor={[0.5, 0]} />
      <Text text="BOARDROOM"   style={boardStyle}  x={CANVAS_W / 2}              y={BOARD_TOP + 8} anchor={[0.5, 0]} />
    </>
  );
};

// ─── Animated: Code Rain (Dev Zone) ──────────────────────────────────────────
interface CodeDrop { x: number; y: number; speed: number; alpha: number; len: number; }

const CodeRain: React.FC = () => {
  const drops = useRef<CodeDrop[]>([]);
  const gRef  = useRef<PIXI.Graphics>(null);

  if (drops.current.length === 0) {
    for (let i = 0; i < 30; i++) {
      drops.current.push({
        x: Math.random() * DEV_ZONE.w,
        y: Math.random() * WORK_BOTTOM,
        speed: 1.5 + Math.random() * 2.5,
        alpha: 0.1 + Math.random() * 0.35,
        len:   20  + Math.random() * 60,
      });
    }
  }

  useTick((delta) => {
    if (!gRef.current) return;
    const g = gRef.current;
    g.clear();
    for (const d of drops.current) {
      d.y += d.speed * delta;
      if (d.y > WORK_BOTTOM + d.len) d.y = -d.len;
      g.lineStyle(1,   C_DEV_ACCENT, d.alpha * 0.22);
      g.moveTo(d.x, d.y - d.len);
      g.lineTo(d.x, d.y - d.len * 0.5);
      g.lineStyle(1.5, C_DEV_ACCENT, d.alpha * 0.7);
      g.moveTo(d.x, d.y - d.len * 0.5);
      g.lineTo(d.x, d.y);
      g.beginFill(C_DEV_ACCENT, d.alpha);
      g.drawRect(d.x - 0.5, d.y, 1.5, 3);
      g.endFill();
    }
  });

  return <Graphics ref={gRef} x={DEV_ZONE.x} y={0} />;
};

// ─── Animated: Creative Sparks (Marketing Zone) ──────────────────────────────
interface Spark { x: number; y: number; vx: number; vy: number; r: number; alpha: number; color: number; life: number; maxLife: number; }

const CreativeSparks: React.FC = () => {
  const sparks = useRef<Spark[]>([]);
  const gRef   = useRef<PIXI.Graphics>(null);
  const COLORS  = [C_MKT_ACCENT, 0xec4899, 0xf97316, 0xfbbf24, 0xa855f7];

  useTick((delta) => {
    if (!gRef.current) return;
    const g = gRef.current;
    g.clear();
    if (sparks.current.length < 36 && Math.random() < 0.22) {
      sparks.current.push({
        x: MKT_ZONE.x + 200 + Math.random() * (MKT_ZONE.w - 220),
        y: 80 + Math.random() * (WORK_BOTTOM - 100),
        vx: (Math.random() - 0.5) * 1.2,
        vy: -0.8 - Math.random() * 1.4,
        r: 2 + Math.random() * 3,
        alpha: 0.8,
        color: COLORS[Math.floor(Math.random() * COLORS.length)],
        life: 0,
        maxLife: 60 + Math.random() * 80,
      });
    }
    sparks.current = sparks.current.filter(s => s.life < s.maxLife);
    for (const s of sparks.current) {
      s.life += delta;
      s.x += s.vx * delta;
      s.y += s.vy * delta;
      s.vy += 0.015 * delta;
      const p = s.life / s.maxLife;
      const a = s.alpha * (1 - p);
      const r = s.r * (1 - p * 0.5);
      g.beginFill(s.color, a);
      g.drawPolygon([
        s.x, s.y - r * 2,
        s.x + r * 0.5, s.y - r * 0.5,
        s.x + r * 2, s.y,
        s.x + r * 0.5, s.y + r * 0.5,
        s.x, s.y + r * 2,
        s.x - r * 0.5, s.y + r * 0.5,
        s.x - r * 2, s.y,
        s.x - r * 0.5, s.y - r * 0.5,
      ]);
      g.endFill();
    }
  });

  return <Graphics ref={gRef} />;
};

// ─── Animated: Data Streams (Corridor) ───────────────────────────────────────
interface Stream { y: number; dir: 1 | -1; speed: number; alpha: number; color: number; }

const DataStreams: React.FC = () => {
  const streams = useRef<Stream[]>([]);
  const gRef    = useRef<PIXI.Graphics>(null);
  const CX = CORR_ZONE.x + CORR_ZONE.w / 2;

  if (streams.current.length === 0) {
    for (let i = 0; i < 18; i++) {
      streams.current.push({
        y: Math.random() * CANVAS_H,
        dir: Math.random() > 0.5 ? 1 : -1,
        speed: 1 + Math.random() * 2,
        alpha: 0.3 + Math.random() * 0.6,
        color: i % 3 === 0 ? C_GOLD : i % 3 === 1 ? C_DEV_ACCENT : C_MKT_ACCENT,
      });
    }
  }

  useTick((delta) => {
    if (!gRef.current) return;
    const g = gRef.current;
    g.clear();
    for (const s of streams.current) {
      s.y += s.speed * s.dir * delta;
      if (s.y > CANVAS_H + 20) s.y = -20;
      if (s.y < -20) s.y = CANVAS_H + 20;
      for (let t = 0; t < 5; t++) {
        const ty = s.y - s.dir * t * 8;
        const ta = s.alpha * (1 - t / 5);
        g.beginFill(s.color, ta);
        g.drawCircle(CX + Math.sin(s.y * 0.02 + t) * 4, ty, 2 - t * 0.3);
        g.endFill();
      }
    }
  });

  return <Graphics ref={gRef} />;
};

// ─── Animated: Server LEDs (Dev Zone) ────────────────────────────────────────
const ServerLEDs: React.FC = () => {
  const gRef   = useRef<PIXI.Graphics>(null);
  const tick   = useRef(0);
  const RACK_X = DEV_ZONE.w - 106, RACK_Y = 52;

  useTick((delta) => {
    if (!gRef.current) return;
    tick.current += delta * 0.05;
    const g = gRef.current;
    g.clear();
    for (let si = 0; si < 8; si++) {
      const sy  = RACK_Y + 12 + si * 23;
      const on  = Math.sin(tick.current * (1 + si * 0.4)) > 0.2;
      if (!on) continue;
      const col = si % 3 === 0 ? 0x00ff88 : si % 3 === 1 ? C_DEV_ACCENT : C_GOLD;
      g.beginFill(col, 0.9);
      g.drawCircle(RACK_X + 74, sy + 8, 2.5);
      g.endFill();
      g.beginFill(col, 0.2);
      g.drawCircle(RACK_X + 74, sy + 8, 6);
      g.endFill();
    }
  });

  return <Graphics ref={gRef} />;
};

// ─── Animated: NEXUS holographic radar ───────────────────────────────────────
const NexusRadar: React.FC = () => {
  const gRef = useRef<PIXI.Graphics>(null);
  const tick = useRef(0);
  const CX   = CORR_ZONE.x + CORR_ZONE.w / 2;
  const CY   = CANVAS_H / 2 - 45;

  useTick((delta) => {
    if (!gRef.current) return;
    tick.current += delta * 0.018;
    const g = gRef.current;
    g.clear();

    // Rotating scan beam
    const angle = tick.current;
    const r = 20;
    g.lineStyle(2, C_GOLD, 0.55);
    g.moveTo(CX, CY);
    g.lineTo(CX + Math.cos(angle) * r, CY + Math.sin(angle) * r);

    // Trailing glow arc
    for (let i = 1; i <= 8; i++) {
      const a = angle - i * 0.08;
      g.lineStyle(0);
      g.beginFill(C_GOLD, 0.06 * (9 - i) / 9);
      const ar = r * 0.85;
      g.drawPolygon([
        CX, CY,
        CX + Math.cos(a) * ar, CY + Math.sin(a) * ar,
        CX + Math.cos(a - 0.08) * ar, CY + Math.sin(a - 0.08) * ar,
      ]);
      g.endFill();
    }

    // Pulsing outer ring
    const pulse = 0.3 + Math.sin(tick.current * 2) * 0.2;
    g.lineStyle(1, C_GOLD, pulse);
    g.drawCircle(CX, CY, r + 5 + Math.sin(tick.current * 3) * 2);
  });

  return <Graphics ref={gRef} />;
};

// ─── Animated: Boardroom holo pulse ──────────────────────────────────────────
const BoardroomHolo: React.FC = () => {
  const gRef = useRef<PIXI.Graphics>(null);
  const tick = useRef(0);

  useTick((delta) => {
    if (!gRef.current) return;
    tick.current += delta * 0.015;
    const g = gRef.current;
    g.clear();

    // Pulsing rings around table center
    for (let i = 0; i < 3; i++) {
      const phase = tick.current + i * 1.05;
      const radius = TABLE_A * 0.22 + Math.sin(phase) * 8;
      const alpha  = (0.08 + Math.sin(phase) * 0.04) * (1 - i * 0.25);
      g.lineStyle(1, C_GOLD, alpha);
      g.drawEllipse(TABLE_CX, TABLE_CY, radius, radius * (TABLE_B / TABLE_A));
    }

    // Rotating cross hair
    const a = tick.current * 0.6;
    g.lineStyle(0.8, C_GOLD, 0.15 + Math.sin(tick.current * 2) * 0.08);
    g.moveTo(TABLE_CX + Math.cos(a) * 60, TABLE_CY + Math.sin(a) * 18);
    g.lineTo(TABLE_CX + Math.cos(a + Math.PI) * 60, TABLE_CY + Math.sin(a + Math.PI) * 18);
    g.moveTo(TABLE_CX + Math.cos(a + Math.PI / 2) * 60, TABLE_CY + Math.sin(a + Math.PI / 2) * 18);
    g.lineTo(TABLE_CX + Math.cos(a + 3 * Math.PI / 2) * 60, TABLE_CY + Math.sin(a + 3 * Math.PI / 2) * 18);
  });

  return <Graphics ref={gRef} />;
};

// ─── Cursor blink ─────────────────────────────────────────────────────────────
const CursorBlink: React.FC = () => {
  const gRef = useRef<PIXI.Graphics>(null);
  const tick = useRef(0);

  useTick((delta) => {
    if (!gRef.current) return;
    tick.current += delta * 0.04;
    const g = gRef.current;
    g.clear();
    if (Math.sin(tick.current * 5) > 0) {
      g.beginFill(C_DEV_ACCENT, 0.9);
      g.drawRect(188 + 10, 300 + 60, 8, 12);
      g.endFill();
    }
  });

  return <Graphics ref={gRef} />;
};

// ─── Idle Wander System (runs outside Stage) ──────────────────────────────────
/** Triggers gentle idle wandering for agents at desk. Runs every 4 seconds. */
const IdleWanderSystem: React.FC = () => {
  const wanderIdleAgents = useOfficeStore((s) => s.wanderIdleAgents);

  useEffect(() => {
    const id = setInterval(wanderIdleAgents, 4000);
    return () => clearInterval(id);
  }, [wanderIdleAgents]);

  return null;
};

// ─── Main OfficeLayout ────────────────────────────────────────────────────────
interface OfficeLayoutProps {
  onAgentClick: (agentId: string) => void;
}

export const OfficeLayout: React.FC<OfficeLayoutProps> = ({ onAgentClick }) => {
  const agents      = useOfficeStore((s) => s.agents);
  const tasks       = useOfficeStore((s) => s.tasks);
  const agentList   = Object.values(agents);
  const activeTasks = Object.values(tasks).filter(
    (t) => t.assigned_agent_id && t.status !== 'completed' && t.status !== 'failed'
  );

  return (
    <>
      {/* Idle wander runs outside Stage so it can use React lifecycle hooks */}
      <IdleWanderSystem />

      <Stage
        width={CANVAS_W}
        height={CANVAS_H}
        options={{
          backgroundColor: 0x03030a,
          antialias: true,
          resolution: Math.min(window.devicePixelRatio || 1, 2),
          autoDensity: true,
          powerPreference: 'high-performance',
        }}
      >
        {/* ── Zone backgrounds ── */}
        <DevBackground />
        <MktBackground />
        <CorrBackground />
        <Boardroom />
        <ZoneLabels />

        {/* ── Ambient animations ── */}
        <CodeRain />
        <CreativeSparks />
        <DataStreams />
        <ServerLEDs />
        <NexusRadar />
        <BoardroomHolo />
        <CursorBlink />

        {/* ── Task bubbles ── */}
        {activeTasks.map((task) => {
          const agent = task.assigned_agent_id ? agents[task.assigned_agent_id] : null;
          if (!agent) return null;
          return <TaskBubble key={task.task_id} task={task} agent={agent} />;
        })}

        {/* ── Agent sprites ── */}
        {agentList.map((agent) => (
          <AgentSprite key={agent.agent_id} agent={agent} onAgentClick={onAgentClick} />
        ))}
      </Stage>
    </>
  );
};

export default OfficeLayout;
