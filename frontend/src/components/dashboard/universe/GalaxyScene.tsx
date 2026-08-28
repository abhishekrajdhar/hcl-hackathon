"use client";

// The WebGL half of the Learning Universe.
//
// Everything drawn here is read off the GalaxyLayout — the scene holds no
// state of its own beyond the camera. Mastery is the visual language:
//
//   mastered  → amber, warm and fully lit
//   learning  → cyan, energised, with charge moving through it
//   weak      → coral, dim, a slow attention pulse
//   locked    → steel in fog: dark, translucent, waiting to be discovered
//
// Goal skills are landmarks — larger, ringed, brighter. Selecting a node
// illuminates its full prerequisite chain, dims everything else, and eases the
// camera toward it.

import { useMemo, useRef, useState } from "react";
import { Canvas, useFrame, useThree } from "@react-three/fiber";
import { Html, Line, OrbitControls, Stars } from "@react-three/drei";
import * as THREE from "three";
import type { OrbitControls as OrbitControlsImpl } from "three-stdlib";
import type { GraphModel } from "@/lib/graph-view";
import { transitive } from "@/lib/graph-view";
import { layoutGalaxy, type GalaxyNode } from "@/lib/universe-layout";

// Hex twins of the CSS state tokens — WebGL cannot read CSS variables.
const STATE_HEX = {
  mastered: "#ffb84a",
  learning: "#29e6d1",
  weak: "#ff6b6b",
  not_started: "#607080",
} as const;
const CYAN = "#29e6d1";
const TEAL = "#0f8f87";
const EDGE_IDLE = "#1e2830";
const VOID = "#070a0d";

export interface GalaxySceneProps {
  model: GraphModel;
  selectedId: string | null;
  onSelect: (id: string | null) => void;
  /** Node ids the AI coach just mentioned — rendered with a pulse. */
  pulseIds: Set<string>;
  /**
   * Camera proximity multiplier. 1 (default) frames the whole graph with
   * headroom — right for the interactive dashboard. The landing hero passes
   * >1 to sit closer, so the stars read at a glance in a half-width panel.
   */
  zoom?: number;
}

export function GalaxyScene({ model, selectedId, onSelect, pulseIds, zoom = 1 }: GalaxySceneProps) {
  const layout = useMemo(() => layoutGalaxy(model), [model]);

  const focus = useMemo(() => {
    if (!selectedId) return null;
    return {
      ancestors: transitive(selectedId, model, "up"),
      descendants: transitive(selectedId, model, "down"),
    };
  }, [selectedId, model]);

  const lit = (id: string) =>
    !focus || id === selectedId || focus.ancestors.has(id) || focus.descendants.has(id);

  const mid = layout.height / 2;
  const cameraDistance = Math.max(11, layout.spread * 2.4 + layout.height * 0.5) / zoom;

  if (!layout.nodes.length) {
    return (
      <div className="grid h-full place-items-center">
        <p className="label-meta">No skills charted yet — set a goal to generate your universe.</p>
      </div>
    );
  }

  return (
    <Canvas
      camera={{ position: [cameraDistance * 0.5, mid + 3, cameraDistance], fov: 42 }}
      dpr={[1, 2]}
      gl={{ antialias: true }}
      onPointerMissed={() => onSelect(null)}
      // The world is committed to space in both app themes.
      style={{
        background:
          "radial-gradient(ellipse 70% 60% at 50% 30%, #0e1620 0%, #080c11 55%, #05070a 100%)",
      }}
    >
      {/* Depth cue: distant geometry fades into the void rather than popping. */}
      <fog attach="fog" args={[VOID, cameraDistance * 0.9, cameraDistance * 2.8]} />

      {/* Cinematic three-point-ish rig: cool key from above, teal fill from
          below, faint rim so silhouettes separate from the background. */}
      <ambientLight intensity={0.35} />
      <pointLight position={[6, layout.height + 8, 6]} intensity={260} color="#bff6ef" distance={80} />
      <pointLight position={[-9, -3, -7]} intensity={110} color={TEAL} distance={70} />
      <pointLight position={[0, mid, -14]} intensity={70} color={CYAN} distance={60} />

      <Stars radius={90} depth={55} count={1400} factor={2.6} saturation={0} fade speed={0.25} />
      <Dust count={90} spread={26} />

      <group position={[0, -mid, 0]}>
        <EnergyEdges layout={layout} focus={focus} selectedId={selectedId} lit={lit} />
        {layout.nodes.map((n) => (
          <SkillBody
            key={n.id}
            node={n}
            selected={n.id === selectedId}
            dimmed={focus != null && !lit(n.id)}
            pulsing={pulseIds.has(n.id)}
            onSelect={onSelect}
          />
        ))}
      </group>

      <CameraRig
        target={selectedId ? layout.byId.get(selectedId) ?? null : null}
        home={[0, 0, 0]}
        midY={mid}
      />
      <OrbitControls
        makeDefault
        enablePan={false}
        enableDamping
        dampingFactor={0.06}
        rotateSpeed={0.5}
        zoomSpeed={0.6}
        minDistance={5}
        maxDistance={cameraDistance * 1.9}
        autoRotate
        autoRotateSpeed={0.32}
      />
    </Canvas>
  );
}

