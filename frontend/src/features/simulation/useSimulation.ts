"use client";

import { useCallback, useEffect, useMemo, useReducer, useRef } from "react";

import type { CityOsTransport } from "../../lib/api/transport";
import type { SimulationRequest } from "../../lib/contracts/generated";
import {
  createInitialSimulationState,
  selectCurrentFrames,
  selectTerminalMetrics,
  simulationReducer,
  type PlaybackSpeed,
} from "./state";

const STATUS_POLL_MS = 500;
const RETRY_DELAYS_MS = [250, 500, 1_000] as const;

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : "Falha inesperada na simulação";
}

export interface UseSimulationOptions {
  durationMinutes?: number;
  statusPollMs?: number;
}

export function useSimulation(
  transport: CityOsTransport,
  options: UseSimulationOptions = {},
) {
  const [state, dispatch] = useReducer(
    simulationReducer,
    options.durationMinutes ?? 360,
    createInitialSimulationState,
  );
  const cleanupRef = useRef<() => void>(() => undefined);
  const timelineRef = useRef<number[]>([]);
  const mountedRef = useRef(true);

  useEffect(() => {
    timelineRef.current = state.timeline;
  }, [state.timeline]);

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
      cleanupRef.current();
    };
  }, []);

  useEffect(() => {
    if (!state.playing) return undefined;
    let previous = performance.now();
    const interval = window.setInterval(() => {
      const now = performance.now();
      dispatch({ type: "tick", elapsedSeconds: (now - previous) / 1_000 });
      previous = now;
    }, 100);
    return () => window.clearInterval(interval);
  }, [state.playing]);

  const reset = useCallback(() => {
    cleanupRef.current();
    cleanupRef.current = () => undefined;
    dispatch({ type: "reset" });
  }, []);

  const run = useCallback(
    async (request: SimulationRequest) => {
      cleanupRef.current();
      dispatch({ type: "runRequested" });

      const abortController = new AbortController();
      const timers = new Set<ReturnType<typeof setTimeout>>();
      let unsubscribe: () => void = () => undefined;
      let stopped = false;
      let retryCount = 0;

      const cleanup = () => {
        stopped = true;
        abortController.abort();
        unsubscribe();
        for (const timer of timers) clearTimeout(timer);
        timers.clear();
      };
      cleanupRef.current = cleanup;

      try {
        const created = await transport.createSimulation(request);
        if (stopped || !mountedRef.current) return;
        dispatch({ type: "simulationCreated", simulationId: created.simulation_id });

        const subscribe = () => {
          if (stopped) return;
          dispatch({
            type: "connectionChanged",
            connection: retryCount === 0 ? "connecting" : "retrying",
          });
          unsubscribe = transport.subscribeFrames(
            created.simulation_id,
            (frame) => {
              retryCount = 0;
              dispatch({ type: "connectionChanged", connection: "connected" });
              dispatch({ type: "frameReceived", frame });
            },
            (error) => {
              if (stopped) return;
              unsubscribe();
              if (retryCount >= RETRY_DELAYS_MS.length) {
                dispatch({ type: "failed", message: errorMessage(error) });
                return;
              }
              const delay = RETRY_DELAYS_MS[retryCount] ?? RETRY_DELAYS_MS.at(-1)!;
              retryCount += 1;
              dispatch({ type: "connectionChanged", connection: "retrying" });
              const timer = setTimeout(() => {
                timers.delete(timer);
                subscribe();
              }, delay);
              timers.add(timer);
            },
            {
              // Replay one bucket inclusively: if only one policy arrived before
              // the disconnect, its paired frame cannot be skipped on recovery.
              afterMinute:
                timelineRef.current.length === 0
                  ? undefined
                  : Math.max(
                      0,
                      (timelineRef.current[timelineRef.current.length - 1] ?? 0) - 5,
                    ),
              signal: abortController.signal,
              reconnect: false,
            },
          );
        };

        subscribe();

        const poll = async () => {
          if (stopped) return;
          try {
            const status = await transport.getSimulation(created.simulation_id);
            if (stopped) return;
            if (status.status === "completed") {
              if (status.metrics) {
                dispatch({ type: "terminalMetricsReceived", metrics: status.metrics });
              }
              dispatch({ type: "jobChanged", job: "completed" });
              unsubscribe();
              return;
            }
            if (status.status === "failed") {
              dispatch({
                type: "failed",
                message: status.error?.message ?? "A simulação não pôde ser concluída",
              });
              unsubscribe();
              return;
            }
            dispatch({ type: "jobChanged", job: "running" });
            const timer = setTimeout(poll, options.statusPollMs ?? STATUS_POLL_MS);
            timers.add(timer);
          } catch {
            // The frame subscription has its own replay path; a transient status
            // polling failure should not discard already validated frames.
            if (!stopped) {
              dispatch({ type: "connectionChanged", connection: "retrying" });
              const timer = setTimeout(poll, options.statusPollMs ?? STATUS_POLL_MS);
              timers.add(timer);
            }
          }
        };
        await poll();
      } catch (error) {
        if (!stopped && mountedRef.current) {
          dispatch({ type: "failed", message: errorMessage(error) });
        }
      }
    },
    [options.statusPollMs, transport],
  );

  const currentFrames = useMemo(() => selectCurrentFrames(state), [state]);
  const terminalMetrics = useMemo(() => selectTerminalMetrics(state), [state]);

  return {
    state,
    currentFrames,
    terminalMetrics,
    run,
    reset,
    setPlaying: useCallback(
      (playing: boolean) => dispatch({ type: playing ? "play" : "pause" }),
      [],
    ),
    setSpeed: useCallback(
      (speed: PlaybackSpeed) => dispatch({ type: "setSpeed", speed }),
      [],
    ),
    scrub: useCallback(
      (minute: number) => dispatch({ type: "scrub", minute }),
      [],
    ),
  };
}
