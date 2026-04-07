import React, { useCallback } from 'react';
import { Stage, Graphics, Text, useTick } from '@pixi/react';
import * as PIXI from 'pixi.js';
import { useOfficeStore } from '../state/officeStore';
import AgentSprite from '../components/agents/AgentSprite';
import TaskBubble from '../components/agents/TaskBubble';

// Zone constants
const CANVAS_W = 1280;
const CANVAS_H = 720;

const DEV_ZONE = { x: 0, y: 0, w: 580, h: CANVAS_H };
const ORCH_ZONE = { x: 580, y: 0, w: 120, h: CANVAS_H };
const MKT_ZONE = { x: 700, y: 0, w: 580, h: CANVAS_H };

const MEETING_ROOM = { x: 480, y: 20, w: 320, h: 120 };
const IDLE_AREA_H = 90;

// ---------- Static background layer ----------
const BackgroundLayer: React.FC = () => {
  const draw = useCallback((g: PIXI.Graphics) => {
    g.clear();

    // Dev zone
    g.beginFill(0x0d1b2a, 1);
    g.drawRect(DEV_ZONE.x, DEV_ZONE.y, DEV_ZONE.w, DEV_ZONE.h);
    g.endFill();

    // Dev zone subtle grid
    g.lineStyle(0.4, 0x1e3a5f, 0.35);
    for (let gx = 0; gx <= DEV_ZONE.w; gx += 40) {
      g.moveTo(DEV_ZONE.x + gx, DEV_ZONE.y);
      g.lineTo(DEV_ZONE.x + gx, DEV_ZONE.h);
    }
    for (let gy = 0; gy <= DEV_ZONE.h; gy += 40) {
      g.moveTo(DEV_ZONE.x, DEV_ZONE.y + gy);
      g.lineTo(DEV_ZONE.x + DEV_ZONE.w, DEV_ZONE.y + gy);
    }

    // Orchestrator zone
    g.beginFill(0x080810, 1);
    g.drawRect(ORCH_ZONE.x, ORCH_ZONE.y, ORCH_ZONE.w, ORCH_ZONE.h);
    g.endFill();

    // Orch zone divider lines
    g.lineStyle(1, 0x1e3a5f, 0.4);
    g.moveTo(ORCH_ZONE.x, 0);
    g.lineTo(ORCH_ZONE.x, CANVAS_H);
    g.lineStyle(1, 0x3b1a5a, 0.4);
    g.moveTo(ORCH_ZONE.x + ORCH_ZONE.w, 0);
    g.lineTo(ORCH_ZONE.x + ORCH_ZONE.w, CANVAS_H);

    // Marketing zone
    g.beginFill(0x1a0d2e, 1);
    g.drawRect(MKT_ZONE.x, MKT_ZONE.y, MKT_ZONE.w, MKT_ZONE.h);
    g.endFill();

    // Marketing zone subtle grid
    g.lineStyle(0.4, 0x3b1a5a, 0.35);
    for (let gx = 0; gx <= MKT_ZONE.w; gx += 40) {
      g.moveTo(MKT_ZONE.x + gx, MKT_ZONE.y);
      g.lineTo(MKT_ZONE.x + gx, MKT_ZONE.h);
    }
    for (let gy = 0; gy <= MKT_ZONE.h; gy += 40) {
      g.moveTo(MKT_ZONE.x, MKT_ZONE.y + gy);
      g.lineTo(MKT_ZONE.x + MKT_ZONE.w, MKT_ZONE.y + gy);
    }

    // --- Meeting Room (top center) ---
    g.beginFill(0x0f0f1f, 0.8);
    g.lineStyle(2, 0xfbbf24, 0.85);
    g.drawRoundedRect(MEETING_ROOM.x, MEETING_ROOM.y, MEETING_ROOM.w, MEETING_ROOM.h, 6);
    g.endFill();

    // Meeting room label
    g.lineStyle(0);
    g.beginFill(0xfbbf24, 0.12);
    g.drawRoundedRect(MEETING_ROOM.x + 2, MEETING_ROOM.y + 2, MEETING_ROOM.w - 4, 24, 4);
    g.endFill();

    // --- Idle Areas (sofas at bottom of each zone) ---
    // Dev zone sofa
    g.beginFill(0x0f2035, 0.7);
    g.lineStyle(1.5, 0x1e3a5f, 0.7);
    g.drawRoundedRect(20, CANVAS_H - IDLE_AREA_H - 10, DEV_ZONE.w - 40, IDLE_AREA_H, 8);
    g.endFill();

    // Sofa cushion indicators (dev)
    for (let i = 0; i < 4; i++) {
      g.beginFill(0x1e3a5f, 0.5);
      g.drawRoundedRect(35 + i * 120, CANVAS_H - IDLE_AREA_H, 100, 60, 10);
      g.endFill();
    }

    // Marketing zone sofa
    g.beginFill(0x200f35, 0.7);
    g.lineStyle(1.5, 0x3b1a5a, 0.7);
    g.drawRoundedRect(
      MKT_ZONE.x + 20,
      CANVAS_H - IDLE_AREA_H - 10,
      MKT_ZONE.w - 40,
      IDLE_AREA_H,
      8
    );
    g.endFill();

    // Sofa cushion indicators (marketing)
    for (let i = 0; i < 4; i++) {
      g.beginFill(0x3b1a5a, 0.5);
      g.drawRoundedRect(MKT_ZONE.x + 35 + i * 120, CANVAS_H - IDLE_AREA_H, 100, 60, 10);
      g.endFill();
    }

    // --- Desk clusters (3 desks per zone) ---
    const drawDesk = (dx: number, dy: number, color: number) => {
      g.beginFill(color, 0.35);
      g.lineStyle(1, color, 0.5);
      g.drawRoundedRect(dx, dy, 70, 40, 4);
      g.endFill();
      // Monitor
      g.beginFill(0x000000, 0.8);
      g.lineStyle(0.5, color, 0.6);
      g.drawRect(dx + 18, dy - 22, 34, 20);
      g.endFill();
      g.lineStyle(1, color, 0.4);
      g.moveTo(dx + 35, dy - 2);
      g.lineTo(dx + 35, dy);
    };

    // Dev desks
    drawDesk(60, 200, 0x1e3a5f);
    drawDesk(200, 200, 0x1e3a5f);
    drawDesk(340, 200, 0x1e3a5f);
    drawDesk(60, 360, 0x1e3a5f);
    drawDesk(200, 360, 0x1e3a5f);
    drawDesk(340, 360, 0x1e3a5f);

    // Marketing desks
    drawDesk(MKT_ZONE.x + 60, 200, 0x3b1a5a);
    drawDesk(MKT_ZONE.x + 200, 200, 0x3b1a5a);
    drawDesk(MKT_ZONE.x + 340, 200, 0x3b1a5a);
    drawDesk(MKT_ZONE.x + 60, 360, 0x3b1a5a);
    drawDesk(MKT_ZONE.x + 200, 360, 0x3b1a5a);
    drawDesk(MKT_ZONE.x + 340, 360, 0x3b1a5a);

    // Orchestrator desks (central column, vertical)
    g.beginFill(0x1a1a00, 0.6);
    g.lineStyle(1.5, 0xfbbf24, 0.4);
    g.drawRoundedRect(ORCH_ZONE.x + 10, 200, 100, 40, 4);
    g.endFill();
    g.beginFill(0x1a1a00, 0.6);
    g.lineStyle(1.5, 0xfbbf24, 0.4);
    g.drawRoundedRect(ORCH_ZONE.x + 10, 360, 100, 40, 4);
    g.endFill();

  }, []);

  return <Graphics draw={draw} />;
};

