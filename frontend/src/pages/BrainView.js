import React, { useState, useEffect, useCallback, useRef, useMemo, Suspense } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Canvas, useFrame, useThree } from '@react-three/fiber';
import { OrbitControls } from '@react-three/drei';
import * as THREE from 'three';
import {
  Brain, Zap, Eye, Target, Lightbulb, Cpu, ArrowRight,
  RefreshCw, Circle, Loader2, Waves, X
} from 'lucide-react';
import { Button } from '../components/ui/button';
import { getBrainState } from '../lib/api';

/* ─── Brain Region Definitions ─────────────────────────── */
const BRAIN_REGIONS = {
  goals:     { label: 'Goals',     color: '#06d6a0', icon: Target,     theta: -0.3, phi: 0.9,  r: 0.7,  desc: 'Current objectives & priorities' },
  reasoning: { label: 'Reasoning', color: '#118ab2', icon: Cpu,        theta: -0.8, phi: 1.2,  r: 0.65, desc: 'Active thought chains & decisions' },
  memory:    { label: 'Memory',    color: '#ffd166', icon: Lightbulb,  theta: 0.8,  phi: 1.2,  r: 0.65, desc: 'Stored knowledge & insights' },
  actions:   { label: 'Actions',   color: '#ef476f', icon: Zap,        theta: -0.6, phi: 1.8,  r: 0.6,  desc: 'Recent tool calls & executions' },
  learning:  { label: 'Learning',  color: '#7209b7', icon: Eye,        theta: 0.6,  phi: 1.8,  r: 0.6,  desc: 'New discoveries & observations' },
  planning:  { label: 'Planning',  color: '#f77f00', icon: ArrowRight, theta: 0.0,  phi: 2.2,  r: 0.55, desc: 'Upcoming tasks & strategies' },
};

/* ─── Helper: spherical to cartesian ───────────────────── */
function sphericalToCartesian(theta, phi, r) {
  return {
    x: r * Math.sin(phi) * Math.cos(theta),
    y: r * Math.cos(phi),
    z: r * Math.sin(phi) * Math.sin(theta),
  };
}

/* ─── Procedural brain-shape point cloud ───────────────── */
function generateBrainPoints(count) {
  const positions = new Float32Array(count * 3);
  const colors = new Float32Array(count * 3);
  const speeds = new Float32Array(count);
  const col = new THREE.Color();

  for (let i = 0; i < count; i++) {
    const u = Math.random() * Math.PI * 2;
    const v = Math.acos(2 * Math.random() - 1);

    // Brain-like ellipsoid with hemisphere bulges
    let rx = 0.85 + 0.15 * Math.sin(v);
    let ry = 0.9 + 0.1 * Math.sin(v * 2);
    let rz = 0.75 + 0.1 * Math.cos(v);

    // Central fissure indent along top midline
    const midlineDist = Math.abs(Math.sin(u));
    if (Math.cos(v) > 0.3) ry *= (0.85 + 0.15 * midlineDist);

    // Cortical fold wrinkles
    const folds = 0.04 * Math.sin(u * 8 + v * 6) + 0.03 * Math.cos(u * 5 - v * 9);

    // Volumetric fill — 70% near surface, 30% interior
    const fillR = Math.pow(Math.random(), 0.33);
    const surfaceBias = Math.random() > 0.3 ? 1.0 : fillR;

    positions[i * 3]     = (rx + folds) * Math.sin(v) * Math.cos(u) * surfaceBias;
    positions[i * 3 + 1] = (ry + folds) * Math.cos(v) * surfaceBias * 0.9;
    positions[i * 3 + 2] = (rz + folds) * Math.sin(v) * Math.sin(u) * surfaceBias;

    // Color: cool blue-purple gradient
    const t = (positions[i * 3 + 1] + 1) / 2;
    col.setHSL(0.55 + t * 0.15, 0.5, 0.55 + surfaceBias * 0.25);
    colors[i * 3]     = col.r;
    colors[i * 3 + 1] = col.g;
    colors[i * 3 + 2] = col.b;

    speeds[i] = 0.2 + Math.random() * 0.8;
  }

  return { positions, colors, speeds };
}