/* -------------------------------------------------------------------------
   Edges — prerequisite paths that carry charge
   ---------------------------------------------------------------------- */

/**
 * Each edge is drawn twice: a quiet base line that is always there, and — when
 * the edge is part of the selected chain — a particle travelling along it in
 * the direction of learning (prerequisite → dependent).
 */
function EnergyEdges({
  layout,
  focus,
  selectedId,
  lit,
}: {
  layout: ReturnType<typeof layoutGalaxy>;
  focus: { ancestors: Set<string>; descendants: Set<string> } | null;
  selectedId: string | null;
  lit: (id: string) => boolean;
}) {
  return (
    <group>
      {layout.edges.map((e) => {
        const onChain =
          focus != null &&
          (e.prerequisiteId === selectedId ||
            e.dependentId === selectedId ||
            (lit(e.prerequisiteId) && lit(e.dependentId)));
        const hard = e.kind === "hard_prerequisite";
        const dimmed = focus != null && !onChain;

        return (
          <group key={`${e.prerequisiteId}->${e.dependentId}`}>
            <Line
              points={[e.from, e.to]}
              color={onChain ? CYAN : EDGE_IDLE}
              lineWidth={onChain ? 1.6 : 1}
              dashed={!hard}
              dashSize={0.16}
              gapSize={0.12}
              transparent
              opacity={dimmed ? 0.06 : onChain ? 0.9 : hard ? 0.4 : 0.22}
            />
            {onChain && <Charge from={e.from} to={e.to} />}
          </group>
        );
      })}
    </group>
  );
}

/** A packet of charge running prerequisite → dependent. */
function Charge({ from, to }: { from: [number, number, number]; to: [number, number, number] }) {
  const ref = useRef<THREE.Mesh>(null);
  const a = useMemo(() => new THREE.Vector3(...from), [from]);
  const b = useMemo(() => new THREE.Vector3(...to), [to]);
  // Offset by position so several packets on one chain do not move in lockstep.
  const phase = useMemo(() => Math.abs(a.x * 3.7 + a.z * 1.3) % 1, [a]);

  useFrame((state) => {
    if (!ref.current) return;
    const t = (state.clock.elapsedTime * 0.45 + phase) % 1;
    ref.current.position.lerpVectors(a, b, t);
    // Fade in and out at the ends so packets do not blink into existence.
    const fade = Math.sin(t * Math.PI);
    const material = ref.current.material as THREE.MeshBasicMaterial;
    material.opacity = fade * 0.95;
    ref.current.scale.setScalar(0.6 + fade * 0.6);
  });

  return (
    <mesh ref={ref}>
      <sphereGeometry args={[0.055, 10, 10]} />
      <meshBasicMaterial color="#d8fffa" transparent opacity={0} toneMapped={false} />
    </mesh>
  );
}

/* -------------------------------------------------------------------------
   Nodes — small structures rather than plain spheres
   ---------------------------------------------------------------------- */

