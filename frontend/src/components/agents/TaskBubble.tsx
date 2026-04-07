import React, { useRef } from 'react';
import { Graphics, Text, useTick } from '@pixi/react';
import * as PIXI from 'pixi.js';
import type { Task, Agent } from '../../state/officeStore';

interface TaskBubbleProps {
  task: Task;
  agent: Agent;
}

const STATUS_COLORS: Record<string, number> = {
  pending: 0x6b7280,
  assigned: 0x3b82f6,
  in_progress: 0xf59e0b,
  completed: 0x22c55e,
  failed: 0xef4444,
};

const TaskBubble: React.FC<TaskBubbleProps> = ({ task, agent }) => {
  const tickRef = useRef(0);
  const gRef = useRef<PIXI.Graphics>(null);
  const textRef = useRef<PIXI.Text>(null);

  useTick((delta) => {
    tickRef.current += delta * 0.03;
    if (!gRef.current || !textRef.current) return;

    const floatY = Math.sin(tickRef.current) * 4;
    const bx = agent.position.x;
    const by = agent.position.y - 80 + floatY;

    const g = gRef.current;
    g.clear();

    const bubbleColor = STATUS_COLORS[task.status] ?? 0x6b7280;
    const bubbleW = 120;
    const bubbleH = 32;

    // Bubble background
    g.beginFill(0x0f172a, 0.88);
    g.lineStyle(1.5, bubbleColor, 0.9);
    g.drawRoundedRect(bx - bubbleW / 2, by - bubbleH / 2, bubbleW, bubbleH, 8);
    g.endFill();

    // Tail pointing down to agent
    g.beginFill(0x0f172a, 0.88);
    g.lineStyle(1.5, bubbleColor, 0.9);
    g.moveTo(bx - 6, by + bubbleH / 2);
    g.lineTo(bx, by + bubbleH / 2 + 8);
    g.lineTo(bx + 6, by + bubbleH / 2);
    g.closePath();
    g.endFill();

    // Status dot
    g.beginFill(bubbleColor, 1);
    g.drawCircle(bx - bubbleW / 2 + 10, by, 4);
    g.endFill();

    // Update text position
    textRef.current.x = bx + 4;
    textRef.current.y = by;
  });

  const shortRequest = task.request.length > 14
    ? task.request.slice(0, 14) + '…'
    : task.request;

  const textStyle = new PIXI.TextStyle({
    fontFamily: 'monospace',
    fontSize: 9,
    fill: '#e2e8f0',
    align: 'left',
  });

  return (
    <>
      <Graphics ref={gRef} />
      <Text
        ref={textRef}
        text={shortRequest}
        style={textStyle}
        anchor={[0.5, 0.5]}
        x={agent.position.x}
        y={agent.position.y - 80}
      />
    </>
  );
};

export default TaskBubble;