/* ─── Neural spark on curved path ──────────────────────── */
function NeuralSpark({ start, end, color, speed = 1, delay = 0 }) {
  const ref = useRef();
  const progress = useRef(delay);

  const curve = useMemo(() => {
    const mid = new THREE.Vector3().addVectors(start, end).multiplyScalar(0.5);
    mid.normalize().multiplyScalar(mid.length() * 1.3);
    return new THREE.QuadraticBezierCurve3(start, mid, end);
  }, [start, end]);

  useFrame((_, delta) => {
    if (!ref.current) return;
    progress.current += delta * speed * 0.3;
    if (progress.current > 1) progress.current = 0;
    const p = curve.getPoint(progress.current);
    ref.current.position.copy(p);
    ref.current.material.opacity = Math.sin(progress.current * Math.PI) * 0.9;
  });

  return (
    <mesh ref={ref}>
      <sphereGeometry args={[0.02, 8, 8]} />
      <meshBasicMaterial color={color} transparent opacity={0.5} />
    </mesh>
  );
}

/* ─── Particle Brain Mesh ──────────────────────────────── */
function ParticleBrain({ activeRegion }) {
  const pointsRef = useRef();
  const time = useRef(0);
  const COUNT = 18000;

  const { positions, colors, speeds } = useMemo(() => generateBrainPoints(COUNT), []);
  const origPositions = useMemo(() => new Float32Array(positions), [positions]);

  // Store base colors for reset
  const baseColors = useMemo(() => new Float32Array(colors), [colors]);

  useFrame((_, delta) => {
    if (!pointsRef.current) return;
    time.current += delta;
    const t = time.current;
    const posArr = pointsRef.current.geometry.attributes.position.array;
    const colArr = pointsRef.current.geometry.attributes.color.array;

    for (let i = 0; i < COUNT; i++) {
      const i3 = i * 3;
      const ox = origPositions[i3], oy = origPositions[i3 + 1], oz = origPositions[i3 + 2];
      const spd = speeds[i];

      // Organic breathing + subtle drift
      const breath = 1.0 + Math.sin(t * 0.4 + i * 0.01) * 0.015;
      posArr[i3]     = ox * breath + Math.sin(t * spd * 0.5 + i * 0.1) * 0.003;
      posArr[i3 + 1] = oy * breath + Math.sin(t * 0.3 + oz * 2) * 0.003;
      posArr[i3 + 2] = oz * breath + Math.cos(t * spd * 0.4 + ox * 2) * 0.003;

      // Reset color to base
      colArr[i3]     = baseColors[i3];
      colArr[i3 + 1] = baseColors[i3 + 1];
      colArr[i3 + 2] = baseColors[i3 + 2];

      // Highlight region zone
      if (activeRegion) {
        const reg = BRAIN_REGIONS[activeRegion];
        const rp = sphericalToCartesian(reg.theta, reg.phi, reg.r);
        const dx = posArr[i3] - rp.x, dy = posArr[i3 + 1] - rp.y, dz = posArr[i3 + 2] - rp.z;
        const dist = Math.sqrt(dx * dx + dy * dy + dz * dz);
        if (dist < 0.45) {
          const regCol = new THREE.Color(reg.color);
          const blend = Math.max(0, 1 - dist / 0.45) * 0.7;
          colArr[i3]     = THREE.MathUtils.lerp(colArr[i3], regCol.r, blend);
          colArr[i3 + 1] = THREE.MathUtils.lerp(colArr[i3 + 1], regCol.g, blend);
          colArr[i3 + 2] = THREE.MathUtils.lerp(colArr[i3 + 2], regCol.b, blend);
        }
      }
    }

    pointsRef.current.geometry.attributes.position.needsUpdate = true;
    pointsRef.current.geometry.attributes.color.needsUpdate = true;
  });

  return (
    <points ref={pointsRef}>
      <bufferGeometry>
        <bufferAttribute attach="attributes-position" count={COUNT} array={positions} itemSize={3} />
        <bufferAttribute attach="attributes-color" count={COUNT} array={colors} itemSize={3} />
      </bufferGeometry>
      <pointsMaterial
        size={0.012}
        vertexColors
        transparent
        opacity={0.85}
        sizeAttenuation
        blending={THREE.AdditiveBlending}
        depthWrite={false}
      />
    </points>
  );
}

