import React, { useCallback, useRef } from 'react';
import { Graphics, Text, useTick } from '@pixi/react';
import * as PIXI from 'pixi.js';
import type { Agent } from '../../state/officeStore';

interface AgentSpriteProps {
  agent: Agent;
  onAgentClick: (agentId: string) => void;
}

// Parse a CSS hex color string like '#ff0000' to a PIXI numeric color
function hexToPixi(hex: string): number {
  return parseInt(hex.replace('#', ''), 16);
}

// Lerp utility
function lerp(a: number, b: number, t: number): number {
  return a + (b - a) * t;
}

interface AnimState {
  // Current render position (may differ from target during move)
  renderX: number;
  renderY: number;
  // Animation tick
  tick: number;
  // Pulse scale for thinking
  pulseScale: number;
  pulseDir: number;
  // Vibration offset for working
  vibX: number;
}

const AgentSprite: React.FC<AgentSpriteProps> = ({ agent, onAgentClick }) => {
  const animRef = useRef<AnimState>({
    renderX: agent.position.x,
    renderY: agent.position.y,
    tick: Math.random() * Math.PI * 2, // Random phase offset so agents don't all move together
    pulseScale: 1,
    pulseDir: 1,
    vibX: 0,
  });

  const gRef = useRef<PIXI.Graphics>(null);
  const labelRef = useRef<PIXI.Text>(null);

  const color = hexToPixi(agent.color);
  const glowColor = 0xffffff;

  useTick((delta) => {
    const anim = animRef.current;
    anim.tick += delta * 0.04;

    // Smoothly move toward target position
    const lerpSpeed = agent.status === 'moving' ? 0.06 : 0.12;
    anim.renderX = lerp(anim.renderX, agent.position.x, lerpSpeed * delta);
    anim.renderY = lerp(anim.renderY, agent.position.y, lerpSpeed * delta);

    // Pulse (thinking)
    if (agent.status === 'thinking') {
      anim.pulseScale += anim.pulseDir * 0.018 * delta;
      if (anim.pulseScale > 1.35) anim.pulseDir = -1;
      if (anim.pulseScale < 0.75) anim.pulseDir = 1;
    } else {
      anim.pulseScale = lerp(anim.pulseScale, 1, 0.1 * delta);
    }

    // Vibration (working)
    if (agent.status === 'working') {
      anim.vibX = (Math.random() - 0.5) * 2.5;
    } else {
      anim.vibX = lerp(anim.vibX, 0, 0.2 * delta);
    }

    if (!gRef.current) return;

    const g = gRef.current;
    g.clear();

    const x = anim.renderX + anim.vibX;
    // Idle: gentle vertical oscillation
    const idleOffsetY = agent.status === 'idle'
      ? Math.sin(anim.tick) * 4
      : 0;
    const y = anim.renderY + idleOffsetY;

    // --- Body (main circle, 20px radius) ---
    g.beginFill(color, 0.9);
    g.lineStyle(1.5, glowColor, 0.3);
    g.drawCircle(x, y, 20);
    g.endFill();

    // --- Inner body glow vertical line ---
    g.lineStyle(2, glowColor, 0.25);
    g.moveTo(x, y - 14);
    g.lineTo(x, y + 14);

    // --- Head (smaller circle, 12px radius) ---
    const headScale = agent.status === 'thinking' ? anim.pulseScale : 1;
    const headY = y - 32;
    g.beginFill(color, 1);
    g.lineStyle(1, glowColor, 0.5);
    g.drawCircle(x, headY, 12 * headScale);
    g.endFill();

    // --- Eye dots on head ---
    g.beginFill(glowColor, 0.9);
    g.drawCircle(x - 4, headY - 2, 2);
    g.drawCircle(x + 4, headY - 2, 2);
    g.endFill();

    // --- Antenna left ---
    const antennaTick = anim.tick;
    g.lineStyle(1.5, color, 0.9);
    g.moveTo(x - 5, headY - 12 * headScale);
    g.lineTo(x - 12 + Math.sin(antennaTick * 1.3) * 3, headY - 26 + Math.cos(antennaTick) * 2);
    // Antenna orb
    g.beginFill(glowColor, 0.8);
    g.drawCircle(
      x - 12 + Math.sin(antennaTick * 1.3) * 3,
      headY - 26 + Math.cos(antennaTick) * 2,
      2.5
    );
    g.endFill();

    // --- Antenna right ---
    g.lineStyle(1.5, color, 0.9);
    g.moveTo(x + 5, headY - 12 * headScale);
    g.lineTo(x + 12 + Math.sin(antennaTick * 0.9 + 1) * 3, headY - 26 + Math.cos(antennaTick + 1) * 2);
    // Antenna orb
    g.beginFill(glowColor, 0.8);
    g.drawCircle(
      x + 12 + Math.sin(antennaTick * 0.9 + 1) * 3,
      headY - 26 + Math.cos(antennaTick + 1) * 2,
      2.5
    );
    g.endFill();

    // --- Neck connector ---
    g.lineStyle(3, color, 0.6);
    g.moveTo(x, headY + 12 * headScale);
    g.lineTo(x, y - 20);

    // --- Legs ---
    g.lineStyle(3, color, 0.7);
    // Left leg
    g.moveTo(x - 6, y + 20);
    g.lineTo(x - 12 + Math.sin(anim.tick * 1.5) * 4, y + 38);
    // Right leg
    g.moveTo(x + 6, y + 20);
    g.lineTo(x + 12 + Math.sin(anim.tick * 1.5 + Math.PI) * 4, y + 38);

    // --- Arms ---
    g.lineStyle(2.5, color, 0.7);
    // Left arm
    g.moveTo(x - 16, y - 5);
    g.lineTo(x - 26 + Math.cos(anim.tick * 1.2) * 4, y + 8 + Math.sin(anim.tick * 1.2) * 3);
    // Right arm
    g.moveTo(x + 16, y - 5);
    g.lineTo(x + 26 + Math.cos(anim.tick * 1.2 + Math.PI) * 4, y + 8 + Math.sin(anim.tick * 1.2 + Math.PI) * 3);

    // --- Status indicator ring ---
    if (agent.status === 'working' || agent.status === 'thinking') {
      const alpha = 0.4 + Math.sin(anim.tick * 3) * 0.3;
      g.lineStyle(2, color, alpha);
      g.drawCircle(x, y, 28);
    }

    // Update label position
    if (labelRef.current) {
      labelRef.current.x = x;
      labelRef.current.y = y + 44;
    }
  });

  const handleClick = useCallback(() => {
    onAgentClick(agent.agent_id);
  }, [agent.agent_id, onAgentClick]);

  const shortRole = agent.agent_role.length > 10
    ? agent.agent_role.slice(0, 10) + '…'
    : agent.agent_role;

  const textStyle = new PIXI.TextStyle({
    fontFamily: 'monospace',
    fontSize: 10,
    fill: agent.color,
    align: 'center',
    dropShadow: true,
    dropShadowColor: '#000000',
    dropShadowDistance: 1,
    dropShadowBlur: 2,
  });

  return (
    <>
      <Graphics
        ref={gRef}
        interactive={true}
        cursor="pointer"
        onclick={handleClick}
        ontouchstart={handleClick}
      />
      <Text
        ref={labelRef}
        text={shortRole}
        style={textStyle}
        anchor={[0.5, 0]}
        x={agent.position.x}
        y={agent.position.y + 44}
      />
    </>
  );
};

export default AgentSprite;
