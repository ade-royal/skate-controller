<script lang="ts">
  import { Backend } from "$lib/backend.svelte";
  import Bindings from "$lib/Bindings.svelte";
  import RidePov from "$lib/RidePov.svelte";

  const backend = new Backend();
  let tab = $state<"bindings" | "pov">("bindings");

  const tick = $derived(backend.tick);
  const alert = $derived(!backend.connected ? "App backend not running. Restart the app." : (tick?.alert ?? ""));
  const piLabel = $derived(
    { idle: "…", starting: "CONNECTING", live: "LIVE", error: "OFFLINE" }[tick?.pi ?? "idle"]
  );
</script>

<main class={tab}>
  {#if tab === "bindings"}
    <Bindings {backend} />
  {:else}
    <RidePov {backend} />
  {/if}

  <div class="status">
    <span class={["chip", { ok: tick?.pi === "live", bad: tick?.pi === "error" }]}>PI {piLabel}</span>
    <span class={["chip", { ok: tick?.sensor }]}>SENSOR</span>
    <span class={["chip", { ok: tick?.camera === "ok" }]}>CAM</span>
    <span class={["chip", { ok: tick?.phone?.connected }]}>PHONE</span>
  </div>

  <div class="toggles">
    <button class={["toggle", { on: tick?.keys }]} onclick={() => backend.send({ cmd: "keys", on: !tick?.keys })}>
      KEYS {tick?.keys ? "ON" : "OFF"}
    </button>
    <button class={["toggle", { on: tick?.bridge }]} onclick={() => backend.send({ cmd: "bridge", on: !tick?.bridge })}>
      XBOX BRIDGE {tick?.bridge ? "ON" : "OFF"}
    </button>
  </div>

  {#if alert}
    <div class="alert" role="alert">
      <span>{alert}</span>
      {#if backend.connected && tick?.pi === "error"}
        <button onclick={() => backend.send({ cmd: "retry" })}>RETRY</button>
      {/if}
      {#if backend.connected}
        <button class="x" aria-label="Dismiss" onclick={() => backend.send({ cmd: "dismiss" })}>✕</button>
      {/if}
    </div>
  {/if}

  <button class={["tab", "tab-bindings", { current: tab === "bindings" }]} onclick={() => (tab = "bindings")}>
    BINDINGS
  </button>
  <button class={["tab", "tab-pov", { current: tab === "pov" }]} onclick={() => (tab = "pov")}>RIDE POV</button>

  <footer class="brand">
    <h1><span>SKATE</span><span>CONTROLLER</span></h1>
    <p><b>HACKLANTA '26,</b> Royal x David</p>
  </footer>
</main>

<style>
  main {
    position: fixed;
    inset: 0;
    background: var(--bg);
  }
  .brand { position: absolute; left: 26px; bottom: 18px; pointer-events: none; }
  h1 {
    margin: 0;
    display: flex;
    flex-direction: column;
    font-family: "Barge", sans-serif;
    font-style: italic;
    font-weight: 900;
    line-height: 0.95;
    color: var(--white);
    text-shadow: 0 2px 6px rgba(0, 0, 0, 0.5);
  }
  h1 span:first-child { font-size: 66px; padding-left: 14px; }
  h1 span:last-child { font-size: 43px; }
  .brand p { margin: 8px 0 0; font-family: "Coolvetica"; font-size: 17px; color: var(--white); }
  .brand b { font-style: italic; font-weight: 700; }

  .tab {
    position: absolute;
    right: 22px;
    padding: 5px 12px;
    background: var(--chip);
    color: var(--ink);
    border: 1px solid #9a9a9a;
    font-family: var(--label);
    font-style: oblique;
    font-size: 11px;
  }
  .tab-bindings { top: 18px; }
  .tab-pov { bottom: 18px; }
  .tab.current { background: var(--red-hot); color: var(--white); border-color: var(--red-hot); }

  .status, .toggles {
    position: absolute;
    left: 22px;
    display: flex;
    gap: 6px;
    font-family: var(--label);
    font-style: oblique;
    font-size: 10px;
  }
  .status { top: 16px; }
  .toggles { top: 40px; }
  .pov .status, .pov .toggles { left: auto; right: 22px; justify-content: flex-end; }
  .pov .status { top: 52px; }
  .pov .toggles { top: 76px; }
  .chip { padding: 3px 8px; background: #222; color: var(--muted); }
  .chip::before { content: "● "; }
  .chip.ok { color: #3fd27a; }
  .chip.bad { color: var(--red-hot); }
  .toggle {
    padding: 4px 9px;
    background: transparent;
    border: 1px solid var(--muted);
    color: var(--muted);
    font-family: var(--label);
    font-style: oblique;
    font-size: 10px;
  }
  .toggle.on { background: var(--red-hot); border-color: var(--red-hot); color: var(--white); }

  .alert {
    position: absolute;
    top: 14px;
    left: 50%;
    transform: translateX(-50%);
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 8px 14px;
    background: var(--red-hot);
    color: var(--white);
    font-family: var(--label);
    font-style: oblique;
    font-size: 12px;
    z-index: 10;
    max-width: 70%;
  }
  .alert button {
    background: var(--white);
    color: var(--ink);
    border: none;
    padding: 3px 9px;
    font-family: var(--label);
    font-style: oblique;
    font-size: 11px;
  }
  .alert .x { background: transparent; color: var(--white); padding: 0 2px; }
</style>