/* ─── Region hotspot sphere (3D clickable) ─────────────── */
function RegionHotspot({ region, active, pulsing, itemCount, onClick }) {
  const meshRef = useRef();
  const glowRef = useRef();
  const pos = sphericalToCartesian(region.theta, region.phi, region.r);
  const col = useMemo(() => new THREE.Color(region.color), [region.color]);

  useFrame((state) => {
    if (!meshRef.current) return;
    const t = state.clock.elapsedTime;
    meshRef.current.scale.setScalar(active ? 1.4 : (pulsing ? 1.0 + Math.sin(t * 3) * 0.2 : 1.0));
    if (glowRef.current) {
      glowRef.current.scale.setScalar(1.0 + Math.sin(t * 2) * 0.3);
      glowRef.current.material.opacity = pulsing ? 0.2 + Math.sin(t * 3) * 0.1 : 0.08;
    }
  });

  return (
    <group position={[pos.x, pos.y, pos.z]}>
      <mesh ref={glowRef}>
        <sphereGeometry args={[0.08, 16, 16]} />
        <meshBasicMaterial color={col} transparent opacity={0.08} blending={THREE.AdditiveBlending} />
      </mesh>
      <mesh ref={meshRef} onClick={onClick}>
        <sphereGeometry args={[0.04, 16, 16]} />
        <meshBasicMaterial color={active ? col : col.clone().multiplyScalar(0.7)} transparent opacity={active ? 1 : 0.7} />
      </mesh>
      {itemCount > 0 && (
        <mesh position={[0.06, 0.06, 0]}>
          <sphereGeometry args={[0.018, 8, 8]} />
          <meshBasicMaterial color={col} />
        </mesh>
      )}
    </group>
  );
}

/* ─── Neural Pathways with sparks ──────────────────────── */
const CONNECTIONS = [
  ['goals', 'reasoning'], ['goals', 'memory'], ['reasoning', 'actions'],
  ['reasoning', 'memory'], ['memory', 'learning'], ['actions', 'planning'],
  ['learning', 'planning'], ['goals', 'planning'], ['reasoning', 'learning'],
];

function NeuralPathways({ activeRegion, pulsingRegions }) {
  return (
    <group>
      {CONNECTIONS.map(([from, to], i) => {
        const a = BRAIN_REGIONS[from], b = BRAIN_REGIONS[to];
        const posA = sphericalToCartesian(a.theta, a.phi, a.r);
        const posB = sphericalToCartesian(b.theta, b.phi, b.r);
        const isActive = activeRegion === from || activeRegion === to || pulsingRegions.includes(from) || pulsingRegions.includes(to);
        const lineColor = activeRegion === from ? a.color : activeRegion === to ? b.color : '#4a9eff';

        return (
          <group key={`p-${i}`}>
            <line>
              <bufferGeometry>
                <bufferAttribute
                  attach="attributes-position" count={2}
                  array={new Float32Array([posA.x, posA.y, posA.z, posB.x, posB.y, posB.z])}
                  itemSize={3}
                />
              </bufferGeometry>
              <lineBasicMaterial color={isActive ? lineColor : '#1a2a3a'} transparent opacity={isActive ? 0.4 : 0.08} blending={THREE.AdditiveBlending} />
            </line>
            {isActive && (
              <>
                <NeuralSpark start={new THREE.Vector3(posA.x, posA.y, posA.z)} end={new THREE.Vector3(posB.x, posB.y, posB.z)} color={lineColor} speed={1.5 + Math.random()} delay={i * 0.1} />
                <NeuralSpark start={new THREE.Vector3(posB.x, posB.y, posB.z)} end={new THREE.Vector3(posA.x, posA.y, posA.z)} color={lineColor} speed={1.2 + Math.random()} delay={i * 0.15 + 0.5} />
              </>
            )}
          </group>
        );
      })}
    </group>
  );
}