// ---------- Animated zone labels ----------
const ZoneLabels: React.FC = () => {
  const devStyle = new PIXI.TextStyle({
    fontFamily: 'monospace',
    fontSize: 11,
    fill: '#1e3a5f',
    letterSpacing: 4,
    fontWeight: '700',
  });
  const mktStyle = new PIXI.TextStyle({
    fontFamily: 'monospace',
    fontSize: 11,
    fill: '#3b1a5a',
    letterSpacing: 4,
    fontWeight: '700',
  });
  const orchStyle = new PIXI.TextStyle({
    fontFamily: 'monospace',
    fontSize: 9,
    fill: '#fbbf2488',
    letterSpacing: 2,
    fontWeight: '700',
  });
  const meetingStyle = new PIXI.TextStyle({
    fontFamily: 'monospace',
    fontSize: 10,
    fill: '#fbbf24',
    letterSpacing: 2,
    fontWeight: '700',
  });
  const idleStyle = new PIXI.TextStyle({
    fontFamily: 'monospace',
    fontSize: 9,
    fill: '#1e3a5f',
    letterSpacing: 2,
  });

  return (
    <>
      <Text text="DEV ZONE" style={devStyle} x={20} y={8} />
      <Text text="MARKETING ZONE" style={mktStyle} x={MKT_ZONE.x + 20} y={8} />
      <Text text="ORCH" style={orchStyle} x={ORCH_ZONE.x + 12} y={8} anchor={[0, 0]} />
      <Text
        text="MEETING ROOM"
        style={meetingStyle}
        x={MEETING_ROOM.x + MEETING_ROOM.w / 2}
        y={MEETING_ROOM.y + 6}
        anchor={[0.5, 0]}
      />
      <Text
        text="IDLE AREA"
        style={idleStyle}
        x={DEV_ZONE.w / 2}
        y={CANVAS_H - IDLE_AREA_H - 5}
        anchor={[0.5, 0]}
      />
      <Text
        text="IDLE AREA"
        style={{ ...idleStyle, fill: '#3b1a5a' } as PIXI.TextStyle}
        x={MKT_ZONE.x + MKT_ZONE.w / 2}
        y={CANVAS_H - IDLE_AREA_H - 5}
        anchor={[0.5, 0]}
      />
    </>
  );
};

