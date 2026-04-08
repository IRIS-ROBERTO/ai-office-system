/**
 * AI Office System — Premium Office Layout
 * Two fully realized offices rendered in WebGL via PixiJS:
 *   Dev Zone   → Cyberpunk tech noir  (electric blue, server racks, code rain)
 *   Marketing  → Creative studio      (vibrant violet/pink, mood boards, spark particles)
 *   Corridor   → Command nexus        (gold hologram, data streams)
 */
import React, { useCallback, useRef } from 'react';
import { Stage, Graphics, Text, useTick } from '@pixi/react';
import * as PIXI from 'pixi.js';
import { useOfficeStore } from '../state/officeStore';
import AgentSprite from '../components/agents/AgentSprite';
import TaskBubble from '../components/agents/TaskBubble';

// ─── Canvas dimensions ────────────────────────────────────────────────────────
export const CANVAS_W = 1440;
export const CANVAS_H = 810;

// ─── Zone boundaries ──────────────────────────────────────────────────────────
export const DEV_ZONE    = { x: 0,    y: 0, w: 636, h: CANVAS_H };
export const CORR_ZONE   = { x: 636,  y: 0, w: 108, h: CANVAS_H };
export const MKT_ZONE    = { x: 744,  y: 0, w: 696, h: CANVAS_H };

// Colors
const C_DEV_BG      = 0x060b14;
const C_DEV_GRID    = 0x0d2137;
const C_DEV_ACCENT  = 0x00c8ff;
const C_MKT_BG      = 0x0d0718;
const C_MKT_GRID    = 0x1d0b30;
const C_MKT_ACCENT  = 0xb144ff;
const C_CORR_BG     = 0x03030a;
const C_GOLD        = 0xfbbf24;

// ─── Utility ──────────────────────────────────────────────────────────────────
// (lerp reserved for future animation use)

