/**
 * AgentSprite — Premium character rendering for AI Office agents
 *
 * Supports three body poses driven by agent.pose from officeStore:
 *   'seated'   — at desk (legs tucked under, arms on keyboard, typing animation)
 *   'walking'  — in transit between zones (full leg swing, trail FX)
 *   'standing' — in boardroom meeting (upright, thinking/idle FX)
 *
 * Status → pose mapping:
 *   idle + seated     → gentle head bob, micro posture shift
 *   working + seated  → fast typing arms, nodding head
 *   thinking + standing → head pulse, antenna glow
 *   moving + walking  → fast leg/arm swing, cyan trail
 */
import React, { useCallback, useRef } from 'react';
import { Graphics, Text, useTick } from '@pixi/react';
import * as PIXI from 'pixi.js';
import type { Agent } from '../../state/officeStore';

interface AgentSpriteProps {
  agent: Agent;
  onAgentClick: (agentId: string) => void;
}

function hexToPixi(hex: string): number {
  return parseInt(hex.replace('#', ''), 16);
}
function lerp(a: number, b: number, t: number) { return a + (b - a) * t; }

interface AnimState {
  renderX: number;
  renderY: number;
  tick: number;
  floatY: number;
  // Think pulse
  pulseR: number;
  pulseDir: number;
  // Work sparks
  sparks: Array<{ dx: number; dy: number; life: number; maxLife: number; col: number }>;
  sparkTimer: number;
  // Move trail
  trail: Array<{ x: number; y: number; alpha: number }>;
  trailTimer: number;
  // Data packet FX (working at desk)
  dataPackets: Array<{ progress: number; lane: number; col: number }>;
  dataTimer: number;
}

