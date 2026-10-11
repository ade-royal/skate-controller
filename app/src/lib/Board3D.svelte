<script lang="ts">
  // Line-art 3D skateboard that tilts with the real board.
  import { untrack } from "svelte";
  import * as THREE from "three";
  import { LineSegments2 } from "three/examples/jsm/lines/LineSegments2.js";
  import { LineSegmentsGeometry } from "three/examples/jsm/lines/LineSegmentsGeometry.js";
  import { LineMaterial } from "three/examples/jsm/lines/LineMaterial.js";

  let { lean = 0, pitch = 0 }: { lean?: number; pitch?: number } = $props();

  // Real leans are a few degrees; exaggerate so the motion reads from across a room.
  const LEAN_GAIN = 3;
  const PITCH_GAIN = 2;
  const MAX_TILT = 35;
  const LINE_COLOR = 0x8a0d0d;
  const BG_COLOR = 0x0b0b0b;

  const DECK_LENGTH = 8;
  const DECK_WIDTH = 2.1;
  const KICK_START = 2.6;
  const KICK_SLOPE = Math.tan(THREE.MathUtils.degToRad(20));

  function deckGeometry(): THREE.BufferGeometry {
    const r = DECK_WIDTH / 2;
    const half = DECK_LENGTH / 2 - r;
    const shape = new THREE.Shape();
    shape.moveTo(-half, -r);
    shape.lineTo(half, -r);
    shape.absarc(half, 0, r, -Math.PI / 2, Math.PI / 2, false);
    shape.lineTo(-half, r);
    shape.absarc(-half, 0, r, Math.PI / 2, (3 * Math.PI) / 2, false);
    const geo = new THREE.ExtrudeGeometry(shape, { depth: 0.14, bevelEnabled: false, curveSegments: 24 });
    geo.rotateX(-Math.PI / 2); // lie flat: shape y -> world -z
    // Bend nose and tail up into kicktails.
    const pos = geo.attributes.position;
    for (let i = 0; i < pos.count; i++) {
      const x = pos.getX(i);
      const over = Math.abs(x) - KICK_START;
      if (over > 0) pos.setY(i, pos.getY(i) + over * KICK_SLOPE);
    }
    geo.computeVertexNormals();
    return geo;
  }

  function edges(geo: THREE.BufferGeometry, threshold = 30): number[] {
    return Array.from(new THREE.EdgesGeometry(geo, threshold).attributes.position.array as Float32Array);
  }

  // Solid parts (drawn in the background colour to hide back lines) + their outlines.
  function boardParts(): { solids: THREE.BufferGeometry[]; lines: number[] } {
    const solids: THREE.BufferGeometry[] = [deckGeometry()];
    const lines: number[] = [];
    for (const x of [-2.45, 2.45]) {
      solids.push(new THREE.BoxGeometry(0.7, 0.12, 0.6).translate(x, -0.06, 0));
      solids.push(new THREE.BoxGeometry(0.35, 0.28, 1.5).translate(x, -0.3, 0));
      lines.push(x, -0.42, -1.05, x, -0.42, 1.05); // axle
      for (const z of [-1.05, 1.05]) {
        solids.push(new THREE.CylinderGeometry(0.34, 0.34, 0.32, 28).rotateX(Math.PI / 2).translate(x, -0.42, z));
        solids.push(new THREE.CylinderGeometry(0.12, 0.12, 0.34, 16).rotateX(Math.PI / 2).translate(x, -0.42, z * 1.01));
      }
    }
    for (const geo of solids) lines.push(...edges(geo));
    return { solids, lines };
  }

  function mount(node: HTMLDivElement) {
    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    renderer.setPixelRatio(window.devicePixelRatio);
    node.appendChild(renderer.domElement);

    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(30, 1, 0.1, 100);
    camera.position.set(7.5, 4.2, 10.5);
    camera.lookAt(0, -0.3, 0);

    const { solids, lines } = boardParts();
    const geometry = new LineSegmentsGeometry().setPositions(lines);
    const material = new LineMaterial({ color: LINE_COLOR, linewidth: 3.2, worldUnits: false });
    const pivot = new THREE.Group();
    pivot.add(new LineSegments2(geometry, material));
    // Push the hiding faces back slightly so their own outlines stay visible.
    const hider = new THREE.MeshBasicMaterial({
      color: BG_COLOR, polygonOffset: true, polygonOffsetFactor: 1, polygonOffsetUnits: 1,
    });
    for (const solid of solids) pivot.add(new THREE.Mesh(solid, hider));
    scene.add(pivot);

    const resize = () => {
      const { clientWidth: w, clientHeight: h } = node;
      renderer.setSize(w, h);
      camera.aspect = w / h;
      camera.updateProjectionMatrix();
      material.resolution.set(w, h);
    };
    const observer = new ResizeObserver(resize);
    observer.observe(node);
    resize();

    let frame = 0;
    const clamp = (v: number) => THREE.MathUtils.clamp(v, -MAX_TILT, MAX_TILT);
    const render = () => {
      // Lean rolls the board about its long axis; pitch lifts nose/tail. Ease toward target.
      const targetRoll = THREE.MathUtils.degToRad(clamp(lean * LEAN_GAIN));
      const targetPitch = THREE.MathUtils.degToRad(clamp(pitch * PITCH_GAIN));
      pivot.rotation.x += (targetRoll - pivot.rotation.x) * 0.2;
      pivot.rotation.z += (targetPitch - pivot.rotation.z) * 0.2;
      renderer.render(scene, camera);
      frame = requestAnimationFrame(render);
    };
    // Read live tilt outside attachment tracking so it does not recreate WebGL.
    untrack(render);

    return () => {
      cancelAnimationFrame(frame);
      observer.disconnect();
      geometry.dispose();
      material.dispose();
      hider.dispose();
      solids.forEach((solid) => solid.dispose());
      renderer.dispose();
      renderer.domElement.remove();
    };
  }
</script>

<div class="board" {@attach mount}></div>

<style>
  .board {
    position: absolute;
    inset: 0;
  }
</style>