// ─── Dev Zone Background ─────────────────────────────────────────────────────
const DevBackground: React.FC = () => {
  const draw = useCallback((g: PIXI.Graphics) => {
    g.clear();

    // Base fill
    g.beginFill(C_DEV_BG);
    g.drawRect(DEV_ZONE.x, DEV_ZONE.y, DEV_ZONE.w, DEV_ZONE.h);
    g.endFill();

    // Subtle hex-grid floor (isometric feel)
    const HEX = 36;
    g.lineStyle(0.5, C_DEV_GRID, 0.6);
    for (let row = 0; row < 30; row++) {
      for (let col = 0; col < 22; col++) {
        const ox = col * HEX * 1.5;
        const oy = row * HEX * 0.866 + (col % 2 === 0 ? 0 : HEX * 0.433);
        if (ox > DEV_ZONE.w + 10) continue;
        // Flat-top hexagon
        for (let i = 0; i < 6; i++) {
          const a1 = (Math.PI / 180) * (60 * i);
          const a2 = (Math.PI / 180) * (60 * (i + 1));
          const r = HEX * 0.5;
          g.moveTo(ox + r * Math.cos(a1), oy + r * Math.sin(a1));
          g.lineTo(ox + r * Math.cos(a2), oy + r * Math.sin(a2));
        }
      }
    }

    // Floor accent line
    g.lineStyle(1.5, C_DEV_ACCENT, 0.15);
    g.moveTo(DEV_ZONE.x, CANVAS_H - 120);
    g.lineTo(DEV_ZONE.x + DEV_ZONE.w, CANVAS_H - 120);

    // ─── Server Rack (top-right corner) ──────────────────────────────────────
    const RACK_X = DEV_ZONE.w - 100, RACK_Y = 60;
    g.beginFill(0x0a1a28, 1);
    g.lineStyle(1.5, C_DEV_ACCENT, 0.35);
    g.drawRoundedRect(RACK_X, RACK_Y, 84, 220, 4);
    g.endFill();
    // Rack slots
    for (let si = 0; si < 9; si++) {
      const slotY = RACK_Y + 12 + si * 22;
      g.beginFill(0x0d2a3a, 1);
      g.lineStyle(0.5, C_DEV_ACCENT, 0.2);
      g.drawRoundedRect(RACK_X + 8, slotY, 68, 16, 2);
      g.endFill();
      // LED indicator
      const ledColor = si % 3 === 0 ? 0x00ff88 : si % 3 === 1 ? C_DEV_ACCENT : 0xfbbf24;
      g.beginFill(ledColor, 0.9);
      g.drawCircle(RACK_X + 74, slotY + 8, 2.5);
      g.endFill();
    }
    // Rack label
    g.lineStyle(0);
    g.beginFill(C_DEV_ACCENT, 0.08);
    g.drawRoundedRect(RACK_X + 4, RACK_Y + 206, 76, 10, 2);
    g.endFill();

    // ─── Workstation Clusters — Row A (y=140) ────────────────────────────────
    drawDevWorkstation(g, 40,  130);
    drawDevWorkstation(g, 180, 130);
    drawDevWorkstation(g, 320, 130);

    // ─── Workstation Clusters — Row B (y=310) ────────────────────────────────
    drawDevWorkstation(g, 40,  310);
    drawDevWorkstation(g, 180, 310);
    drawDevWorkstation(g, 320, 310);

    // ─── Code Review Screen (center, y=480) ──────────────────────────────────
    const SCR_X = 60, SCR_Y = 480, SCR_W = 460, SCR_H = 160;
    g.beginFill(0x03111d, 0.95);
    g.lineStyle(1.5, C_DEV_ACCENT, 0.5);
    g.drawRoundedRect(SCR_X, SCR_Y, SCR_W, SCR_H, 6);
    g.endFill();
    // Code lines
    for (let li = 0; li < 7; li++) {
      const lineW = 80 + Math.random() * 200;
      const lineColor = [C_DEV_ACCENT, 0x00ff88, 0xfbbf24, 0xff6b6b][li % 4];
      g.beginFill(lineColor, 0.35);
      g.drawRoundedRect(SCR_X + 16 + (li % 2) * 24, SCR_Y + 20 + li * 19, lineW, 8, 2);
      g.endFill();
    }
    // Cursor blink placeholder
    g.beginFill(C_DEV_ACCENT, 0.8);
    g.drawRect(SCR_X + 16, SCR_Y + 140, 8, 12);
    g.endFill();

    // ─── Lounge area (bottom) ─────────────────────────────────────────────────
    // Sofa
    g.beginFill(0x0d2137, 0.9);
    g.lineStyle(1.5, C_DEV_ACCENT, 0.25);
    g.drawRoundedRect(30, CANVAS_H - 100, 540, 70, 12);
    g.endFill();
    for (let c = 0; c < 4; c++) {
      g.beginFill(0x122840, 0.9);
      g.lineStyle(0.5, C_DEV_ACCENT, 0.15);
      g.drawRoundedRect(42 + c * 130, CANVAS_H - 92, 112, 52, 10);
      g.endFill();
    }

    // Zone label bar (top)
    g.beginFill(C_DEV_ACCENT, 0.06);
    g.drawRect(0, 0, DEV_ZONE.w, 38);
    g.endFill();
    g.lineStyle(1, C_DEV_ACCENT, 0.3);
    g.moveTo(0, 38);
    g.lineTo(DEV_ZONE.w, 38);

  }, []);

  return <Graphics draw={draw} />;
};

