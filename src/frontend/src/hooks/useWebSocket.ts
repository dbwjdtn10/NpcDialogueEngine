import { useCallback, useEffect, useRef, useState } from 'react';
import { ChatResponse, ConnectionStatus } from '../types';

interface SessionStartData {
  session_id: string;
  npc_id: string;
  npc_name: string;
  emotion: string;
  affinity: number;
  affinity_level: string;
}

interface UseWebSocketOptions {
  onMessage: (response: ChatResponse) => void;
  onStreamToken?: (token: string) => void;
  onSessionStart?: (data: SessionStartData) => void;
  reconnectInterval?: number;
  maxReconnectAttempts?: number;
}

export function useWebSocket(options: UseWebSocketOptions) {
  const {
    onMessage,
    onStreamToken,
    onSessionStart,
    reconnectInterval = 3000,
    maxReconnectAttempts = 5,
  } = options;

  const [status, setStatus] = useState<ConnectionStatus>('disconnected');
  const [isNpcTyping, setIsNpcTyping] = useState(false);

  const wsRef = useRef<WebSocket | null>(null);
  const reconnectAttemptsRef = useRef(0);
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const currentNpcIdRef = useRef<string | null>(null);
  const currentUserIdRef = useRef<string | null>(null);
  const shouldReconnectRef = useRef(false);
  const onMessageRef = useRef(onMessage);
  const onStreamTokenRef = useRef(onStreamToken);
  const onSessionStartRef = useRef(onSessionStart);

  onMessageRef.current = onMessage;
  onStreamTokenRef.current = onStreamToken;
  onSessionStartRef.current = onSessionStart;

  const cleanup = useCallback(() => {
    if (reconnectTimerRef.current) {
      clearTimeout(reconnectTimerRef.current);
      reconnectTimerRef.current = null;
    }
    if (wsRef.current) {
      wsRef.current.onopen = null;
      wsRef.current.onmessage = null;
      wsRef.current.onclose = null;
      wsRef.current.onerror = null;
      if (wsRef.current.readyState === WebSocket.OPEN ||
          wsRef.current.readyState === WebSocket.CONNECTING) {
        wsRef.current.close();
      }
      wsRef.current = null;
    }
  }, []);

  const connectWs = useCallback((npcId: string, userId: string) => {
    cleanup();

    setStatus('connecting');
    shouldReconnectRef.current = true;
    currentNpcIdRef.current = npcId;
    currentUserIdRef.current = userId;

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const host = window.location.host;
    const url = `${protocol}//${host}/ws/chat/${npcId}?user_id=${userId}`;

    const ws = new WebSocket(url);
    wsRef.current = ws;

    ws.onopen = () => {
      setStatus('connected');
      reconnectAttemptsRef.current = 0;
    };

    ws.onmessage = (event: MessageEvent) => {
      try {
        const data = JSON.parse(event.data);

        switch (data.type) {
          case 'session_start':
            onSessionStartRef.current?.(data as SessionStartData);
            return;

          case 'token':
            // Backend streams individual characters as tokens
            setIsNpcTyping(true);
            onStreamTokenRef.current?.(data.content);
            return;

          case 'complete':
            // Backend sends the full response nested under data.data
            setIsNpcTyping(false);
            onMessageRef.current(data.data as ChatResponse);
            return;

          case 'error':
            setIsNpcTyping(false);
            console.error('Server error:', data.detail);
            return;

          default:
            console.warn('Unknown message type:', data.type);
        }
      } catch {
        // Non-JSON message, ignore
        console.warn('Non-JSON WebSocket message:', event.data);
      }
    };

    ws.onclose = () => {
      setStatus('disconnected');
      setIsNpcTyping(false);

      if (shouldReconnectRef.current &&
          reconnectAttemptsRef.current < maxReconnectAttempts) {
        reconnectAttemptsRef.current += 1;
        reconnectTimerRef.current = setTimeout(() => {
          if (currentNpcIdRef.current && currentUserIdRef.current) {
            connectWs(currentNpcIdRef.current, currentUserIdRef.current);
          }
        }, reconnectInterval);
      }
    };

    ws.onerror = () => {
      setStatus('error');
    };
  }, [cleanup, reconnectInterval, maxReconnectAttempts]);

  const disconnect = useCallback(() => {
    shouldReconnectRef.current = false;
    reconnectAttemptsRef.current = 0;
    cleanup();
    setStatus('disconnected');
    setIsNpcTyping(false);
  }, [cleanup]);

  const sendMessage = useCallback((content: string) => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ message: content }));
      setIsNpcTyping(true);
    }
  }, []);

  useEffect(() => {
    return () => {
      shouldReconnectRef.current = false;
      cleanup();
    };
  }, [cleanup]);

  return {
    connect: connectWs,
    disconnect,
    sendMessage,
    status,
    isNpcTyping,
  };
}
