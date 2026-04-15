import { useEffect, useRef, useState, useCallback } from 'react';
import { useOfficeStore } from '../state/officeStore';

// Suporta override via variável de ambiente Vite para deploy em produção
const WS_URL = import.meta.env.VITE_WS_URL ?? 'ws://127.0.0.1:8124/ws';
const MAX_RETRIES = 10;
const BASE_DELAY_MS = 1000;
const MAX_DELAY_MS = 30000;

export interface EventStreamState {
  connected: boolean;
  lastEvent: Record<string, unknown> | null;
}

interface WebSocketEnvelope {
  type?: string;
  data?: Record<string, unknown>;
  events?: Record<string, unknown>[];
}

export function useEventStream(): EventStreamState {
  const wsRef = useRef<WebSocket | null>(null);
  const retriesRef = useRef(0);
  const retryTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const unmountedRef = useRef(false);

  const [connected, setConnectedLocal] = useState(false);
  const [lastEvent, setLastEvent] = useState<Record<string, unknown> | null>(null);

  const setConnected = useOfficeStore((s) => s.setConnected);
  const processEvent = useOfficeStore((s) => s.processEvent);

  const handleMessage = useCallback((payload: WebSocketEnvelope | Record<string, unknown>) => {
    const envelope = payload as WebSocketEnvelope;

    if (envelope.type === 'heartbeat' || envelope.type === 'pong') {
      return;
    }

    if (envelope.type === 'history') {
      const history = Array.isArray(envelope.events) ? envelope.events : [];
      for (const item of history) {
        processEvent(item);
      }
      if (history.length > 0) {
        setLastEvent(history[history.length - 1]);
      }
      return;
    }

    if (envelope.type === 'event' && envelope.data) {
      setLastEvent(envelope.data);
      processEvent(envelope.data);
      return;
    }

    const directEvent = payload as Record<string, unknown>;
    if (typeof directEvent.event_type === 'string') {
      setLastEvent(directEvent);
      processEvent(directEvent);
    }
  }, [processEvent]);

  const connect = useCallback(() => {
    if (unmountedRef.current) return;
    if (wsRef.current && wsRef.current.readyState === WebSocket.CONNECTING) return;

    try {
      const ws = new WebSocket(WS_URL);
      wsRef.current = ws;

      ws.onopen = () => {
        if (unmountedRef.current) { ws.close(); return; }
        retriesRef.current = 0;
        setConnectedLocal(true);
        setConnected(true);
        console.info('[WS] Connected to', WS_URL);
      };

      ws.onmessage = (event) => {
        if (unmountedRef.current) return;
        try {
          const data = JSON.parse(event.data as string) as WebSocketEnvelope;
          handleMessage(data);
        } catch (err) {
          console.warn('[WS] Failed to parse message:', event.data, err);
        }
      };

      ws.onclose = (event) => {
        if (unmountedRef.current) return;
        setConnectedLocal(false);
        setConnected(false);
        console.warn(`[WS] Closed (code=${event.code}). Retry #${retriesRef.current + 1}`);
        scheduleReconnect();
      };

      ws.onerror = (err) => {
        console.error('[WS] Error:', err);
        ws.close();
      };
    } catch (err) {
      console.error('[WS] Failed to create WebSocket:', err);
      scheduleReconnect();
    }
  }, [handleMessage, setConnected]);

  const scheduleReconnect = useCallback(() => {
    if (unmountedRef.current) return;
    if (retriesRef.current >= MAX_RETRIES) {
      console.error('[WS] Max retries reached. Giving up.');
      return;
    }

    // Exponential backoff: 1s, 2s, 4s, 8s … capped at 30s
    const delay = Math.min(BASE_DELAY_MS * Math.pow(2, retriesRef.current), MAX_DELAY_MS);
    retriesRef.current += 1;

    console.info(`[WS] Reconnecting in ${delay}ms (attempt ${retriesRef.current}/${MAX_RETRIES})…`);

    retryTimerRef.current = setTimeout(() => {
      if (!unmountedRef.current) connect();
    }, delay);
  }, [connect]);

  useEffect(() => {
    unmountedRef.current = false;
    connect();

    return () => {
      unmountedRef.current = true;
      if (retryTimerRef.current) clearTimeout(retryTimerRef.current);
      if (wsRef.current) {
        wsRef.current.onclose = null; // Prevent reconnect loop on intentional close
        wsRef.current.close();
        wsRef.current = null;
      }
      setConnected(false);
    };
  }, [connect, setConnected]);

  return { connected, lastEvent };
}