const AgentSprite: React.FC<AgentSpriteProps> = ({ agent, onAgentClick }) => {
  const animRef = useRef<AnimState>({
    renderX: agent.position.x,
    renderY: agent.position.y,
    tick: Math.random() * Math.PI * 2,
    floatY: 0,
    pulseR: 1,
    pulseDir: 1,
    sparks: [],
    sparkTimer: 0,
    trailTimer: 0,
    trail: [],
    dataPackets: [],
    dataTimer: 0,
  });

  const gRef  = useRef<PIXI.Graphics>(null);
  const gRef2 = useRef<PIXI.Graphics>(null); // fx layer
  const lblRef = useRef<PIXI.Text>(null);

  const color   = hexToPixi(agent.color);
  const colorR  = (color >> 16) & 0xff;
  const colorG  = (color >> 8)  & 0xff;
  const colorB  =  color        & 0xff;
  const colorLt = ((Math.min(colorR + 80, 255)) << 16) |
                  ((Math.min(colorG + 80, 255)) << 8)  |
                   (Math.min(colorB + 80, 255));
  const colorDk = ((Math.max(colorR - 40, 0)) << 16) |
                  ((Math.max(colorG - 40, 0)) << 8)  |
                   (Math.max(colorB - 40, 0));
  const isOrchestrator = agent.team === 'orchestrator' || agent.agent_role.toLowerCase().includes('orchestrator');

  useTick((delta) => {
    const a = animRef.current;
    a.tick += delta * 0.035;

    // ── Smooth movement ──────────────────────────────────────────────────────
    const lerpSpd = agent.status === 'moving' ? 0.055 : 0.14;
    const prevX = a.renderX, prevY = a.renderY;
    a.renderX = lerp(a.renderX, agent.position.x, lerpSpd * delta);
    a.renderY = lerp(a.renderY, agent.position.y, lerpSpd * delta);
    const isMovingPixels = Math.abs(a.renderX - prevX) > 0.5 || Math.abs(a.renderY - prevY) > 0.5;

    const isSeated   = agent.pose === 'seated';
    const isWalking  = agent.pose === 'walking';

    // ── Float / sway ────────────────────────────────────────────────────────
    if (isSeated) {
      // Micro posture sway — seated agents breathe and shift weight
      a.floatY = Math.sin(a.tick * 0.55) * 1.5;
    } else if (agent.status === 'idle') {
      a.floatY = Math.sin(a.tick) * 5;
    } else {
      a.floatY = lerp(a.floatY, 0, 0.1 * delta);
    }

    // ── Think pulse ──────────────────────────────────────────────────────────
    if (agent.status === 'thinking') {
      a.pulseR += a.pulseDir * 0.022 * delta;
      if (a.pulseR > 1.4) a.pulseDir = -1;
      if (a.pulseR < 0.7) a.pulseDir = 1;
    } else {
      a.pulseR = lerp(a.pulseR, 1, 0.08 * delta);
    }

    // ── Work sparks (standing/walking working state) ─────────────────────────
    if (agent.status === 'working' && !isSeated) {
      a.sparkTimer += delta;
      if (a.sparkTimer > 8) {
        a.sparkTimer = 0;
        a.sparks.push({
          dx: (Math.random() - 0.5) * 26,
          dy: -5 - Math.random() * 20,
          life: 0,
          maxLife: 30 + Math.random() * 30,
          col: [color, colorLt, 0xffffff][Math.floor(Math.random() * 3)],
        });
      }
    }
    a.sparks = a.sparks.filter(s => s.life < s.maxLife);
    for (const s of a.sparks) {
      s.life += delta;
      s.dx += (Math.random() - 0.5) * 0.5;
      s.dy += 0.15;
    }

    // ── Data packets (seated working — stream from agent toward monitors) ────
    if (agent.status === 'working' && isSeated) {
      a.dataTimer += delta;
      if (a.dataTimer > 18) {
        a.dataTimer = 0;
        a.dataPackets.push({
          progress: 0,
          lane: Math.floor(Math.random() * 3), // 3 lanes above agent
          col: [color, colorLt, 0x00ff88][Math.floor(Math.random() * 3)],
        });
      }
    }
    a.dataPackets = a.dataPackets.filter(d => d.progress < 1);
    for (const d of a.dataPackets) d.progress += delta * 0.018;

    // ── Move trail ──────────────────────────────────────────────────────────
    if (isMovingPixels && isWalking) {
      a.trailTimer += delta;
      if (a.trailTimer > 4) {
        a.trailTimer = 0;
        a.trail.push({ x: a.renderX, y: a.renderY + a.floatY, alpha: 0.4 });
      }
    }
    a.trail = a.trail.filter(t => t.alpha > 0.01);
    for (const t of a.trail) t.alpha *= 0.88;

    if (!gRef.current || !gRef2.current) return;

    // ────────────────────────────────────────────────────────────────────────
    // ── FX Layer (trail + sparks + data packets) ─────────────────────────────
    const fx = gRef2.current;
    fx.clear();

    // Trail
    for (const t of a.trail) {
      fx.beginFill(color, t.alpha * 0.5);
      fx.drawCircle(t.x, t.y, 8 * t.alpha);
      fx.endFill();
    }

    // Sparks (only when not seated)
    if (!isSeated) {
      const cx = a.renderX, cy = a.renderY + a.floatY - 28;
      for (const s of a.sparks) {
        const progress = s.life / s.maxLife;
        const sx2 = cx + s.dx * progress * 2;
        const sy2 = cy + s.dy * progress * 2;
        const sa = (1 - progress) * 0.9;
        const sr = 2 * (1 - progress);
        fx.beginFill(s.col, sa);
        fx.drawCircle(sx2, sy2, sr);
        fx.endFill();
      }
    }

    // Data packets — float upward from agent head toward monitor area
    if (isSeated) {
      const cx = a.renderX;
      const cy = a.renderY + a.floatY - 38;
      for (const d of a.dataPackets) {
        const laneX = cx + (d.lane - 1) * 10;
        const py = cy - d.progress * 32;
        const pa = (1 - d.progress) * 0.8;
        fx.beginFill(d.col, pa);
        fx.drawRoundedRect(laneX - 4, py - 3, 8, 6, 1);
        fx.endFill();
        // Tiny glow
        fx.beginFill(d.col, pa * 0.25);
        fx.drawCircle(laneX, py, 6);
        fx.endFill();
      }
    }

    // ────────────────────────────────────────────────────────────────────────
    // ── Character Layer ──────────────────────────────────────────────────────
    const g = gRef.current;
    g.clear();

    const x = a.renderX;
    const y = a.renderY + a.floatY;
    const tk = a.tick;

    // ── Shadow ───────────────────────────────────────────────────────────────
    const shadowW = isSeated ? 14 : 18;
    g.beginFill(0x000000, 0.22);
    g.drawEllipse(x, y + (isSeated ? 24 : 32), shadowW, 5);
    g.endFill();

    // ── Halo ring (working / thinking — only when not seated) ───────────────
    if (!isSeated && (agent.status === 'working' || agent.status === 'thinking')) {
      const ringA = 0.3 + Math.sin(tk * 4) * 0.2;
      const ringR = agent.status === 'thinking' ? 36 * a.pulseR : 34 + Math.sin(tk * 5) * 3;
      g.lineStyle(1.5, color, ringA);
      g.drawCircle(x, y, ringR);
      g.lineStyle(0.5, colorLt, ringA * 0.5);
      g.drawCircle(x, y, ringR + 5);
    }

    // ── Legs & Feet ─────────────────────────────────────────────────────────
    if (isSeated) {
      // Thighs angled forward and down (knees at desk level)
      g.lineStyle(5, colorDk, 0.95);
      g.moveTo(x - 7, y + 18);
      g.lineTo(x - 9, y + 28);
      g.moveTo(x + 7, y + 18);
      g.lineTo(x + 9, y + 28);
      // Lower legs tucked back under desk (foreshortened)
      g.lineStyle(4, colorDk, 0.55);
      g.moveTo(x - 9, y + 28);
      g.lineTo(x - 6, y + 22);
      g.moveTo(x + 9, y + 28);
      g.lineTo(x + 6, y + 22);
      // Feet (small, resting on floor)
      g.lineStyle(0);
      g.beginFill(colorDk, 0.75);
      g.drawRoundedRect(x - 14, y + 20, 8, 4, 2);
      g.drawRoundedRect(x + 6, y + 20, 8, 4, 2);
      g.endFill();
    } else {
      // Walking / standing legs
      const legSwing = isWalking ? Math.sin(tk * 6) * 10 : Math.sin(tk * 1.5) * 2;
      g.lineStyle(5, colorDk, 0.95);
      g.moveTo(x - 7, y + 18);
      g.lineTo(x - 10 + legSwing, y + 34);
      g.lineTo(x - 14 + legSwing, y + 38);
      g.moveTo(x + 7, y + 18);
      g.lineTo(x + 10 - legSwing, y + 34);
      g.lineTo(x + 14 - legSwing, y + 38);
      g.lineStyle(0);
      g.beginFill(colorDk, 0.9);
      g.drawRoundedRect(x - 18 + legSwing, y + 36, 10, 5, 2);
      g.drawRoundedRect(x + 8 - legSwing, y + 36, 10, 5, 2);
      g.endFill();
    }

    // ── Body ─────────────────────────────────────────────────────────────────
    g.beginFill(color, 0.92);
    g.lineStyle(1.5, colorLt, 0.5);
    g.drawRoundedRect(x - 16, y - 16, 32, 34, 8);
    g.endFill();
    // Body shine
    g.beginFill(0xffffff, 0.12);
    g.drawRoundedRect(x - 12, y - 14, 14, 16, 5);
    g.endFill();
    // Inner panel
    g.beginFill(colorDk, 0.55);
    g.lineStyle(0.5, colorLt, 0.2);
    g.drawRoundedRect(x - 9, y - 4, 18, 16, 3);
    g.endFill();
    // Status light
    const litColor = agent.status === 'working'  ? 0x00ff88 :
                     agent.status === 'thinking'  ? 0xfbbf24 :
                     agent.status === 'moving'    ? 0x00c8ff : 0x4a5568;
    const litPulse = agent.status === 'working'
      ? 0.7 + Math.sin(tk * (isSeated ? 12 : 8)) * 0.3
      : 0.85;
    g.lineStyle(0);
    g.beginFill(litColor, litPulse);
    g.drawCircle(x, y + 6, 3.5);
    g.endFill();
    // Panel grid lines
    g.lineStyle(0.5, colorLt, 0.12);
    g.moveTo(x - 9, y + 1); g.lineTo(x + 9, y + 1);
    g.moveTo(x - 9, y + 6); g.lineTo(x + 9, y + 6);

    // ── Arms ─────────────────────────────────────────────────────────────────
    if (isSeated) {
      // Arms reaching forward to keyboard — typing animation when working
      const typingL = agent.status === 'working'
        ? Math.sin(tk * 10) * 3
        : Math.sin(tk * 1.8) * 1;
      const typingR = agent.status === 'working'
        ? Math.sin(tk * 10 + 0.8) * 3
        : Math.sin(tk * 1.8 + 0.5) * 1;
      g.lineStyle(5, colorDk, 0.9);
      g.moveTo(x - 16, y - 6);
      g.lineTo(x - 18, y + 15 + typingL);
      g.moveTo(x + 16, y - 6);
      g.lineTo(x + 18, y + 15 + typingR);
      // Hands (on keyboard)
      g.lineStyle(0);
      g.beginFill(colorLt, 0.8);
      g.drawCircle(x - 18, y + 15 + typingL, 3.5);
      g.drawCircle(x + 18, y + 15 + typingR, 3.5);
      g.endFill();
    } else {
      // Standing / walking arms
      const armSwing = isWalking
        ? Math.sin(tk * 6) * 8
        : (agent.status === 'working' ? Math.sin(tk * 6) * 6 : Math.sin(tk * 1.8) * 3);
      g.lineStyle(5, colorDk, 0.9);
      g.moveTo(x - 16, y - 6);
      g.lineTo(x - 26 + armSwing, y + 6);
      g.moveTo(x + 16, y - 6);
      g.lineTo(x + 26 - armSwing, y + 6);
      g.lineStyle(0);
      g.beginFill(colorLt, 0.8);
      g.drawCircle(x - 26 + armSwing, y + 6, 4);
      g.drawCircle(x + 26 - armSwing, y + 6, 4);
      g.endFill();
    }

    // ── Neck ─────────────────────────────────────────────────────────────────
    g.beginFill(colorDk, 0.9);
    g.drawRoundedRect(x - 5, y - 24, 10, 10, 2);
    g.endFill();

    // ── Head ─────────────────────────────────────────────────────────────────
    const headScale = agent.status === 'thinking' ? a.pulseR : 1;
    const headR = 16 * headScale;
    // Typing head-nod when seated + working
    const headNod = (isSeated && agent.status === 'working')
      ? Math.sin(tk * 8) * 1.8
      : 0;
    const headY = y - 40 + headNod;

    g.beginFill(color, 0.97);
    g.lineStyle(1.5, colorLt, 0.6);
    g.drawCircle(x, headY, headR);
    g.endFill();
    // Head shine
    g.beginFill(0xffffff, 0.18);
    g.drawEllipse(x - 5, headY - 6, 8, 5);
    g.endFill();
    // Eyes
    g.lineStyle(0);
    const eyeA = 0.9 + Math.sin(tk * 3) * 0.1;
    const pupilSize = agent.status === 'thinking' ? 4 : 3;
    // Narrowed eyes when seated working (focus/concentration look)
    const eyeH = (isSeated && agent.status === 'working') ? 3.5 : 4.5;
    g.beginFill(0xffffff, 0.95);
    g.drawEllipse(x - 5, headY - 2, 4.5, eyeH);
    g.drawEllipse(x + 5, headY - 2, 4.5, eyeH);
    g.endFill();
    g.beginFill(colorDk, eyeA);
    g.drawCircle(x - 5, headY - 2, pupilSize);
    g.drawCircle(x + 5, headY - 2, pupilSize);
    g.endFill();
    // Pupil glint
    g.beginFill(0xffffff, 0.9);
    g.drawCircle(x - 4, headY - 3, 1.5);
    g.drawCircle(x + 6, headY - 3, 1.5);
    g.endFill();
    // Mouth
    g.lineStyle(1.5, colorDk, 0.7);
    if (agent.status === 'working') {
      if (isSeated) {
        // Pursed / focused mouth (typing concentration)
        g.moveTo(x - 3, headY + 7);
        g.lineTo(x + 3, headY + 7);
      } else {
        // Open mouth (active work, standing)
        g.drawEllipse(x, headY + 7, 5, 3);
      }
    } else if (agent.status === 'thinking') {
      // Neutral
      g.moveTo(x - 4, headY + 7); g.lineTo(x + 4, headY + 7);
    } else {
      // Slight smile
      g.moveTo(x - 4, headY + 6);
      g.bezierCurveTo(x - 2, headY + 9, x + 2, headY + 9, x + 4, headY + 6);
    }

    // ── Antenna ──────────────────────────────────────────────────────────────
    const antA  = tk * 1.4;
    const antBx = x - 6 + Math.sin(antA) * 3;
    const antBy = headY - headR + Math.cos(antA) * 2 - 14;
    const antCx = x + 6 + Math.sin(antA + 0.9) * 3;
    const antCy = headY - headR + Math.cos(antA + 0.9) * 2 - 12;
    g.lineStyle(1.5, color, 0.85);
    g.moveTo(x - 6, headY - headR + 2); g.lineTo(antBx, antBy);
    g.moveTo(x + 6, headY - headR + 2); g.lineTo(antCx, antCy);
    const orbColor = agent.status === 'thinking' ? 0xfbbf24 :
                     agent.status === 'working'   ? 0x00ff88 : colorLt;
    const orbA = 0.7 + Math.sin(tk * 5) * 0.3;
    g.lineStyle(0);
    g.beginFill(orbColor, orbA);
    g.drawCircle(antBx, antBy, 3);
    g.drawCircle(antCx, antCy, 3);
    g.endFill();
    g.beginFill(orbColor, orbA * 0.25);
    g.drawCircle(antBx, antBy, 7);
    g.drawCircle(antCx, antCy, 7);
    g.endFill();

    if (isOrchestrator) {
      const crownY = headY - headR - 16;
      g.beginFill(0xfbbf24, 0.95);
      g.lineStyle(1.5, 0xfff1a8, 0.7);
      g.drawPolygon([
        x - 14, crownY + 10,
        x - 10, crownY - 2,
        x - 4, crownY + 8,
        x, crownY - 8,
        x + 4, crownY + 8,
        x + 10, crownY - 2,
        x + 14, crownY + 10,
      ]);
      g.endFill();
      g.beginFill(0xb45309, 0.95);
      g.lineStyle(1, 0xfff1a8, 0.45);
      g.drawRoundedRect(x - 16, crownY + 8, 32, 6, 3);
      g.endFill();
      g.beginFill(0xfff1a8, 0.9);
      g.drawCircle(x, crownY - 8, 2.5);
      g.drawCircle(x - 10, crownY - 2, 2.1);
      g.drawCircle(x + 10, crownY - 2, 2.1);
      g.endFill();
    }

    // ── Role badge + completed_tasks counter ─────────────────────────────────
    const badgeW = 68, badgeH = 18;
    g.beginFill(0x000000, 0.62);
    g.lineStyle(1, color, 0.55);
    g.drawRoundedRect(x - badgeW / 2, headY - headR - 30, badgeW, badgeH, 9);
    g.endFill();

    // Tiny completed-tasks pip row (up to 5 pips)
    if (agent.completed_tasks > 0) {
      const pips = Math.min(agent.completed_tasks, 5);
      const pipStart = x - (pips - 1) * 5;
      for (let i = 0; i < pips; i++) {
        g.beginFill(0x00ff88, 0.7);
        g.drawCircle(pipStart + i * 10, headY - headR - 38, 2.5);
        g.endFill();
      }
    }

    // Update badge text position
    if (lblRef.current) {
      lblRef.current.x = x;
      lblRef.current.y = headY - headR - 26;
    }
  });

  const handleClick = useCallback(() => {
    onAgentClick(agent.agent_id);
  }, [agent.agent_id, onAgentClick]);

  const badgeLabel = agent.agent_name || agent.agent_role.split(' ')[0].toUpperCase();

  const labelStyle = new PIXI.TextStyle({
    fontFamily: '"SF Mono", "Cascadia Code", monospace',
    fontSize: 9,
    fontWeight: '700',
    fill: agent.color,
    align: 'center',
    letterSpacing: 1.2,
  });

  return (
    <>
      {/* FX layer (non-interactive) */}
      <Graphics ref={gRef2} />
      {/* Body layer (interactive) */}
      <Graphics
        ref={gRef}
        interactive={true}
        cursor="pointer"
        onclick={handleClick}
        ontouchstart={handleClick}
      />
      {/* Codinome badge */}
      <Text
        ref={lblRef}
        text={badgeLabel}
        style={labelStyle}
        anchor={[0.5, 0.5]}
        x={agent.position.x}
        y={agent.position.y - 56}
      />
    </>
  );
};

export default AgentSprite;