function drawDevWorkstation(g: PIXI.Graphics, x: number, y: number) {
  // Desk surface
  g.beginFill(0x0d2137, 0.85);
  g.lineStyle(1, C_DEV_ACCENT, 0.3);
  g.drawRoundedRect(x, y, 110, 54, 5);
  g.endFill();
  // Left monitor
  g.beginFill(0x020a12, 0.98);
  g.lineStyle(1, C_DEV_ACCENT, 0.5);
  g.drawRoundedRect(x + 4, y - 56, 44, 36, 3);
  g.endFill();
  // Screen glow
  g.beginFill(C_DEV_ACCENT, 0.06);
  g.drawRoundedRect(x + 6, y - 54, 40, 32, 2);
  g.endFill();
  // Code on left monitor (colored bars)
  for (let i = 0; i < 4; i++) {
    g.beginFill([C_DEV_ACCENT, 0x00ff88, 0xfbbf24, 0xff6b6b][i], 0.3);
    g.drawRoundedRect(x + 7, y - 52 + i * 7, 20 + (i * 5) % 16, 4, 1);
    g.endFill();
  }
  // Right monitor
  g.beginFill(0x020a12, 0.98);
  g.lineStyle(1, C_DEV_ACCENT, 0.5);
  g.drawRoundedRect(x + 60, y - 56, 44, 36, 3);
  g.endFill();
  g.beginFill(C_DEV_ACCENT, 0.04);
  g.drawRoundedRect(x + 62, y - 54, 40, 32, 2);
  g.endFill();
  // Monitor stands
  g.lineStyle(1.5, C_DEV_GRID, 0.8);
  g.moveTo(x + 26, y - 20); g.lineTo(x + 26, y);
  g.moveTo(x + 82, y - 20); g.lineTo(x + 82, y);
  // Keyboard
  g.beginFill(0x091624, 1);
  g.lineStyle(0.5, C_DEV_ACCENT, 0.2);
  g.drawRoundedRect(x + 12, y + 36, 82, 14, 2);
  g.endFill();
}