function SkillBody({
  node,
  selected,
  dimmed,
  pulsing,
  onSelect,
}: {
  node: GalaxyNode;
  selected: boolean;
  dimmed: boolean;
  pulsing: boolean;
  onSelect: (id: string) => void;
}) {
  const group = useRef<THREE.Group>(null);
  const core = useRef<THREE.Mesh>(null);
  const ring = useRef<THREE.Mesh>(null);
  const [hovered, setHovered] = useState(false);

  const inFog = node.state === "not_started";
  const color = STATE_HEX[node.state];
  const emphasised = selected || hovered || pulsing;

  // Each body drifts on its own phase, so the field breathes instead of
  // pulsing as one object.
  const phase = useMemo(() => (node.position[0] * 1.7 + node.position[2] * 0.9) % (Math.PI * 2), [node.position]);

  useFrame((state) => {
    const t = state.clock.elapsedTime;
    if (group.current) {
      group.current.position.y = node.position[1] + Math.sin(t * 0.55 + phase) * 0.075;
    }
    if (core.current) {
      const beat = emphasised ? 1 + Math.sin(t * 3.4) * 0.07 : 1;
      core.current.scale.setScalar(beat);
      core.current.rotation.y = t * 0.12 + phase;
    }
    // Goal skills carry an orbital ring; it turns slowly and tips as it goes.
    if (ring.current) {
      ring.current.rotation.z = t * 0.28 + phase;
      ring.current.rotation.x = Math.PI / 2.4 + Math.sin(t * 0.3 + phase) * 0.12;
    }
  });

  const emissive = dimmed ? 0.04 : inFog ? 0.1 : emphasised ? 1.35 : 0.6;
  const opacity = dimmed ? 0.12 : inFog ? 0.42 : 1;

  return (
    <group ref={group} position={node.position}>
      {/* Core body. An icosahedron reads as a constructed object at this size
          while still silhouetting like a planet. */}
      <mesh
        ref={core}
        onClick={(e) => {
          e.stopPropagation();
          onSelect(node.id);
        }}
        onPointerOver={(e) => {
          e.stopPropagation();
          setHovered(true);
          document.body.style.cursor = "pointer";
        }}
        onPointerOut={() => {
          setHovered(false);
          document.body.style.cursor = "";
        }}
      >
        <icosahedronGeometry args={[node.radius, 1]} />
        <meshStandardMaterial
          color={color}
          emissive={color}
          emissiveIntensity={emissive}
          transparent
          opacity={opacity}
          roughness={0.42}
          metalness={0.25}
          flatShading
        />
      </mesh>

      {/* Atmosphere: a larger back-facing shell gives the body a rim of light
          instead of a flat billboard glow. */}
      {!dimmed && !inFog && (
        <mesh scale={emphasised ? 1.9 : 1.55}>
          <sphereGeometry args={[node.radius, 20, 20]} />
          <meshBasicMaterial
            color={color}
            transparent
            opacity={emphasised ? 0.16 : 0.07}
            side={THREE.BackSide}
            depthWrite={false}
            toneMapped={false}
          />
        </mesh>
      )}

      {/* Goal skills are landmarks. */}
      {node.isTarget && (
        <mesh ref={ring}>
          <torusGeometry args={[node.radius + 0.26, 0.014, 8, 64]} />
          <meshBasicMaterial
            color={node.state === "mastered" ? STATE_HEX.mastered : CYAN}
            transparent
            opacity={dimmed ? 0.08 : 0.75}
            toneMapped={false}
          />
        </mesh>
      )}

      {/* Selection cage — a wireframe shell, closer to a targeting reticle
          than to a halo. */}
      {selected && (
        <mesh scale={2.15}>
          <icosahedronGeometry args={[node.radius, 0]} />
          <meshBasicMaterial color={CYAN} wireframe transparent opacity={0.3} toneMapped={false} />
        </mesh>
      )}

      <NodeLabel node={node} dimmed={dimmed} emphasised={emphasised} inFog={inFog} color={color} />
    </group>
  );
}

