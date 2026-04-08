/**
 * AgentSprite — Premium character rendering for AI Office agents
 *
 * Each agent is rendered as a stylized humanoid with:
 *   - Team-colored body with inner gradient glow
 *   - Animated walking legs when moving
 *   - Status-specific visual effects (thinking pulse, work sparks, move trail)
 *   - Holographic status ring
 *   - Name badge that hovers above
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
  // Idle float
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
  });

  const gRef  = useRef<PIXI.Graphics>(null);
  const gRef2 = useRef<PIXI.Graphics>(null); // fx layer
  const lblRef = useRef<PIXI.Text>(null);

  const color   = hexToPixi(agent.color);
  const colorR  = (color >> 16) & 0xff;
  const colorG  = (color >> 8)  & 0xff;
  const colorB  =  color        & 0xff;
  // Lighter tint
  const colorLt = ((Math.min(colorR + 80, 255)) << 16) |
                  ((Math.min(colorG + 80, 255)) << 8)  |
                   (Math.min(colorB + 80, 255));
  // Darker tint
  const colorDk = ((Math.max(colorR - 40, 0)) << 16) |
                  ((Math.max(colorG - 40, 0)) << 8)  |
                   (Math.max(colorB - 40, 0));

  useTick((delta) => {
    const a = animRef.current;
    a.tick += delta * 0.035;

    // ── Smooth movement ──────────────────────────────────────────────────────
    const lerpSpd = agent.status === 'moving' ? 0.055 : 0.14;
    const prevX = a.renderX, prevY = a.renderY;
    a.renderX = lerp(a.renderX, agent.position.x, lerpSpd * delta);
    a.renderY = lerp(a.renderY, agent.position.y, lerpSpd * delta);
    const moving = Math.abs(a.renderX - prevX) > 0.5 || Math.abs(a.renderY - prevY) > 0.5;

    // ── Idle float ───────────────────────────────────────────────────────────
    a.floatY = agent.status === 'idle' ? Math.sin(a.tick) * 5 : lerp(a.floatY, 0, 0.1 * delta);

    // ── Think pulse ──────────────────────────────────────────────────────────
    if (agent.status === 'thinking') {
      a.pulseR += a.pulseDir * 0.022 * delta;
      if (a.pulseR > 1.4) a.pulseDir = -1;
      if (a.pulseR < 0.7) a.pulseDir = 1;
    } else {
      a.pulseR = lerp(a.pulseR, 1, 0.08 * delta);
    }

    // ── Work sparks ──────────────────────────────────────────────────────────
    if (agent.status === 'working') {
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
      s.dy += 0.15; // gravity
    }

    // ── Move trail ──────────────────────────────────────────────────────────
    if (moving && agent.status === 'moving') {
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
    // ── FX Layer (trail + sparks) ────────────────────────────────────────────
    const fx = gRef2.current;
    fx.clear();

    // Trail
    for (const t of a.trail) {
      fx.beginFill(color, t.alpha * 0.5);
      fx.drawCircle(t.x, t.y, 8 * t.alpha);
      fx.endFill();
    }

    // Sparks
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

    // ────────────────────────────────────────────────────────────────────────
    // ── Character Layer ──────────────────────────────────────────────────────
    const g = gRef.current;
    g.clear();

    const x = a.renderX;
    const y = a.renderY + a.floatY;
    const tk = a.tick;

    // ── Shadow ───────────────────────────────────────────────────────────────
    g.beginFill(0x000000, 0.22);
    g.drawEllipse(x, y + 32, 18, 5);
    g.endFill();

    // ── Halo ring (working / thinking) ───────────────────────────────────────
    if (agent.status === 'working' || agent.status === 'thinking') {
      const ringA = 0.3 + Math.sin(tk * 4) * 0.2;
      const ringR = agent.status === 'thinking' ? 36 * a.pulseR : 34 + Math.sin(tk * 5) * 3;
      g.lineStyle(1.5, color, ringA);
      g.drawCircle(x, y, ringR);
      g.lineStyle(0.5, colorLt, ringA * 0.5);
      g.drawCircle(x, y, ringR + 5);
    }

    // ── Legs ─────────────────────────────────────────────────────────────────
    const legSwing = agent.status === 'moving' ? Math.sin(tk * 6) * 10 : Math.sin(tk * 1.5) * 2;
    g.lineStyle(5, colorDk, 0.95);
    // Left leg
    g.moveTo(x - 7, y + 18);
    g.lineTo(x - 10 + legSwing, y + 34);
    g.lineTo(x - 14 + legSwing, y + 38);
    // Right leg
    g.moveTo(x + 7, y + 18);
    g.lineTo(x + 10 - legSwing, y + 34);
    g.lineTo(x + 14 - legSwing, y + 38);
    // Foot caps
    g.lineStyle(0);
    g.beginFill(colorDk, 0.9);
    g.drawRoundedRect(x - 18 + legSwing, y + 36, 10, 5, 2);
    g.drawRoundedRect(x + 8 - legSwing, y + 36, 10, 5, 2);
    g.endFill();

    // ── Body ─────────────────────────────────────────────────────────────────
    // Outer shell
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
    // Status light on panel
    const litColor = agent.status === 'working' ? 0x00ff88 :
                     agent.status === 'thinking' ? 0xfbbf24 :
                     agent.status === 'moving'   ? 0x00c8ff : 0x4a5568;
    const litA = agent.status === 'working' ? 0.7 + Math.sin(tk * 8) * 0.3 : 0.85;
    g.beginFill(litColor, litA);
    g.drawCircle(x, y + 6, 3.5);
    g.endFill();
    // Panel grid lines
    g.lineStyle(0.5, colorLt, 0.12);
    g.moveTo(x - 9, y + 1); g.lineTo(x + 9, y + 1);
    g.moveTo(x - 9, y + 6); g.lineTo(x + 9, y + 6);

    // ── Arms ─────────────────────────────────────────────────────────────────
    const armSwing = agent.status === 'working'
      ? Math.sin(tk * 6) * 6
      : Math.sin(tk * 1.8) * 3;
    g.lineStyle(5, colorDk, 0.9);
    g.moveTo(x - 16, y - 6);
    g.lineTo(x - 26 + armSwing, y + 6);
    g.moveTo(x + 16, y - 6);
    g.lineTo(x + 26 - armSwing, y + 6);
    // Hand caps
    g.lineStyle(0);
    g.beginFill(colorLt, 0.8);
    g.drawCircle(x - 26 + armSwing, y + 6, 4);
    g.drawCircle(x + 26 - armSwing, y + 6, 4);
    g.endFill();

    // ── Neck ─────────────────────────────────────────────────────────────────
    g.beginFill(colorDk, 0.9);
    g.drawRoundedRect(x - 5, y - 24, 10, 10, 2);
    g.endFill();

    // ── Head ─────────────────────────────────────────────────────────────────
    const headScale = agent.status === 'thinking' ? a.pulseR : 1;
    const headR = 16 * headScale;
    const headY = y - 40;
    // Head shell
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
    g.beginFill(0xffffff, 0.95);
    g.drawCircle(x - 5, headY - 2, 4.5);
    g.drawCircle(x + 5, headY - 2, 4.5);
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
      // Open mouth (working)
      g.drawEllipse(x, headY + 7, 5, 3);
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
    // Orbs
    const orbColor = agent.status === 'thinking' ? 0xfbbf24 :
                     agent.status === 'working'   ? 0x00ff88 : colorLt;
    const orbA = 0.7 + Math.sin(tk * 5) * 0.3;
    g.lineStyle(0);
    g.beginFill(orbColor, orbA);
    g.drawCircle(antBx, antBy, 3);
    g.drawCircle(antCx, antCy, 3);
    g.endFill();
    // Orb glow
    g.beginFill(orbColor, orbA * 0.25);
    g.drawCircle(antBx, antBy, 7);
    g.drawCircle(antCx, antCy, 7);
    g.endFill();

    // ── Role badge (floating above head) ────────────────────────────────────
    // drawn as pill background
    const badgeW = 68, badgeH = 18;
    g.beginFill(0x000000, 0.62);
    g.lineStyle(1, color, 0.55);
    g.drawRoundedRect(x - badgeW / 2, headY - headR - 30, badgeW, badgeH, 9);
    g.endFill();

    // Update text label position
    if (lblRef.current) {
      lblRef.current.x = x;
      lblRef.current.y = headY - headR - 26;
    }
  });

  const handleClick = useCallback(() => {
    onAgentClick(agent.agent_id);
  }, [agent.agent_id, onAgentClick]);

  const shortRole = agent.agent_role.length > 9
    ? agent.agent_role.slice(0, 9) + '…'
    : agent.agent_role;

  const labelStyle = new PIXI.TextStyle({
    fontFamily: '"SF Mono", "Cascadia Code", monospace',
    fontSize: 9,
    fontWeight: '700',
    fill: agent.color,
    align: 'center',
    letterSpacing: 0.5,
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
      {/* Role badge text */}
      <Text
        ref={lblRef}
        text={shortRole.toUpperCase()}
        style={labelStyle}
        anchor={[0.5, 0.5]}
        x={agent.position.x}
        y={agent.position.y - 56}
      />
    </>
  );
};

export default AgentSprite;