/* ─── Fresnel X-Ray shell (inspired by 3dbrain) ───────── */
function XRayShell() {
  const ref = useRef();

  const mat = useMemo(() => new THREE.ShaderMaterial({
    uniforms: {
      uTime: { value: 0 },
      uColor: { value: new THREE.Color('#1a6aff') },
      uOpacity: { value: 0.06 },
    },
    vertexShader: `
      varying vec3 vNormal;
      varying vec3 vViewDir;
      void main() {
        vNormal = normalize(normalMatrix * normal);
        vec4 mvPos = modelViewMatrix * vec4(position, 1.0);
        vViewDir = normalize(-mvPos.xyz);
        gl_Position = projectionMatrix * mvPos;
      }
    `,
    fragmentShader: `
      uniform float uTime;
      uniform vec3 uColor;
      uniform float uOpacity;
      varying vec3 vNormal;
      varying vec3 vViewDir;
      void main() {
        float fresnel = pow(1.0 - abs(dot(vNormal, vViewDir)), 3.0);
        vec3 col = uColor * fresnel * 1.5;
        float scanline = sin(vNormal.y * 40.0 + uTime * 2.0) * 0.5 + 0.5;
        gl_FragColor = vec4(col, fresnel * uOpacity * (0.6 + scanline * 0.4));
      }
    `,
    transparent: true,
    side: THREE.DoubleSide,
    depthWrite: false,
    blending: THREE.AdditiveBlending,
  }), []);

  useFrame((state) => {
    if (ref.current) mat.uniforms.uTime.value = state.clock.elapsedTime;
  });

  return (
    <mesh ref={ref} material={mat}>
      <sphereGeometry args={[1.05, 64, 64]} />
    </mesh>
  );
}

/* ─── Ambient floating dust ────────────────────────────── */
function AmbientParticles() {
  const ref = useRef();
  const COUNT = 500;

  const { positions, colors } = useMemo(() => {
    const p = new Float32Array(COUNT * 3);
    const c = new Float32Array(COUNT * 3);
    const col = new THREE.Color();
    for (let i = 0; i < COUNT; i++) {
      p[i * 3]     = (Math.random() - 0.5) * 6;
      p[i * 3 + 1] = (Math.random() - 0.5) * 6;
      p[i * 3 + 2] = (Math.random() - 0.5) * 6;
      col.setHSL(0.55 + Math.random() * 0.1, 0.4, 0.5);
      c[i * 3] = col.r; c[i * 3 + 1] = col.g; c[i * 3 + 2] = col.b;
    }
    return { positions: p, colors: c };
  }, []);

  useFrame((state) => {
    if (!ref.current) return;
    const t = state.clock.elapsedTime;
    const arr = ref.current.geometry.attributes.position.array;
    for (let i = 0; i < COUNT; i++) arr[i * 3 + 1] += Math.sin(t * 0.2 + i) * 0.0003;
    ref.current.geometry.attributes.position.needsUpdate = true;
  });

  return (
    <points ref={ref}>
      <bufferGeometry>
        <bufferAttribute attach="attributes-position" count={COUNT} array={positions} itemSize={3} />
        <bufferAttribute attach="attributes-color" count={COUNT} array={colors} itemSize={3} />
      </bufferGeometry>
      <pointsMaterial size={0.006} vertexColors transparent opacity={0.3} sizeAttenuation blending={THREE.AdditiveBlending} depthWrite={false} />
    </points>
  );
}

/* ─── Camera slow auto-orbit ───────────────────────────── */
function AutoRotate() {
  const { camera } = useThree();
  const angle = useRef(0);

  useFrame((_, delta) => {
    angle.current += delta * 0.08;
    const r = 3.0;
    camera.position.x = Math.sin(angle.current) * r;
    camera.position.z = Math.cos(angle.current) * r;
    camera.position.y = 0.3 + Math.sin(angle.current * 0.3) * 0.15;
    camera.lookAt(0, 0, 0);
  });

  return null;
}