/** HTML label. Kept minimal — the colour already carries the state. */
function NodeLabel({
  node,
  dimmed,
  emphasised,
  inFog,
  color,
}: {
  node: GalaxyNode;
  dimmed: boolean;
  emphasised: boolean;
  inFog: boolean;
  color: string;
}) {
  return (
    <Html
      center
      distanceFactor={12}
      position={[0, node.radius + 0.5, 0]}
      style={{ pointerEvents: "none", transition: "opacity 220ms ease" }}
      zIndexRange={[10, 0]}
    >
      <div
        style={{
          opacity: dimmed ? 0.12 : inFog && !emphasised ? 0.4 : 1,
          textAlign: "center",
          whiteSpace: "nowrap",
          fontFamily: "var(--font-display), system-ui, sans-serif",
        }}
      >
        <div
          style={{
            color: emphasised ? color : "#f4f7f7",
            fontSize: 11,
            fontWeight: emphasised ? 600 : 500,
            letterSpacing: "0.01em",
            textShadow: "0 1px 10px rgba(0,0,0,0.95)",
          }}
        >
          {node.name}
        </div>
        {node.proficiency != null && (
          <div
            style={{
              color: "#9aa8b2",
              fontSize: 9,
              letterSpacing: "0.14em",
              marginTop: 2,
              fontVariantNumeric: "tabular-nums",
            }}
          >
            {Math.round(node.proficiency * 100)}%
          </div>
        )}
      </div>
    </Html>
  );
}

/* -------------------------------------------------------------------------
   Atmosphere and camera
   ---------------------------------------------------------------------- */

/** Slow motes of dust, for parallax and a sense of volume. */
function Dust({ count, spread }: { count: number; spread: number }) {
  const points = useRef<THREE.Points>(null);
  const positions = useMemo(() => {
    // Deterministic placement: a hash rather than Math.random, so the field is
    // identical across renders and reloads.
    const arr = new Float32Array(count * 3);
    for (let i = 0; i < count; i++) {
      const h = (n: number) => ((Math.sin(i * 12.9898 + n * 78.233) * 43758.5453) % 1 + 1) % 1;
      arr[i * 3] = (h(1) - 0.5) * spread;
      arr[i * 3 + 1] = (h(2) - 0.5) * spread;
      arr[i * 3 + 2] = (h(3) - 0.5) * spread;
    }
    return arr;
  }, [count, spread]);

  useFrame((state) => {
    if (points.current) points.current.rotation.y = state.clock.elapsedTime * 0.014;
  });

  return (
    <points ref={points}>
      <bufferGeometry>
        <bufferAttribute attach="attributes-position" args={[positions, 3]} />
      </bufferGeometry>
      <pointsMaterial
        size={0.045}
        color={TEAL}
        transparent
        opacity={0.5}
        sizeAttenuation
        depthWrite={false}
      />
    </points>
  );
}

/**
 * Cinematic focus. Selecting a node eases BOTH the orbit target and the camera
 * itself toward that node — the shot travels rather than cutting. Damping is
 * frame-rate independent so the move feels identical on a 60Hz and a 120Hz
 * display.
 */
function CameraRig({
  target,
  midY,
}: {
  target: GalaxyNode | null;
  home: [number, number, number];
  midY: number;
}) {
  const { camera } = useThree();
  const desiredTarget = useRef(new THREE.Vector3());
  const desiredPos = useRef(new THREE.Vector3());

  useFrame((state, delta) => {
    const controls = state.controls as OrbitControlsImpl | null;
    if (!controls) return;

    if (target) {
      // Group space is offset by -midY; match it so the reticle lands on the node.
      desiredTarget.current.set(target.position[0], target.position[1] - midY, target.position[2]);
      // Approach along the camera's current bearing, so selecting a node never
      // spins the world round behind the learner's back.
      const bearing = camera.position.clone().sub(controls.target).normalize();
      const distance = THREE.MathUtils.clamp(camera.position.distanceTo(controls.target), 6, 11);
      desiredPos.current.copy(desiredTarget.current).addScaledVector(bearing, distance);
    } else {
      desiredTarget.current.set(0, 0, 0);
      desiredPos.current.copy(camera.position); // free orbit: leave the camera alone
    }

    const ease = 1 - Math.pow(0.0015, delta); // ~critically damped, fps-independent
    controls.target.lerp(desiredTarget.current, ease);
    if (target) camera.position.lerp(desiredPos.current, ease);
    controls.update();
  });

  return null;
}