// ─── Marketing Zone Background ────────────────────────────────────────────────
const MktBackground: React.FC = () => {
  const draw = useCallback((g: PIXI.Graphics) => {
    g.clear();

    // Base fill
    g.beginFill(C_MKT_BG);
    g.drawRect(MKT_ZONE.x, MKT_ZONE.y, MKT_ZONE.w, MKT_ZONE.h);
    g.endFill();

    // Diagonal stripe floor pattern
    g.lineStyle(0.6, C_MKT_GRID, 0.55);
    const STRIPE = 42;
    for (let i = -20; i < 60; i++) {
      const ox = MKT_ZONE.x + i * STRIPE;
      g.moveTo(ox, 0);
      g.lineTo(ox + CANVAS_H, CANVAS_H);
    }

    // Floor accent line
    g.lineStyle(1.5, C_MKT_ACCENT, 0.12);
    g.moveTo(MKT_ZONE.x, CANVAS_H - 120);
    g.lineTo(MKT_ZONE.x + MKT_ZONE.w, CANVAS_H - 120);

    // ─── Mood Board Wall (left of marketing zone) ─────────────────────────────
    const MB_X = MKT_ZONE.x + 10, MB_Y = 55, MB_W = 160, MB_H = 320;
    g.beginFill(0x120820, 0.95);
    g.lineStyle(1.5, C_MKT_ACCENT, 0.4);
    g.drawRoundedRect(MB_X, MB_Y, MB_W, MB_H, 6);
    g.endFill();
    // Cards on mood board
    const cardColors = [0xec4899, 0xa855f7, 0xf97316, 0x10b981, 0x3b82f6, 0xfbbf24, 0xef4444, 0x06b6d4];
    const positions = [
      [10, 14], [90, 14], [10, 100], [90, 100],
      [40, 186], [10, 260], [90, 200], [50, 280],
    ];
    positions.forEach(([cx, cy], idx) => {
      const cw = 56 + (idx % 2) * 16, ch = 70 + (idx % 3) * 12;
      // Simulate card rotation via skew (graphics API)
      g.beginFill(cardColors[idx % cardColors.length], 0.22);
      g.lineStyle(1, cardColors[idx % cardColors.length], 0.5);
      g.drawRoundedRect(MB_X + cx, MB_Y + cy, cw, ch, 3);
      g.endFill();
      // Lines on card (content)
      g.lineStyle(0);
      g.beginFill(cardColors[idx % cardColors.length], 0.5);
      g.drawRoundedRect(MB_X + cx + 4, MB_Y + cy + ch - 20, cw - 8, 5, 1);
      g.drawRoundedRect(MB_X + cx + 4, MB_Y + cy + ch - 12, (cw - 8) * 0.6, 5, 1);
      g.endFill();
    });
    // Pin dots
    positions.forEach(([cx, cy]) => {
      g.beginFill(0xffffff, 0.8);
      g.drawCircle(MB_X + cx + 30, MB_Y + cy + 5, 3);
      g.endFill();
    });

    // ─── Creative Workstations (row A) ────────────────────────────────────────
    drawMktWorkstation(g, MKT_ZONE.x + 200, 130);
    drawMktWorkstation(g, MKT_ZONE.x + 360, 130);
    drawMktWorkstation(g, MKT_ZONE.x + 520, 130);

    // ─── Creative Workstations (row B) ────────────────────────────────────────
    drawMktWorkstation(g, MKT_ZONE.x + 200, 310);
    drawMktWorkstation(g, MKT_ZONE.x + 360, 310);
    drawMktWorkstation(g, MKT_ZONE.x + 520, 310);

    // ─── Large Presentation Screen ────────────────────────────────────────────
    const PS_X = MKT_ZONE.x + 190, PS_Y = 480, PS_W = 480, PS_H = 160;
    g.beginFill(0x08021a, 0.95);
    g.lineStyle(2, C_MKT_ACCENT, 0.55);
    g.drawRoundedRect(PS_X, PS_Y, PS_W, PS_H, 8);
    g.endFill();
    // Gradient-like fill
    g.beginFill(C_MKT_ACCENT, 0.04);
    g.drawRoundedRect(PS_X + 2, PS_Y + 2, PS_W - 4, PS_H / 2, 6);
    g.endFill();
    // Bar chart (analytics viz)
    const bars = [0.4, 0.7, 0.55, 0.9, 0.65, 0.8, 0.5, 0.75];
    bars.forEach((h, i) => {
      const bx = PS_X + 40 + i * 50, by = PS_Y + 140;
      const bh = h * 100;
      const col = [C_MKT_ACCENT, 0xec4899, 0xa855f7, C_MKT_ACCENT][i % 4];
      g.beginFill(col, 0.55);
      g.lineStyle(0);
      g.drawRoundedRect(bx, by - bh, 28, bh, 3);
      g.endFill();
      // Top glow dot
      g.beginFill(col, 0.9);
      g.drawCircle(bx + 14, by - bh, 4);
      g.endFill();
    });

    // ─── Plants (decorative) ─────────────────────────────────────────────────
    drawPlant(g, MKT_ZONE.x + 660, 70);
    drawPlant(g, MKT_ZONE.x + 14, 680);

    // ─── Lounge sofa (bottom) ─────────────────────────────────────────────────
    g.beginFill(0x1d0b30, 0.9);
    g.lineStyle(1.5, C_MKT_ACCENT, 0.25);
    g.drawRoundedRect(MKT_ZONE.x + 30, CANVAS_H - 100, 620, 70, 12);
    g.endFill();
    for (let c = 0; c < 5; c++) {
      g.beginFill(0x28103e, 0.9);
      g.lineStyle(0.5, C_MKT_ACCENT, 0.15);
      g.drawRoundedRect(MKT_ZONE.x + 42 + c * 120, CANVAS_H - 92, 104, 52, 10);
      g.endFill();
    }

    // Zone label bar (top)
    g.beginFill(C_MKT_ACCENT, 0.06);
    g.drawRect(MKT_ZONE.x, 0, MKT_ZONE.w, 38);
    g.endFill();
    g.lineStyle(1, C_MKT_ACCENT, 0.3);
    g.moveTo(MKT_ZONE.x, 38);
    g.lineTo(MKT_ZONE.x + MKT_ZONE.w, 38);

  }, []);

  return <Graphics draw={draw} />;
};

