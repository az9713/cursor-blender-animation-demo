'use strict';

import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';

const FLAVORS = {
  strawberry: { hex: 0xff7eb6, label: 'Strawberry blush' },
  blueberry: { hex: 0x6d8cff, label: 'Blueberry glaze' },
  matcha: { hex: 0x7dbe6a, label: 'Matcha drip' },
  chocolate: { hex: 0x6b3a2a, label: 'Bittersweet cocoa' }
};

function tintFrosting(root, hex) {
  root.traverse((obj) => {
    if (!obj.isMesh || !obj.material) return;
    const mats = Array.isArray(obj.material) ? obj.material : [obj.material];
    mats.forEach((m, idx) => {
      if (!m || !m.name || !m.name.startsWith('Frosting')) return;
      const c = m.clone();
      if (c.color) c.color.setHex(hex);
      if (Array.isArray(obj.material)) obj.material[idx] = c;
      else obj.material = c;
    });
  });
}

export async function bootViewer(canvas, opts = {}) {
  const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true });
  renderer.setPixelRatio(Math.min(devicePixelRatio || 1, 2));
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  const scene = new THREE.Scene();
  if (!opts.transparent) scene.background = new THREE.Color(opts.bg || 0x3a1424);
  const camera = new THREE.PerspectiveCamera(42, 1, 0.05, 40);
  camera.position.set(3.1, 1.8, 3.4);
  const controls = new OrbitControls(camera, canvas);
  controls.enableDamping = true;
  controls.target.set(0, 0.35, 0);
  scene.add(new THREE.HemisphereLight(0xffe4f0, 0x3a1424, 1.1));
  const key = new THREE.DirectionalLight(0xfff1e4, 1.35);
  key.position.set(4, 8, 3);
  scene.add(key);

  const gltf = await new GLTFLoader().loadAsync(opts.url || '../export/donut.glb');
  const root = gltf.scene;
  scene.add(root);
  const mixer = new THREE.AnimationMixer(root);
  const clips = gltf.animations || [];
  const actions = clips.map((c) => mixer.clipAction(c));
  actions.forEach((a) => {
    a.setLoop(THREE.LoopOnce, 1);
    a.clampWhenFinished = true;
  });

  let playing = false;
  let speed = 1;
  const clock = new THREE.Clock();

  function resize() {
    const w = canvas.clientWidth || canvas.parentElement.clientWidth;
    const h = canvas.clientHeight || canvas.parentElement.clientHeight || 480;
    renderer.setSize(w, h, false);
    camera.aspect = w / Math.max(1, h);
    camera.updateProjectionMatrix();
  }

  function play() {
    playing = true;
    mixer.setTime(0);
    mixer.update(0);
    actions.forEach((a) => {
      a.reset();
      a.paused = false;
      a.play();
    });
  }
  function pause() {
    playing = false;
    actions.forEach((a) => { a.paused = true; });
  }
  function setSpeed(v) {
    speed = v;
    mixer.timeScale = v;
  }
  function setProgress(t01) {
    playing = false;
    const dur = Math.max(...clips.map((c) => c.duration), 0.001);
    actions.forEach((a) => {
      a.enabled = true;
      a.reset();
      a.paused = false;
      a.play();
    });
    mixer.setTime(0);
    mixer.update(dur * Math.min(1, Math.max(0, t01)));
    actions.forEach((a) => { a.paused = true; });
    root.updateMatrixWorld(true);
  }
  function flavor(id) {
    const f = FLAVORS[id] || FLAVORS.strawberry;
    tintFrosting(root, f.hex);
    return f;
  }

  if (clips.length) setProgress(opts.start ?? 0.85);
  const box = new THREE.Box3();
  root.traverse((o) => {
    if (o.isMesh && (o.name === 'Donut' || o.name === 'Frosting' || o.name === 'Plate')) {
      box.expandByObject(o);
    }
  });
  if (box.isEmpty()) box.setFromObject(root);
  const size = box.getSize(new THREE.Vector3());
  const center = box.getCenter(new THREE.Vector3());
  const span = Math.max(size.x, size.y, size.z, 1);
  controls.target.copy(center);
  camera.position.set(center.x + span * 1.6, center.y + span * 1.05, center.z + span * 1.7);
  camera.near = Math.max(0.05, span * 0.02);
  camera.far = span * 30;
  camera.updateProjectionMatrix();

  function loop() {
    const dt = clock.getDelta();
    if (playing) mixer.update(dt);
    controls.update();
    resize();
    renderer.render(scene, camera);
    requestAnimationFrame(loop);
  }
  loop();
  flavor(opts.flavor || 'strawberry');
  if (opts.autoplay) play();

  return { play, pause, setSpeed, setProgress, flavor, clips, mixer, FLAVORS };
}

export { FLAVORS };