/* ─── Full 3D Scene ────────────────────────────────────── */
function BrainScene({ activeRegion, setActiveRegion, regionData, pulsingRegions, isUserInteracting }) {
  return (
    <Canvas
      camera={{ position: [0, 0.2, 3.0], fov: 50, near: 0.1, far: 50 }}
      gl={{ antialias: true, alpha: true, powerPreference: 'high-performance' }}
      style={{ background: 'transparent' }}
      dpr={[1, 2]}
    >
      <Suspense fallback={null}>
        <ambientLight intensity={0.1} />
        <pointLight position={[5, 5, 5]} intensity={0.3} color="#4a9eff" />
        <pointLight position={[-5, -3, -5]} intensity={0.15} color="#7209b7" />

        {!isUserInteracting && <AutoRotate />}

        <OrbitControls
          enablePan={false}
          enableZoom
          minDistance={1.5}
          maxDistance={6}
          dampingFactor={0.05}
          rotateSpeed={0.4}
          zoomSpeed={0.5}
          makeDefault
        />

        <group>
          <ParticleBrain activeRegion={activeRegion} regionData={regionData} />
          <XRayShell />
          <NeuralPathways activeRegion={activeRegion} pulsingRegions={pulsingRegions} />
          {Object.entries(BRAIN_REGIONS).map(([key, region]) => (
            <RegionHotspot
              key={key}
              region={region}
              active={activeRegion === key}
              pulsing={pulsingRegions.includes(key)}
              itemCount={regionData[key]?.items?.length || 0}
              onClick={(e) => { e.stopPropagation(); setActiveRegion(activeRegion === key ? null : key); }}
            />
          ))}
        </group>

        <AmbientParticles />
      </Suspense>
    </Canvas>
  );
}

/* ═══════════════════════════════════════════════════════════
   2D UI OVERLAYS
   ═══════════════════════════════════════════════════════════ */

/* ─── Thought item ─────────────────────────────────────── */
function ThoughtItem({ item, index }) {
  const typeColors = {
    goal: '#06d6a0', action: '#ef476f', insight: '#ffd166',
    learning: '#7209b7', plan: '#f77f00', reasoning: '#118ab2',
    tool: '#ef476f', research: '#118ab2', synthesis: '#ffd166',
    check: '#06d6a0', automation: '#f77f00', assist: '#7209b7',
  };
  const color = typeColors[item.type] || '#4a9eff';

  return (
    <motion.div
      initial={{ opacity: 0, x: -12 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ delay: index * 0.04, duration: 0.3 }}
      className="flex gap-3 py-2.5 px-3 rounded-lg hover:bg-white/[0.03] transition-colors"
    >
      <div className="flex flex-col items-center gap-1 min-w-[3px]">
        <div className="w-1.5 h-1.5 rounded-full mt-2 shrink-0" style={{ background: color, boxShadow: `0 0 6px ${color}60` }} />
        <div className="w-[1px] flex-1 opacity-15" style={{ background: color }} />
      </div>
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 mb-0.5">
          <span className="text-[10px] font-mono uppercase tracking-widest opacity-60" style={{ color }}>{item.type}</span>
          <span className="text-[10px] font-mono text-white/25">{item.time}</span>
        </div>
        <p className="text-[13px] text-white/80 leading-relaxed">{item.content}</p>
        {item.details && <p className="text-[11px] text-white/30 mt-0.5">{item.details}</p>}
      </div>
    </motion.div>
  );
}