function drawMktWorkstation(g: PIXI.Graphics, x: number, y: number) {
  // Curved desk (rounded trapezoid feel)
  g.beginFill(0x1a0a28, 0.88);
  g.lineStyle(1, C_MKT_ACCENT, 0.3);
  g.drawRoundedRect(x, y, 120, 54, 10);
  g.endFill();
  // Widescreen monitor
  g.beginFill(0x08020f, 0.98);
  g.lineStyle(1.5, C_MKT_ACCENT, 0.5);
  g.drawRoundedRect(x + 4, y - 54, 112, 42, 4);
  g.endFill();
  // Gradient fill on screen
  g.beginFill(C_MKT_ACCENT, 0.05);
  g.drawRoundedRect(x + 6, y - 52, 108, 38, 3);
  g.endFill();
  // Creative content on screen (abstract shapes)
  g.beginFill(0xec4899, 0.4);
  g.drawCircle(x + 30, y - 32, 12);
  g.endFill();
  g.beginFill(C_MKT_ACCENT, 0.4);
  g.drawRoundedRect(x + 50, y - 48, 55, 30, 4);
  g.endFill();
  // Monitor stand
  g.lineStyle(2, C_MKT_GRID, 0.8);
  g.moveTo(x + 60, y - 12); g.lineTo(x + 60, y);
  // Stylus/tablet
  g.beginFill(0x12082a, 1);
  g.lineStyle(0.5, C_MKT_ACCENT, 0.2);
  g.drawRoundedRect(x + 8, y + 36, 70, 14, 3);
  g.endFill();
}

function drawPlant(g: PIXI.Graphics, x: number, y: number) {
  // Pot
  g.beginFill(0x2d1818, 1);
  g.lineStyle(1, 0x4a2020, 0.8);
  g.drawRoundedRect(x - 14, y, 28, 30, 4);
  g.endFill();
  // Stem
  g.lineStyle(2, 0x1a4a20, 0.9);
  g.moveTo(x, y); g.lineTo(x, y - 30);
  // Leaves
  for (let i = 0; i < 3; i++) {
    const a = (i / 3) * Math.PI;
    g.beginFill(0x1a6a20, 0.7);
    g.lineStyle(0);
    g.drawEllipse(x + Math.cos(a) * 18, y - 20 - i * 8, 14, 8);
    g.endFill();
  }
}

// ─── Orchestrator Corridor ────────────────────────────────────────────────────
const CorrBackground: React.FC = () => {
  const draw = useCallback((g: PIXI.Graphics) => {
    g.clear();

    // Deep black base
    g.beginFill(C_CORR_BG);
    g.drawRect(CORR_ZONE.x, CORR_ZONE.y, CORR_ZONE.w, CORR_ZONE.h);
    g.endFill();

    // Side borders
    g.lineStyle(1.5, C_DEV_ACCENT, 0.25);
    g.moveTo(CORR_ZONE.x, 0); g.lineTo(CORR_ZONE.x, CANVAS_H);
    g.lineStyle(1.5, C_MKT_ACCENT, 0.25);
    g.moveTo(CORR_ZONE.x + CORR_ZONE.w, 0);
    g.lineTo(CORR_ZONE.x + CORR_ZONE.w, CANVAS_H);

    // Central spine line
    const CX = CORR_ZONE.x + CORR_ZONE.w / 2;
    g.lineStyle(1, C_GOLD, 0.2);
    g.moveTo(CX, 0); g.lineTo(CX, CANVAS_H);

    // Command node platform (center of corridor)
    const NODE_Y = CANVAS_H / 2 - 50;
    g.beginFill(0x0d0b00, 0.95);
    g.lineStyle(2, C_GOLD, 0.6);
    g.drawRoundedRect(CORR_ZONE.x + 8, NODE_Y, CORR_ZONE.w - 16, 100, 8);
    g.endFill();
    // Hologram ring
    g.lineStyle(1.5, C_GOLD, 0.5);
    g.drawCircle(CX, NODE_Y + 50, 24);
    g.lineStyle(0.5, C_GOLD, 0.25);
    g.drawCircle(CX, NODE_Y + 50, 34);
    g.drawCircle(CX, NODE_Y + 50, 40);
    // Core dot
    g.beginFill(C_GOLD, 0.8);
    g.drawCircle(CX, NODE_Y + 50, 5);
    g.endFill();

    // Zone bar
    g.beginFill(C_GOLD, 0.06);
    g.drawRect(CORR_ZONE.x, 0, CORR_ZONE.w, 38);
    g.endFill();

  }, []);

  return <Graphics draw={draw} />;
};

