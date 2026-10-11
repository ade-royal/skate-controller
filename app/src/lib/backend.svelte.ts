// Live connection to the Python backend (backend/server.py).

export type Tele = {
  a: [number, number, number];
  g: [number, number, number];
  lean: number;
  pitch: number;
  gtotal: number;
  steer: number;
};

export type Tick = {
  pi: "idle" | "starting" | "live" | "error";
  alert: string;
  sensor: boolean;
  camera: "none" | "ok" | "error";
  cam_url: string;
  keys: boolean;
  bridge: boolean;
  pop_available: boolean;
  pop_enabled: boolean;
  pop: boolean;
  state: "LEFT" | "CENTER" | "RIGHT";
  held: string | null;
  bindings: { left: string; right: string; pop: string };
  center: number;
  ride_s: number;
  tele: Partial<Tele>;
  phone: { connected: boolean; walk: boolean; push: boolean; y: boolean };
  phone_url: string;
};

const URL = "ws://127.0.0.1:8765/ws";

export class Backend {
  tick = $state.raw<Tick | null>(null);
  connected = $state(false);
  maxLean = $state(0);
  turns = $state(0);

  #ws: WebSocket | null = null;
  #lastState = "CENTER";
  #lastPi = "idle";

  constructor() {
    this.#connect();
  }

  #connect() {
    const ws = new WebSocket(URL);
    this.#ws = ws;
    ws.onopen = () => (this.connected = true);
    ws.onmessage = (e) => this.#onTick(JSON.parse(e.data));
    ws.onclose = () => {
      this.connected = false;
      setTimeout(() => this.#connect(), 1000);
    };
  }

  #onTick(t: Tick) {
    if (t.pi === "live" && this.#lastPi !== "live") {
      this.maxLean = 0;
      this.turns = 0;
    }
    this.#lastPi = t.pi;
    if (t.state !== this.#lastState && t.state !== "CENTER") this.turns += 1;
    this.#lastState = t.state;
    if (t.tele.lean !== undefined) this.maxLean = Math.max(this.maxLean, Math.abs(t.tele.lean));
    this.tick = t;
  }

  send(cmd: Record<string, unknown>) {
    if (this.#ws?.readyState === WebSocket.OPEN) this.#ws.send(JSON.stringify(cmd));
  }
}
