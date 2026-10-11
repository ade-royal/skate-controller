<script lang="ts">
  import type { Backend } from "./backend.svelte";

  let { backend }: { backend: Backend } = $props();

  // The webcam is mounted upside down on the board; remember the choice.
  let flipped = $state(localStorage.getItem("camFlip") !== "0");
  function toggleFlip() {
    flipped = !flipped;
    localStorage.setItem("camFlip", flipped ? "1" : "0");
  }

  const tick = $derived(backend.tick);
  const tele = $derived(tick?.tele ?? {});
  const camOk = $derived(tick?.camera === "ok");
  const lean = $derived(tele.lean ?? 0);
  const pitch = $derived(tele.pitch ?? 0);
  const [ax, ay] = $derived(tele.a ?? [0, 0, 0]);
  const spin = $derived(tele.g?.[2] ?? 0);

  // Lean arc: +-30 deg spans the gauge.
  const ARC_RANGE = 30;
  const needle = $derived(Math.max(-1, Math.min(1, lean / ARC_RANGE)) * 90);

  function clock(s: number) {
    const m = Math.floor(s / 60);
    return `${String(m).padStart(2, "0")}:${String(Math.floor(s % 60)).padStart(2, "0")}`;
  }
</script>

<section class="pov">
  {#if camOk && tick}
    <img class={["feed", { flipped }]} src={tick.cam_url} alt="Board camera" />
  {:else}
    <div class="placeholder">{tick?.pi === "live" ? "camera offline" : "waiting for the board"}</div>
  {/if}

  <button class="rotate" onclick={toggleFlip}>ROTATE 180°</button>

  <div class="hud">
    <div class="rec">
      <span class={["dot", { on: tick?.pi === "live" }]}></span>
      LIVE {clock(tick?.ride_s ?? 0)}
    </div>

    <div class="stats">
      <div><b>{backend.maxLean.toFixed(1)}°</b><span>MAX LEAN</span></div>
      <div><b>{backend.turns}</b><span>TURNS</span></div>
      <div><b>{Math.abs(spin).toFixed(0)}</b><span>SPIN °/S</span></div>
      <div><b>{(tele.gtotal ?? 0).toFixed(2)}</b><span>G</span></div>
    </div>

    <div class="pitch">
      <span>PITCH</span>
      <div class="bar"><i style:bottom="{50 + Math.max(-50, Math.min(50, pitch * 2.5))}%"></i></div>
      <span>{pitch.toFixed(1)}°</span>
    </div>

    <div class="gforce">
      <div class="ring"><i style:left="{50 + Math.max(-45, Math.min(45, ay * 150))}%" style:top="{50 - Math.max(-45, Math.min(45, ax * 150))}%"></i></div>
      <span>BALANCE</span>
    </div>

    <div class="lean">
      <svg viewBox="-110 -110 220 120" width="260">
        <path d="M -100 0 A 100 100 0 0 1 100 0" class="track" />
        <line x1="0" y1="0" x2="0" y2="-96" class="needle" transform="rotate({needle})" />
      </svg>
      <div class="lean-value">{lean >= 0 ? "R" : "L"} {Math.abs(lean).toFixed(1)}°</div>
      <div class="keys">
        <span class={["k", { on: tick?.keys && tick?.state === "LEFT" }]}>{tick?.bindings.left.toUpperCase() ?? "A"}</span>
        <span class={["k", "pop", { on: tick?.pop, off: !tick?.pop_available }]}>{(tick?.bindings.pop ?? "space").toUpperCase()}</span>
        <span class={["k", { on: tick?.keys && tick?.state === "RIGHT" }]}>{tick?.bindings.right.toUpperCase() ?? "D"}</span>
      </div>
    </div>
  </div>
</section>

<style>
  .pov { position: absolute; inset: 0; background: #d9d9d9; }
  .feed { position: absolute; inset: 0; width: 100%; height: 100%; object-fit: cover; }
  .feed.flipped { transform: rotate(180deg); }
  .rotate {
    position: absolute;
    right: 22px;
    top: 100px;
    z-index: 2;
    padding: 4px 9px;
    background: rgba(11, 11, 11, 0.55);
    border: 1px solid var(--chip);
    color: var(--white);
    font-family: var(--label);
    font-style: oblique;
    font-size: 10px;
  }
  .placeholder {
    position: absolute;
    inset: 0;
    display: grid;
    place-items: center;
    color: var(--ink);
    font-family: "Coolvetica";
    font-style: italic;
    font-size: 34px;
  }
  .hud {
    position: absolute;
    inset: 0;
    font-family: var(--label);
    font-style: oblique;
    color: var(--white);
    text-shadow: 0 1px 3px rgba(0, 0, 0, 0.8);
    pointer-events: none;
  }
  .rec { position: absolute; top: 18px; left: 22px; display: flex; gap: 8px; align-items: center; font-size: 13px; }
  .dot { width: 10px; height: 10px; border-radius: 50%; background: var(--muted); }
  .dot.on { background: var(--red-hot); box-shadow: 0 0 8px var(--red-hot); }
  .stats { position: absolute; top: 56px; left: 22px; display: grid; gap: 10px; }
  .stats div { display: flex; flex-direction: column; }
  .stats b { font-size: 24px; font-variant-numeric: tabular-nums; }
  .stats span { font-size: 10px; opacity: 0.85; }
  .pitch { position: absolute; right: 26px; top: 50%; transform: translateY(-50%); display: flex; flex-direction: column; align-items: center; gap: 6px; font-size: 10px; }
  .bar { position: relative; width: 6px; height: 160px; background: rgba(255, 255, 255, 0.3); }
  .bar i { position: absolute; left: -5px; width: 16px; height: 3px; background: var(--red-hot); }
  .gforce { position: absolute; left: 22px; top: 290px; display: flex; flex-direction: column; align-items: center; gap: 6px; font-size: 10px; }
  .ring { position: relative; width: 70px; height: 70px; border: 2px solid rgba(255, 255, 255, 0.7); border-radius: 50%; }
  .ring i { position: absolute; width: 10px; height: 10px; margin: -5px; border-radius: 50%; background: var(--red-hot); }
  .lean { position: absolute; left: 50%; bottom: 22px; transform: translateX(-50%); display: flex; flex-direction: column; align-items: center; }
  .track { fill: none; stroke: rgba(255, 255, 255, 0.75); stroke-width: 4; }
  .needle { stroke: var(--red-hot); stroke-width: 5; stroke-linecap: round; transition: transform 60ms linear; }
  .lean-value { margin-top: -18px; font-size: 22px; font-variant-numeric: tabular-nums; }
  .keys { display: flex; gap: 8px; margin-top: 8px; }
  .k { min-width: 40px; padding: 4px 8px; background: rgba(217, 217, 217, 0.85); color: var(--ink); text-align: center; font-size: 12px; text-shadow: none; }
  .k.on { background: var(--red-hot); color: var(--white); }
  .k.off { opacity: 0.35; }
</style>