// ─── Animated: Code Rain Particles (Dev Zone) ─────────────────────────────────
interface CodeDrop { x: number; y: number; speed: number; alpha: number; len: number; }

const CodeRain: React.FC = () => {
  const drops = useRef<CodeDrop[]>([]);
  const gRef = useRef<PIXI.Graphics>(null);

  if (drops.current.length === 0) {
    for (let i = 0; i < 35; i++) {
      drops.current.push({
        x: Math.random() * DEV_ZONE.w,
        y: Math.random() * CANVAS_H,
        speed: 1.5 + Math.random() * 2.5,
        alpha: 0.15 + Math.random() * 0.4,
        len: 20 + Math.random() * 60,
      });
    }
  }

  useTick((delta) => {
    if (!gRef.current) return;
    const g = gRef.current;
    g.clear();
    for (const d of drops.current) {
      d.y += d.speed * delta;
      if (d.y > CANVAS_H + d.len) d.y = -d.len;
      // Gradient trail
      g.lineStyle(1, C_DEV_ACCENT, d.alpha * 0.25);
      g.moveTo(d.x, d.y - d.len);
      g.lineTo(d.x, d.y - d.len * 0.5);
      g.lineStyle(1.5, C_DEV_ACCENT, d.alpha * 0.7);
      g.moveTo(d.x, d.y - d.len * 0.5);
      g.lineTo(d.x, d.y);
      // Bright head
      g.beginFill(C_DEV_ACCENT, d.alpha);
      g.drawRect(d.x - 0.5, d.y, 1.5, 3);
      g.endFill();
    }
  });

  return <Graphics ref={gRef} x={DEV_ZONE.x} y={0} />;
};

// ─── Animated: Creative Sparks (Marketing Zone) ───────────────────────────────
interface Spark { x: number; y: number; vx: number; vy: number; r: number; alpha: number; color: number; life: number; maxLife: number; }

const CreativeSparks: React.FC = () => {
  const sparks = useRef<Spark[]>([]);
  const gRef = useRef<PIXI.Graphics>(null);
  const tick = useRef(0);
  const SPARK_COLORS = [C_MKT_ACCENT, 0xec4899, 0xf97316, 0xfbbf24, 0xa855f7];

  useTick((delta) => {
    if (!gRef.current) return;
    tick.current += delta;
    const g = gRef.current;
    g.clear();

    // Spawn new sparks
    if (sparks.current.length < 40 && Math.random() < 0.25) {
      const sx = MKT_ZONE.x + 200 + Math.random() * (MKT_ZONE.w - 220);
      const sy = 100 + Math.random() * 550;
      sparks.current.push({
        x: sx, y: sy,
        vx: (Math.random() - 0.5) * 1.2,
        vy: -0.8 - Math.random() * 1.5,
        r: 2 + Math.random() * 3,
        alpha: 0.8 + Math.random() * 0.2,
        color: SPARK_COLORS[Math.floor(Math.random() * SPARK_COLORS.length)],
        life: 0,
        maxLife: 60 + Math.random() * 80,
      });
    }

    sparks.current = sparks.current.filter(s => s.life < s.maxLife);
    for (const s of sparks.current) {
      s.life += delta;
      s.x += s.vx * delta;
      s.y += s.vy * delta;
      s.vy += 0.015 * delta; // soft gravity
      const progress = s.life / s.maxLife;
      const a = s.alpha * (1 - progress);
      const radius = s.r * (1 - progress * 0.5);
      // Star shape (4-point)
      g.beginFill(s.color, a);
      g.drawPolygon([
        s.x, s.y - radius * 2,
        s.x + radius * 0.5, s.y - radius * 0.5,
        s.x + radius * 2, s.y,
        s.x + radius * 0.5, s.y + radius * 0.5,
        s.x, s.y + radius * 2,
        s.x - radius * 0.5, s.y + radius * 0.5,
        s.x - radius * 2, s.y,
        s.x - radius * 0.5, s.y - radius * 0.5,
      ]);
      g.endFill();
    }
  });

  return <Graphics ref={gRef} />;
};