/* ─── Region detail overlay ────────────────────────────── */
function RegionPanel({ regionKey, data, onClose }) {
  const region = BRAIN_REGIONS[regionKey];
  if (!region || !data) return null;
  const Icon = region.icon;

  return (
    <motion.div
      initial={{ opacity: 0, y: 20, scale: 0.95 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      exit={{ opacity: 0, y: 10, scale: 0.95 }}
      className="absolute bottom-4 left-4 right-4 md:left-auto md:right-4 md:w-[380px] z-20"
    >
      <div className="bg-[#0a0e17]/90 backdrop-blur-2xl border border-white/[0.06] rounded-2xl p-5 shadow-2xl shadow-black/50">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-xl flex items-center justify-center" style={{ background: `${region.color}15`, border: `1px solid ${region.color}25` }}>
              <Icon size={16} style={{ color: region.color }} />
            </div>
            <div>
              <h3 className="text-sm font-semibold" style={{ color: region.color }}>{region.label}</h3>
              <p className="text-[11px] text-white/30">{region.desc}</p>
            </div>
          </div>
          <button onClick={onClose} className="w-7 h-7 rounded-lg flex items-center justify-center text-white/30 hover:text-white/60 hover:bg-white/5 transition-colors">
            <X size={14} />
          </button>
        </div>

        {data.summary && (
          <div className="mb-3 p-3 rounded-xl bg-white/[0.03] border border-white/[0.04]">
            <p className="text-[13px] text-white/70 leading-relaxed">{data.summary}</p>
          </div>
        )}

        <div className="space-y-0.5 max-h-[260px] overflow-y-auto pr-1" style={{ scrollbarWidth: 'thin', scrollbarColor: 'rgba(255,255,255,0.1) transparent' }}>
          {(data.items || []).map((item, i) => <ThoughtItem key={i} item={item} index={i} />)}
          {(!data.items || data.items.length === 0) && (
            <p className="text-[13px] text-white/20 italic py-6 text-center">No active thoughts in this region</p>
          )}
        </div>
      </div>
    </motion.div>
  );
}

/* ─── Stats HUD ────────────────────────────────────────── */
function StatsHUD({ stats }) {
  const items = [
    { label: 'TK', value: stats.ticks || 0, color: '#118ab2' },
    { label: 'AC', value: stats.autonomous_actions || 0, color: '#ef476f' },
    { label: 'ID', value: stats.ideas_generated || 0, color: '#ffd166' },
    { label: 'LN', value: stats.internet_learns || 0, color: '#7209b7' },
    { label: 'TL', value: stats.tool_actions || 0, color: '#f77f00' },
    { label: 'GL', value: stats.goals_set || 0, color: '#06d6a0' },
  ];

  return (
    <div className="flex gap-0.5">
      {items.map((item) => (
        <div key={item.label} className="flex items-center gap-1 px-1.5 py-0.5">
          <span className="text-xs font-bold font-mono" style={{ color: item.color }}>{item.value}</span>
          <span className="text-[8px] uppercase tracking-wider text-white/25">{item.label}</span>
        </div>
      ))}
    </div>
  );
}

/* ─── Region legend (left sidebar) ─────────────────────── */
function RegionLegend({ activeRegion, setActiveRegion, regionData, pulsingRegions }) {
  return (
    <div className="flex flex-col gap-1">
      {Object.entries(BRAIN_REGIONS).map(([key, region]) => {
        const Icon = region.icon;
        const isActive = activeRegion === key;
        const isPulsing = pulsingRegions.includes(key);
        const count = regionData[key]?.items?.length || 0;

        return (
          <motion.button
            key={key}
            onClick={() => setActiveRegion(isActive ? null : key)}
            className={`flex items-center gap-2.5 px-3 py-2 rounded-xl text-left transition-all border ${isActive ? 'bg-white/[0.06] border-white/[0.08]' : 'hover:bg-white/[0.03] border-transparent'}`}
            whileHover={{ x: 2 }}
          >
            <div className="relative">
              <div className="w-7 h-7 rounded-lg flex items-center justify-center" style={{ background: `${region.color}${isActive ? '25' : '10'}` }}>
                <Icon size={13} style={{ color: region.color }} />
              </div>
              {isPulsing && (
                <motion.div
                  className="absolute -top-0.5 -right-0.5 w-2 h-2 rounded-full"
                  style={{ background: region.color }}
                  animate={{ scale: [1, 1.5, 1], opacity: [1, 0.4, 1] }}
                  transition={{ duration: 1.5, repeat: Infinity }}
                />
              )}
            </div>
            <span className={`text-xs font-medium flex-1 ${isActive ? 'text-white/90' : 'text-white/50'}`}>{region.label}</span>
            {count > 0 && (
              <span className="text-[10px] font-mono font-bold px-1.5 py-0.5 rounded-md" style={{ background: `${region.color}15`, color: region.color }}>{count}</span>
            )}
          </motion.button>
        );
      })}
    </div>
  );
}

/* ─── Thought Stream panel ─────────────────────────────── */
function ThoughtStreamPanel({ thoughts }) {
  const ref = useRef(null);
  useEffect(() => { if (ref.current) ref.current.scrollTop = 0; }, [thoughts]);

  return (
    <div className="bg-[#0a0e17]/70 backdrop-blur-2xl border border-white/[0.06] rounded-2xl overflow-hidden h-full flex flex-col">
      <div className="px-4 py-3 border-b border-white/[0.04] flex items-center gap-2">
        <Waves size={14} className="text-[#4a9eff]" />
        <span className="text-xs font-semibold tracking-wide text-white/60">Thought Stream</span>
        <motion.div animate={{ opacity: [0.3, 1, 0.3] }} transition={{ duration: 2, repeat: Infinity }} className="ml-auto">
          <Circle size={5} className="fill-[#4a9eff] text-[#4a9eff]" />
        </motion.div>
      </div>
      <div ref={ref} className="flex-1 overflow-y-auto p-2" style={{ scrollbarWidth: 'thin', scrollbarColor: 'rgba(255,255,255,0.06) transparent' }}>
        {thoughts.map((item, i) => <ThoughtItem key={`${item.time}-${i}`} item={item} index={i} />)}
        {thoughts.length === 0 && (
          <div className="flex flex-col items-center justify-center py-16 opacity-30">
            <Brain size={28} className="mb-2 text-white/40" />
            <p className="text-xs text-white/30">Waiting for thoughts…</p>
          </div>
        )}
      </div>
    </div>
  );
}

/* ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
   MAIN PAGE COMPONENT
   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ */
export default function BrainView() {
  const [brainData, setBrainData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [activeRegion, setActiveRegion] = useState(null);
  const [pulsingRegions, setPulsingRegions] = useState([]);
  const [autoRefresh, setAutoRefresh] = useState(true);
  const [isUserInteracting, setIsUserInteracting] = useState(false);
  const interactionTimer = useRef(null);
  const intervalRef = useRef(null);

  const fetchData = useCallback(async () => {
    try {
      const data = await getBrainState();
      setBrainData(data);
      const active = [];
      Object.entries(data.regions || {}).forEach(([key, region]) => {
        if (region.items?.length > 0 && region.items[0]?.age_seconds < 120) active.push(key);
      });
      setPulsingRegions(active);
    } catch (e) {
      console.error('Brain state fetch failed:', e);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchData(); }, [fetchData]);
  useEffect(() => {
    if (autoRefresh) intervalRef.current = setInterval(fetchData, 15000);
    return () => { if (intervalRef.current) clearInterval(intervalRef.current); };
  }, [autoRefresh, fetchData]);

  const handleMouseDown = useCallback(() => {
    setIsUserInteracting(true);
    if (interactionTimer.current) clearTimeout(interactionTimer.current);
  }, []);

  const handleMouseUp = useCallback(() => {
    if (interactionTimer.current) clearTimeout(interactionTimer.current);
    interactionTimer.current = setTimeout(() => setIsUserInteracting(false), 4000);
  }, []);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-[calc(100vh-5rem)] bg-[#060a10]">
        <motion.div animate={{ rotate: 360 }} transition={{ duration: 3, repeat: Infinity, ease: 'linear' }}>
          <Brain size={48} className="text-[#4a9eff]/30" />
        </motion.div>
      </div>
    );
  }

  const regionData = brainData?.regions || {};
  const thoughts = brainData?.thought_stream || [];
  const stats = brainData?.stats || {};
  const currentGoals = brainData?.current_goals || [];

  return (
    <div className="h-[calc(100vh-5rem)] flex flex-col bg-[#060a10] relative overflow-hidden">
      {/* Full-screen 3D Canvas */}
      <div className="absolute inset-0" onMouseDown={handleMouseDown} onMouseUp={handleMouseUp} onTouchStart={handleMouseDown} onTouchEnd={handleMouseUp}>
        <BrainScene activeRegion={activeRegion} setActiveRegion={setActiveRegion} regionData={regionData} pulsingRegions={pulsingRegions} isUserInteracting={isUserInteracting} />
      </div>

      {/* Gradient overlays — subtle, don't occlude brain */}
      <div className="absolute inset-x-0 top-0 h-16 bg-gradient-to-b from-[#060a10]/70 to-transparent pointer-events-none z-10" />
      <div className="absolute inset-x-0 bottom-0 h-20 bg-gradient-to-t from-[#060a10]/60 to-transparent pointer-events-none z-10" />

      {/* Top HUD — compact, no stats, just title + controls */}
      <div className="absolute top-0 inset-x-0 z-20 px-4 py-3 md:px-6 flex items-center justify-between pointer-events-none">
        <div className="pointer-events-auto flex items-center gap-2.5">
          <div className="relative">
            <Brain size={20} className="text-[#4a9eff]" />
            <motion.div className="absolute -top-0.5 -right-0.5 w-1.5 h-1.5 rounded-full bg-[#4a9eff]" animate={{ scale: [1, 1.5, 1], opacity: [1, 0.4, 1] }} transition={{ duration: 2, repeat: Infinity }} />
          </div>
          <div>
            <h1 className="text-sm font-bold tracking-tight text-white/80">Ombra's Mind</h1>
            <p className="text-[9px] text-white/20 tracking-wide">click regions to inspect</p>
          </div>
        </div>

        <div className="pointer-events-auto flex items-center gap-1.5">
          <Button variant="ghost" size="sm" onClick={() => setAutoRefresh(!autoRefresh)} className={`h-7 px-2 ${autoRefresh ? 'text-[#4a9eff]' : 'text-white/30'} hover:bg-white/5 border border-white/[0.06] rounded-lg`}>
            {autoRefresh ? <Loader2 size={12} className="animate-spin mr-1" /> : <Circle size={12} className="mr-1" />}
            <span className="text-[10px]">{autoRefresh ? 'Live' : 'Paused'}</span>
          </Button>
          <Button variant="ghost" size="sm" onClick={fetchData} className="h-7 w-7 p-0 text-white/30 hover:text-white/60 hover:bg-white/5 border border-white/[0.06] rounded-lg">
            <RefreshCw size={12} />
          </Button>
        </div>
      </div>

      {/* Bottom stats bar — compact row */}
      <div className="absolute bottom-3 left-1/2 -translate-x-1/2 z-20 pointer-events-none hidden md:flex">
        <div className="pointer-events-auto flex gap-1 bg-[#0a0e17]/60 backdrop-blur-2xl border border-white/[0.04] rounded-xl px-2 py-1.5">
          <StatsHUD stats={stats} />
          {currentGoals.length > 0 && (
            <>
              <div className="w-px bg-white/[0.06] mx-1" />
              <div className="flex items-center gap-1.5 max-w-[300px] overflow-hidden">
                <Target size={10} className="text-[#06d6a0] shrink-0" />
                {currentGoals.slice(0, 3).map((goal, i) => (
                  <span key={i} className="text-[9px] text-white/40 bg-[#06d6a0]/8 border border-[#06d6a0]/10 rounded px-1.5 py-0.5 truncate max-w-[90px]" title={goal}>{goal}</span>
                ))}
              </div>
            </>
          )}
        </div>
      </div>

      {/* Left: Region Legend — vertically centered, compact */}
      <div className="absolute left-3 top-1/2 -translate-y-1/2 z-20 hidden md:block">
        <div className="bg-[#0a0e17]/50 backdrop-blur-2xl border border-white/[0.04] rounded-2xl p-1.5">
          <RegionLegend activeRegion={activeRegion} setActiveRegion={setActiveRegion} regionData={regionData} pulsingRegions={pulsingRegions} />
        </div>
      </div>

      {/* Right: Thought Stream */}
      <div className="absolute right-3 top-14 bottom-4 w-[260px] z-20 hidden lg:block">
        <ThoughtStreamPanel thoughts={thoughts} />
      </div>

      {/* Region detail panel */}
      <AnimatePresence mode="wait">
        {activeRegion && <RegionPanel key={activeRegion} regionKey={activeRegion} data={regionData[activeRegion]} onClose={() => setActiveRegion(null)} />}
      </AnimatePresence>

      {/* Mobile bottom region bar */}
      <div className="md:hidden absolute bottom-0 inset-x-0 z-20 p-3">
        <div className="flex gap-1.5 overflow-x-auto pb-2" style={{ scrollbarWidth: 'none' }}>
          {Object.entries(BRAIN_REGIONS).map(([key, region]) => {
            const Icon = region.icon;
            return (
              <button key={key} onClick={() => setActiveRegion(activeRegion === key ? null : key)} className={`flex items-center gap-1.5 px-3 py-2 rounded-xl whitespace-nowrap text-xs transition-all border backdrop-blur-xl ${activeRegion === key ? 'bg-white/[0.08] border-white/10' : 'bg-[#0a0e17]/70 border-white/[0.04]'}`}>
                <Icon size={12} style={{ color: region.color }} />
                <span className="text-white/50">{region.label}</span>
              </button>
            );
          })}
        </div>
      </div>
    </div>
  );
}
