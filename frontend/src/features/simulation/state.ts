import type { SimulationFrame, SimulationMetrics } from "../../lib/contracts/generated";

export type SimulationPolicy = "baseline" | "optimized";
export type PlaybackSpeed = 1 | 2 | 4;
export type ConnectionState =
  | "disconnected"
  | "connecting"
  | "connected"
  | "retrying";
export type SimulationJobState =
  | "idle"
  | "creating"
  | "running"
  | "completed"
  | "failed";

export type FramesByPolicy = Record<
  SimulationPolicy,
  Record<number, SimulationFrame>
>;

export interface SimulationState {
  simulationId: string | null;
  frames: FramesByPolicy;
  timeline: number[];
  currentMinute: number;
  durationMinutes: number;
  speed: PlaybackSpeed;
  playing: boolean;
  connection: ConnectionState;
  job: SimulationJobState;
  error: string | null;
  terminalMetrics: {
    baseline: SimulationMetrics;
    optimized: SimulationMetrics;
  } | null;
}

export type SimulationAction =
  | { type: "runRequested" }
  | { type: "simulationCreated"; simulationId: string }
  | { type: "frameReceived"; frame: SimulationFrame }
  | { type: "connectionChanged"; connection: ConnectionState }
  | { type: "jobChanged"; job: SimulationJobState }
  | {
      type: "terminalMetricsReceived";
      metrics: { baseline: SimulationMetrics; optimized: SimulationMetrics };
    }
  | { type: "failed"; message: string }
  | { type: "togglePlayback" }
  | { type: "play" }
  | { type: "pause" }
  | { type: "scrub"; minute: number }
  | { type: "setSpeed"; speed: PlaybackSpeed }
  | { type: "tick"; elapsedSeconds: number }
  | { type: "reset" };

const emptyFrames = (): FramesByPolicy => ({
  baseline: {},
  optimized: {},
});

export const createInitialSimulationState = (
  durationMinutes = 360,
): SimulationState => ({
  simulationId: null,
  frames: emptyFrames(),
  timeline: [],
  currentMinute: 0,
  durationMinutes,
  speed: 1,
  playing: false,
  connection: "disconnected",
  job: "idle",
  error: null,
  terminalMetrics: null,
});

function isPolicy(value: string): value is SimulationPolicy {
  return value === "baseline" || value === "optimized";
}

function clampMinute(minute: number, duration: number): number {
  if (!Number.isFinite(minute)) return 0;
  return Math.min(duration, Math.max(0, minute));
}

export function simulationReducer(
  state: SimulationState,
  action: SimulationAction,
): SimulationState {
  switch (action.type) {
    case "runRequested":
      return {
        ...createInitialSimulationState(state.durationMinutes),
        job: "creating",
        connection: "connecting",
      };
    case "simulationCreated":
      return {
        ...state,
        simulationId: action.simulationId,
        job: "running",
        playing: true,
        error: null,
      };
    case "frameReceived": {
      const { frame } = action;
      if (!isPolicy(frame.policy)) return state;
      if (state.frames[frame.policy][frame.minute] !== undefined) return state;

      const frames = {
        ...state.frames,
        [frame.policy]: {
          ...state.frames[frame.policy],
          [frame.minute]: frame,
        },
      };
      const timeline = Array.from(
        new Set([...state.timeline, frame.minute]),
      ).sort((left, right) => left - right);

      return { ...state, frames, timeline };
    }
    case "connectionChanged":
      return { ...state, connection: action.connection };
    case "jobChanged":
      return {
        ...state,
        job: action.job,
        connection: action.job === "completed" ? "disconnected" : state.connection,
        error: action.job === "failed" ? state.error : null,
      };
    case "terminalMetricsReceived":
      return { ...state, terminalMetrics: action.metrics };
    case "failed":
      return {
        ...state,
        job: "failed",
        connection: "disconnected",
        playing: false,
        error: action.message,
      };
    case "togglePlayback":
      return { ...state, playing: !state.playing };
    case "play":
      return { ...state, playing: true };
    case "pause":
      return { ...state, playing: false };
    case "scrub":
      return {
        ...state,
        currentMinute: clampMinute(action.minute, state.durationMinutes),
      };
    case "setSpeed":
      return { ...state, speed: action.speed };
    case "tick": {
      if (!state.playing || action.elapsedSeconds <= 0) return state;
      // Six simulated hours play in about 60 real seconds at 1x.
      const simulatedMinutes = action.elapsedSeconds * 6 * state.speed;
      const currentMinute = clampMinute(
        state.currentMinute + simulatedMinutes,
        state.durationMinutes,
      );
      return {
        ...state,
        currentMinute,
        playing: currentMinute < state.durationMinutes,
      };
    }
    case "reset":
      return createInitialSimulationState(state.durationMinutes);
  }
}

function frameAtOrBefore(
  frames: Record<number, SimulationFrame>,
  minute: number,
): SimulationFrame | null {
  let selectedMinute = -Infinity;
  for (const key of Object.keys(frames)) {
    const candidate = Number(key);
    if (candidate <= minute && candidate > selectedMinute) {
      selectedMinute = candidate;
    }
  }
  return selectedMinute === -Infinity ? null : frames[selectedMinute] ?? null;
}

export function selectCurrentFrames(state: SimulationState): {
  baseline: SimulationFrame | null;
  optimized: SimulationFrame | null;
} {
  return {
    baseline: frameAtOrBefore(state.frames.baseline, state.currentMinute),
    optimized: frameAtOrBefore(state.frames.optimized, state.currentMinute),
  };
}

function terminalFrame(
  frames: Record<number, SimulationFrame>,
): SimulationFrame | null {
  const minutes = Object.keys(frames).map(Number);
  if (minutes.length === 0) return null;
  return frames[Math.max(...minutes)] ?? null;
}

export function selectTerminalMetrics(state: SimulationState): {
  baseline: SimulationMetrics | null;
  optimized: SimulationMetrics | null;
} {
  if (state.terminalMetrics) return state.terminalMetrics;
  return {
    baseline: terminalFrame(state.frames.baseline)?.metrics ?? null,
    optimized: terminalFrame(state.frames.optimized)?.metrics ?? null,
  };
}
