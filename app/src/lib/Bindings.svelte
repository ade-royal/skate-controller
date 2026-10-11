<script lang="ts">
  import Board3D from "./Board3D.svelte";
  import type { Backend } from "./backend.svelte";

  let { backend }: { backend: Backend } = $props();

  let listening = $state<"left" | "right" | null>(null);

  const tick = $derived(backend.tick);
  const lean = $derived(tick?.tele.lean ?? 0);
  const pitch = $derived(tick?.tele.pitch ?? 0);
  const keysOn = $derived(tick?.keys ?? false);

  function onkeydown(e: KeyboardEvent) {
    if (!listening) return;
    e.preventDefault();
    if (e.key !== "Escape" && /^[a-z]$/i.test(e.key)) {
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

  <div class={["callout", "back", { disabled: !tick?.pop_available, active: tick?.pop }]}>
    <span class="label">LEAN BACK · POP</span>
    <span class="key">{(tick?.bindings.pop ?? "space").toUpperCase()}</span>
    {#if !tick?.pop_available}<span class="soon">OFF · SOON</span>{/if}
  </div>

  <div class="readout">
    <span>LEAN {lean.toFixed(1)}°</span>
    <span>PITCH {pitch.toFixed(1)}°</span>
    <button class="calibrate" onclick={() => backend.send({ cmd: "calibrate" })} title="Stand neutral, then click">
      CALIBRATE
    </button>
  </div>
</section>

<style>
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
  .soon { font-size: 10px; }
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