// ---------- Animated data flow particles in orchestrator lane ----------
interface Particle {
  y: number;
  speed: number;
  alpha: number;
  dir: 1 | -1;
}

const OrchestratorParticles: React.FC = () => {
  const particles = React.useRef<Particle[]>([]);
  const gRef = React.useRef<PIXI.Graphics>(null);

  // Initialize particles
  if (particles.current.length === 0) {
    for (let i = 0; i < 12; i++) {
      particles.current.push({
        y: Math.random() * CANVAS_H,
        speed: 0.8 + Math.random() * 1.5,
        alpha: 0.3 + Math.random() * 0.6,
        dir: Math.random() > 0.5 ? 1 : -1,
      });
    }
  }

  useTick((delta) => {
    if (!gRef.current) return;
    const g = gRef.current;
    g.clear();

    for (const p of particles.current) {
      p.y += p.speed * p.dir * delta;
      if (p.y > CANVAS_H) p.y = 0;
      if (p.y < 0) p.y = CANVAS_H;

      g.lineStyle(1.5, 0xfbbf24, p.alpha * 0.7);
      g.moveTo(ORCH_ZONE.x + 60, p.y);
      g.lineTo(ORCH_ZONE.x + 60, p.y + p.dir * 14);

      g.beginFill(0xfbbf24, p.alpha);
      g.drawCircle(ORCH_ZONE.x + 60, p.y, 2);
      g.endFill();
    }
  });

  return <Graphics ref={gRef} />;
};

// ---------- Main OfficeLayout component ----------
interface OfficeLayoutProps {
  onAgentClick: (agentId: string) => void;
}

export const OfficeLayout: React.FC<OfficeLayoutProps> = ({ onAgentClick }) => {
  const agents = useOfficeStore((s) => s.agents);
  const tasks = useOfficeStore((s) => s.tasks);

  const agentList = Object.values(agents);

  // Find tasks that have an assigned agent and are not completed
  const activeTasks = Object.values(tasks).filter(
    (t) => t.assigned_agent_id && t.status !== 'completed' && t.status !== 'failed'
  );

  return (
    <Stage
      width={CANVAS_W}
      height={CANVAS_H}
      options={{
        backgroundColor: 0x1a1a2e,
        antialias: true,
        resolution: window.devicePixelRatio || 1,
        autoDensity: true,
      }}
    >
      {/* Static background */}
      <BackgroundLayer />

      {/* Zone labels */}
      <ZoneLabels />

      {/* Orchestrator animated particles */}
      <OrchestratorParticles />

      {/* Task bubbles floating over agents */}
      {activeTasks.map((task) => {
        const agent = task.assigned_agent_id ? agents[task.assigned_agent_id] : null;
        if (!agent) return null;
        return <TaskBubble key={task.task_id} task={task} agent={agent} />;
      })}

      {/* Agent sprites */}
      {agentList.map((agent) => (
        <AgentSprite key={agent.agent_id} agent={agent} onAgentClick={onAgentClick} />
      ))}
    </Stage>
  );
};

export default OfficeLayout;