// ─── Animated: Data Streams (Corridor) ────────────────────────────────────────
interface Stream { y: number; dir: 1 | -1; speed: number; alpha: number; color: number; }

const DataStreams: React.FC = () => {
  const streams = useRef<Stream[]>([]);
  const gRef = useRef<PIXI.Graphics>(null);
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

      // Trailing dot chain
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

// ─── Animated: Blinking Server LEDs ──────────────────────────────────────────
const ServerLEDs: React.FC = () => {
  const gRef = useRef<PIXI.Graphics>(null);
  const tick = useRef(0);
  const RACK_X = DEV_ZONE.w - 100, RACK_Y = 60;

  useTick((delta) => {
    if (!gRef.current) return;
    tick.current += delta * 0.05;
    const g = gRef.current;
    g.clear();
    for (let si = 0; si < 9; si++) {
      const slotY = RACK_Y + 12 + si * 22;
      const on = Math.sin(tick.current * (1 + si * 0.4)) > 0.2;
      if (!on) continue;
      const col = si % 3 === 0 ? 0x00ff88 : si % 3 === 1 ? C_DEV_ACCENT : C_GOLD;
      g.beginFill(col, 0.9);
      g.drawCircle(RACK_X + 74, slotY + 8, 2.5);
      g.endFill();
      // Glow
      g.beginFill(col, 0.2);
      g.drawCircle(RACK_X + 74, slotY + 8, 6);
      g.endFill();
    }
  });

  return <Graphics ref={gRef} />;
};

// ─── Animated: Screen content cursor blink ────────────────────────────────────
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
      g.drawRect(76, 532, 8, 12);
      g.endFill();
    }
  });

  return <Graphics ref={gRef} />;
};

// ─── Zone Labels (HTML text rendered via PixiJS) ──────────────────────────────
// Use semi-transparent fill strings since TextStyle has no 'alpha' in pixi v7
const ZoneLabels: React.FC = () => {
  const devStyle = new PIXI.TextStyle({
    fontFamily: '"JetBrains Mono", "SF Mono", monospace',
    fontSize: 11,
    fill: '#66dfff',   // C_DEV_ACCENT at ~70% brightness
    letterSpacing: 6,
    fontWeight: '700',
  });
  const mktStyle = new PIXI.TextStyle({
    fontFamily: '"JetBrains Mono", "SF Mono", monospace',
    fontSize: 11,
    fill: '#cc88ff',   // C_MKT_ACCENT at ~70% brightness
    letterSpacing: 6,
    fontWeight: '700',
  });
  const orchStyle = new PIXI.TextStyle({
    fontFamily: 'monospace',
    fontSize: 8,
    fill: '#d4a017',   // C_GOLD muted
    letterSpacing: 2,
    fontWeight: '700',
  });
  return (
    <>
      <Text text="DEV STUDIO" style={devStyle} x={20} y={11} />
      <Text text="CREATIVE HQ" style={mktStyle} x={MKT_ZONE.x + 20} y={11} />
      <Text text="NEXUS" style={orchStyle}
        x={CORR_ZONE.x + CORR_ZONE.w / 2}
        y={14} anchor={[0.5, 0]}
      />
    </>
  );
};

// ─── Main OfficeLayout ────────────────────────────────────────────────────────
interface OfficeLayoutProps {
  onAgentClick: (agentId: string) => void;
}

export const OfficeLayout: React.FC<OfficeLayoutProps> = ({ onAgentClick }) => {
  const agents = useOfficeStore((s) => s.agents);
  const tasks = useOfficeStore((s) => s.tasks);
  const agentList = Object.values(agents);
  const activeTasks = Object.values(tasks).filter(
    (t) => t.assigned_agent_id && t.status !== 'completed' && t.status !== 'failed'
  );

  return (
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
      {/* ── Background layers ── */}
      <DevBackground />
      <MktBackground />
      <CorrBackground />
      <ZoneLabels />

      {/* ── Ambient animations ── */}
      <CodeRain />
      <CreativeSparks />
      <DataStreams />
      <ServerLEDs />
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
  );
};

export default OfficeLayout;
