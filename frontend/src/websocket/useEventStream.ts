import { useEffect, useRef, useState, useCallback } from 'react';
import { useOfficeStore } from '../state/officeStore';

const WS_URL = 'ws://localhost:8000/ws';
const MAX_RETRIES = 10;
const BASE_DELAY_MS = 1000;
const MAX_DELAY_MS = 30000;

export interface EventStreamState {
  connected: boolean;
  lastEvent: Record<string, unknown> | null;
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
          const data = JSON.parse(event.data as string) as Record<string, unknown>;
          setLastEvent(data);
          processEvent(data);
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
  }, [setConnected, processEvent]);

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
