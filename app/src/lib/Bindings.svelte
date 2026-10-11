<script lang="ts">
  import Board3D from "./Board3D.svelte";
  import type { Backend } from "./backend.svelte";

  let { backend }: { backend: Backend } = $props();

  let listening = $state<"left" | "right" | "pop" | null>(null);

  const tick = $derived(backend.tick);
  const lean = $derived(tick?.tele.lean ?? 0);
  const pitch = $derived(tick?.tele.pitch ?? 0);
  const keysOn = $derived(tick?.keys ?? false);
  const popOn = $derived(tick?.pop_enabled ?? false);

  function onkeydown(e: KeyboardEvent) {
    if (!listening) return;
    e.preventDefault();
    if (e.repeat) return;
    if (listening === "pop" && (e.key === "Backspace" || e.key === "Delete")) {
      backend.send({ cmd: "pop", on: false });
    } else if (listening === "pop" && e.key === " ") {
      backend.send({ cmd: "bind", action: "pop", key: "space" });
    } else if (e.key !== "Escape" && /^[a-z]$/i.test(e.key)) {
      backend.send({ cmd: "bind", action: listening, key: e.key.toLowerCase() });
    }
    listening = null;
  }
</script>

<svelte:window {onkeydown} />

{#snippet binding(action: "left" | "right", label: string, side: string)}
  {@const key = tick?.bindings[action] ?? "?"}
  {@const active = keysOn && tick?.state === action.toUpperCase()}
  <div class={["callout", side, { active }]}>
    <span class="label">{label}</span>
    <button
      class={["key", { listening: listening === action }]}
      title="Click, then press a letter"
      onclick={() => (listening = listening === action ? null : action)}
    >
      {listening === action ? "PRESS KEY" : key.toUpperCase()}
    </button>
  </div>
{/snippet}

<section class="bindings">
  <Board3D {lean} {pitch} />

  {@render binding("left", "LEAN LEFT", "left")}
  {@render binding("right", "LEAN RIGHT", "right")}

  <div class={["callout", "back", { disabled: !tick?.pop_available, active: keysOn && popOn && tick?.pop }]}>
    <span class="label">BACK-FOOT · POP</span>
    <button
      class={["key", { listening: listening === "pop" }]}
      disabled={!tick?.pop_available}
      title="Click, then press Space or a letter. Delete disables pop; Escape cancels."
      onclick={() => (listening = listening === "pop" ? null : "pop")}
    >
      {listening === "pop" ? "PRESS KEY" : (tick?.bindings.pop ?? "space").toUpperCase()}
    </button>
    <button
      class="pop-toggle"
      disabled={!tick?.pop_available}
      aria-pressed={popOn}
      title={popOn ? "Turn off pop input; steering stays on" : "Turn on pop input"}
      onclick={() => {
        listening = null;
        backend.send({ cmd: "pop", on: !popOn });
      }}
    >POP {popOn ? "ON" : "OFF"}</button>
  </div>

  <div class="readout">
    <span>LEAN {lean.toFixed(1)}°</span>
    <span>PITCH {pitch.toFixed(1)}°</span>
    <button class="calibrate" onclick={() => backend.send({ cmd: "calibrate" })} title="Stand neutral, then click">
      CALIBRATE
    </button>
  </div>

  <div class="phone">
    {#if tick?.phone?.connected}
      <div class="phone-keys">
        <span class={["key", { lit: tick.phone.y }]}>Y</span>
        <span class="label">WALK ⇄ SKATE</span>
      </div>
      <div class="phone-keys">
        <span class={["key", { lit: tick.phone.walk }]}>WALK</span>
        <span class="label">W · {tick.phone.walk ? "ON" : "OFF"}</span>
      </div>
      <div class="phone-keys">
        <span class={["key", { lit: tick.phone.push }]}>PUSH</span>
        <span class="label">A · {tick.phone.push ? "ON" : "OFF"}</span>
      </div>
    {:else if tick}
      <!-- Only once the backend is up, so the image never loads before the server exists. -->
      <img class="qr" src="http://127.0.0.1:8765/phone/qr.svg?u={encodeURIComponent(tick.phone_url)}" alt="Phone QR" />
    {/if}
    <span class="phone-label">{tick?.phone?.connected ? "PHONE CONNECTED" : "SCAN · PHONE BUTTONS"}</span>
  </div>
</section>

<style>
  .phone {
    position: absolute;
    right: 22px;
    bottom: 62px;
    display: flex;
    flex-direction: column;
    align-items: flex-end;
    gap: 8px;
    font-family: var(--label);
    font-style: oblique;
    font-size: 11px;
    color: var(--muted);
  }
  .qr { width: 132px; height: 132px; image-rendering: pixelated; }
  .phone-keys { display: flex; align-items: center; gap: 10px; flex-direction: row-reverse; }
  .phone-keys .key.lit { background: var(--red-hot); color: var(--white); }
  .phone-label { letter-spacing: 0.5px; }
  .bindings {
    position: absolute;
    inset: 0;
  }
  .callout {
    position: absolute;
    display: flex;
    align-items: center;
    gap: 10px;
    font-family: var(--label);
    font-style: oblique;
    font-size: 13px;
    letter-spacing: 0.5px;
    color: var(--muted);
    transition: color 80ms;
  }
  .callout::before {
    content: "";
    width: 70px;
    height: 2px;
    background: currentColor;
    order: var(--line-order, 0);
  }
  .left { left: 9%; top: 44%; flex-direction: row-reverse; --line-order: -1; }
  .right { right: 9%; top: 30%; }
  .back { left: 50%; bottom: 17%; transform: translateX(-50%); }
  .back::before { display: none; }
  .active { color: var(--white); }
  .label { white-space: nowrap; }
  .key {
    min-width: 46px;
    padding: 5px 10px;
    background: var(--chip);
    color: var(--ink);
    border: none;
    text-align: center;
    font-family: var(--label);
    font-style: oblique;
    font-size: 13px;
  }
  .active .key { background: var(--red-hot); color: var(--white); }
  .key.listening { background: var(--white); outline: 2px solid var(--red-hot); }
  .disabled { opacity: 0.4; }
  .pop-toggle {
    padding: 5px 9px;
    background: transparent;
    border: 1px solid var(--muted);
    color: var(--muted);
    font-family: var(--label);
    font-style: oblique;
    font-size: 11px;
    white-space: nowrap;
  }
  .pop-toggle[aria-pressed="true"] { color: var(--white); border-color: var(--red-hot); }
  .readout {
    position: absolute;
    left: 50%;
    top: 7%;
    transform: translateX(-50%);
    display: flex;
    gap: 22px;
    align-items: center;
    font-family: var(--label);
    font-style: oblique;
    font-size: 12px;
    color: var(--muted);
  }
  .calibrate {
    background: none;
    border: 1px solid var(--muted);
    padding: 4px 10px;
    font-family: var(--label);
    font-style: oblique;
    font-size: 11px;
    color: var(--white);
  }
  .calibrate:hover { border-color: var(--red-hot); }
</style>
