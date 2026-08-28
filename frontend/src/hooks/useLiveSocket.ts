"use client";

import { useEffect, useReducer, useRef } from "react";
import type { Decision, LiveMessage, Position, Regime } from "@/lib/types";

export interface LiveState {
  connected: boolean;
  running: boolean;
  cycle: number;
  capital: number;
  equity: number;
  peakEquity: number;
  positions: Position[];
  prices: Record<string, number>;
  regimes: Record<string, Regime>;
  recentDecisions: Decision[];
}

const initialState: LiveState = {
  connected: false,
  running: true,
  cycle: 0,
  capital: 0,
  equity: 0,
  peakEquity: 0,
  positions: [],
  prices: {},
  regimes: {},
  recentDecisions: [],
};

type Action = { type: "connected" } | { type: "disconnected" } | { type: "message"; message: LiveMessage };

function reducer(state: LiveState, action: Action): LiveState {
  if (action.type === "connected") return { ...state, connected: true };
  if (action.type === "disconnected") return { ...state, connected: false };

  const message = action.message;
  switch (message.type) {
    case "snapshot":
      return {
        ...state,
        running: message.running,
        cycle: message.cycle,
        capital: message.capital,
        equity: message.equity,
        peakEquity: message.peak_equity,
        positions: message.positions,
        recentDecisions: message.recent_decisions,
      };
    case "tick":
      return { ...state, prices: { ...state.prices, [message.symbol]: message.price } };
    case "regime":
      return { ...state, regimes: { ...state.regimes, [message.asset]: message.new_regime } };
    case "status":
      return { ...state, running: message.running };
    case "decision":
      return { ...state, recentDecisions: [message.decision, ...state.recentDecisions].slice(0, 50) };
    default:
      return state;
  }
}

function wsUrl(): string {
  return process.env.NEXT_PUBLIC_WS_URL ?? "ws://localhost:8000/ws/live";
}

export function useLiveSocket() {
  const [state, dispatch] = useReducer(reducer, initialState);
  const retryDelay = useRef(1000);

  useEffect(() => {
    let socket: WebSocket | null = null;
    let cancelled = false;
    let retryTimer: ReturnType<typeof setTimeout>;

    function connect() {
      if (cancelled) return;
      socket = new WebSocket(wsUrl());

      socket.onopen = () => {
        retryDelay.current = 1000;
        dispatch({ type: "connected" });
      };

      socket.onmessage = (event) => {
        try {
          const message = JSON.parse(event.data) as LiveMessage;
          dispatch({ type: "message", message });
        } catch {
          // ignore malformed frames
        }
      };

      socket.onclose = () => {
        dispatch({ type: "disconnected" });
        if (!cancelled) {
          retryTimer = setTimeout(connect, retryDelay.current);
          retryDelay.current = Math.min(15000, retryDelay.current * 2);
        }
      };

      socket.onerror = () => socket?.close();
    }

    connect();
    return () => {
      cancelled = true;
      clearTimeout(retryTimer);
      socket?.close();
    };
  }, []);

  return state;
}
