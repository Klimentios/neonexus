// Adapted from AI Mirror's MIT-licensed particle face geometry.
// Source: https://github.com/yusufk/ai_mirror (license copied to static/ai-mirror.LICENSE.md)
import * as THREE from 'three';
import { FaceGeometry } from './hologram-face-geometry.js';

const host = document.getElementById('sidebar-agent-signal');
const mount = host?.querySelector('.hologram-canvas');
if (host && mount && window.WebGLRenderingContext) {
  try {
    const reduced = window.matchMedia('(prefers-reduced-motion: reduce)');
    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(50, 1, 1, 2500);
    camera.position.z = 850;
    const renderer = new THREE.WebGLRenderer({ alpha: true, antialias: true, powerPreference: 'low-power' });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
    renderer.setClearColor(0x000000, 0);
    mount.appendChild(renderer.domElement);

    const count = 1900;
    const { positions } = FaceGeometry.generate(count);
    const geometry = new THREE.BufferGeometry();
    geometry.setAttribute('position', new THREE.BufferAttribute(positions, 3));
    const random = new Float32Array(count);
    for (let i = 0; i < count; i++) random[i] = Math.random();
    geometry.setAttribute('aRandom', new THREE.BufferAttribute(random, 1));
    const material = new THREE.ShaderMaterial({
      transparent: true, depthWrite: false, blending: THREE.AdditiveBlending,
      uniforms: { uTime: { value: 0 }, uSpeaking: { value: 0 }, uThinking: { value: 0 } },
      vertexShader: `
        attribute float aRandom;
        uniform float uTime;
        uniform float uSpeaking;
        uniform float uThinking;
        varying float vAlpha;
        varying float vHeight;
        varying float vRandom;
        void main() {
          vec3 p = position;
          p.z += sin(uTime * 1.1 + aRandom * 32.0) * (2.0 + uThinking * 2.0);
          vec4 mv = modelViewMatrix * vec4(p, 1.0);
          gl_Position = projectionMatrix * mv;
          gl_PointSize = clamp((2.2 + uSpeaking * 1.0 + aRandom * 0.8) * (850.0 / -mv.z), 1.0, 4.5);
          vAlpha = 0.72 + 0.24 * sin(uTime * 1.3 + aRandom * 29.0);
          vHeight = p.y;
          vRandom = aRandom;
        }`,
      fragmentShader: `
        varying float vAlpha;
        varying float vHeight;
        varying float vRandom;
        uniform float uSpeaking;
        void main() {
          float d = length(gl_PointCoord - vec2(0.5));
          if (d > 0.5) discard;
          float edge = 1.0 - smoothstep(0.26, 0.5, d);
          vec3 cyan = vec3(0.43, 0.97, 0.93);
          vec3 white = vec3(0.91, 1.0, 0.98);
          vec3 accent = vec3(1.0, 0.33, 0.52);
          vec3 color = mix(cyan, white, smoothstep(-170.0, 150.0, vHeight) * 0.6);
          color = mix(color, accent, step(0.955, vRandom) * 0.8);
          color = mix(color, vec3(1.0, 0.92, 0.28), uSpeaking * 0.45);
          gl_FragColor = vec4(color, edge * vAlpha);
        }`,
    });
    const face = new THREE.Points(geometry, material);
    scene.add(face);
    let pointerX = 0;
    let pointerY = 0;
    let visible = true;
    let frame = 0;
    const resize = () => {
      const width = Math.max(1, mount.clientWidth);
      const height = Math.max(1, mount.clientHeight);
      renderer.setSize(width, height, false);
      camera.aspect = width / height;
      camera.updateProjectionMatrix();
      renderer.render(scene, camera);
    };
    new ResizeObserver(resize).observe(mount);
    resize();
    host.classList.add('webgl-ready');
    document.addEventListener('pointermove', event => {
      if (event.pointerType === 'touch') return;
      pointerX = (event.clientX / window.innerWidth - 0.5) * 2;
      pointerY = (event.clientY / window.innerHeight - 0.5) * 2;
    }, { passive: true });
    new IntersectionObserver(entries => { visible = entries[0]?.isIntersecting ?? false; }, { threshold: 0 }).observe(host);
    const tick = now => {
      frame = requestAnimationFrame(tick);
      if (!visible || document.hidden) return;
      const motion = reduced.matches ? 0 : 1;
      const t = now / 1000;
      face.rotation.y += ((pointerX * 0.42 * motion + Math.sin(t * 0.45) * 0.025 * motion) - face.rotation.y) * 0.07;
      face.rotation.x += ((-pointerY * 0.25 * motion + Math.sin(t * 0.6) * 0.015 * motion) - face.rotation.x) * 0.07;
      material.uniforms.uTime.value = t * motion;
      material.uniforms.uSpeaking.value += ((host.classList.contains('speaking') ? 1 : 0) - material.uniforms.uSpeaking.value) * 0.14;
      material.uniforms.uThinking.value += ((host.classList.contains('thinking') ? 1 : 0) - material.uniforms.uThinking.value) * 0.1;
      renderer.render(scene, camera);
    };
    frame = requestAnimationFrame(tick);
    window.addEventListener('pagehide', () => cancelAnimationFrame(frame), { once: true });
  } catch (error) {
    // The existing SVG remains visible if WebGL is unavailable.
    console.warn('Hologram renderer unavailable:', error);
  }
}
