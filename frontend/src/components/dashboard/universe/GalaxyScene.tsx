"use client";

// The WebGL half of the Learning Universe. Everything drawn here is read off
// the GalaxyLayout — no state of its own beyond the camera. Mastery is the
// visual language:
//
//   mastered  → bright green, solid
//   learning  → warm amber, solid
//   weak      → red, solid
//   not started / locked → the "knowledge fog": dim, translucent, waiting
//
// Goal skills are landmarks: larger, ringed, haloed. Selecting a node lights
// its full prerequisite route and dims the rest — the same rule as the 2D view.

import { useMemo, useRef, useState } from "react";
import { Canvas, useFrame } from "@react-three/fiber";
import { Html, Line, OrbitControls, Stars } from "@react-three/drei";
import * as THREE from "three";
import type { OrbitControls as OrbitControlsImpl } from "three-stdlib";
import type { GraphModel } from "@/lib/graph-view";
import { transitive } from "@/lib/graph-view";
import { layoutGalaxy, type GalaxyNode } from "@/lib/universe-layout";

// Hex twins of the app's CSS state tokens — WebGL can't read CSS variables.
const STATE_HEX = {
  mastered: "#22c55e",
  learning: "#f59e0b",
  weak: "#f87171",
  not_started: "#64748b",
} as const;
const BRAND = "#8b5cf6";
const EDGE_DIM = "#2b3245";

export interface GalaxySceneProps {
  model: GraphModel;
  selectedId: string | null;
  onSelect: (id: string | null) => void;
  /** Node ids the AI mentor just mentioned — rendered with a pulse. */
  pulseIds: Set<string>;
}

export function GalaxyScene({ model, selectedId, onSelect, pulseIds }: GalaxySceneProps) {
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
  const cameraZ = Math.max(9, layout.spread * 2.6 + layout.height * 0.55);

  return (
    <Canvas
      camera={{ position: [cameraZ * 0.55, mid + 2.5, cameraZ], fov: 46 }}
      dpr={[1, 2]}
      onPointerMissed={() => onSelect(null)}
      // The universe is committed to space; both app themes get the same night.
      style={{ background: "radial-gradient(ellipse at 50% 35%, #101529 0%, #05060f 70%)" }}
    >
      <fog attach="fog" args={["#05060f", cameraZ, cameraZ * 2.6]} />
      <ambientLight intensity={0.55} />
      <pointLight position={[8, layout.height + 6, 8]} intensity={220} color="#c4b5fd" />
      <pointLight position={[-8, -4, -6]} intensity={80} color="#38bdf8" />
      <Stars radius={60} depth={40} count={2400} factor={3} saturation={0} fade speed={0.4} />

      <group position={[0, -mid, 0]}>
        {layout.edges.map((e) => {
          const isLit =
            focus != null &&
            (e.prerequisiteId === selectedId || e.dependentId === selectedId ||
              (lit(e.prerequisiteId) && lit(e.dependentId) && focus != null));
          const hard = e.kind === "hard_prerequisite";
          return (
            <Line
              key={`${e.prerequisiteId}->${e.dependentId}`}
              points={[e.from, e.to]}
              color={focus && isLit ? BRAND : EDGE_DIM}
              lineWidth={focus && isLit ? 1.8 : 1}
              dashed={!hard}
              dashSize={0.18}
              gapSize={0.14}
              transparent
              opacity={focus ? (isLit ? 0.95 : 0.12) : hard ? 0.55 : 0.3}
            />
          );
        })}

        {layout.nodes.map((n) => (
          <SkillStar
            key={n.id}
            node={n}
            selected={n.id === selectedId}
            dimmed={focus != null && !lit(n.id)}
            pulsing={pulseIds.has(n.id)}
            onSelect={onSelect}
          />
        ))}
      </group>

      <Rig targetY={selectedId ? (layout.byId.get(selectedId)?.position[1] ?? mid) - mid : 0} />
      <OrbitControls
        makeDefault
        enablePan={false}
        minDistance={4}
        maxDistance={cameraZ * 1.8}
        autoRotate
        autoRotateSpeed={0.55}
      />
    </Canvas>
  );
}

/** Ease the orbit target toward the selected node's altitude. */
function Rig({ targetY }: { targetY: number }) {
  const controlsRef = useRef<OrbitControlsImpl | null>(null);
  useFrame((state) => {
    const controls = (state.controls as OrbitControlsImpl | null) ?? controlsRef.current;
    if (!controls) return;
    controls.target.y += (targetY - controls.target.y) * 0.06;
    controls.update();
  });
  return null;
}

function SkillStar({
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
  const meshRef = useRef<THREE.Mesh>(null);
  const [hovered, setHovered] = useState(false);

  const inFog = node.state === "not_started";
  const color = STATE_HEX[node.state];
  const baseOpacity = inFog ? 0.3 : 1;

  useFrame((state) => {
    if (!meshRef.current) return;
    const pulse = pulsing || selected ? 1 + Math.sin(state.clock.elapsedTime * 4) * 0.12 : 1;
    meshRef.current.scale.setScalar(pulse);
  });

  return (
    <group position={node.position}>
      <mesh
        ref={meshRef}
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
        <sphereGeometry args={[node.radius, 32, 32]} />
        <meshStandardMaterial
          color={color}
          emissive={color}
          emissiveIntensity={dimmed ? 0.05 : inFog ? 0.12 : hovered || selected ? 1.1 : 0.55}
          transparent
          opacity={dimmed ? 0.15 : baseOpacity}
          roughness={0.35}
          metalness={0.1}
        />
      </mesh>

      {/* Goal skills are landmarks — give them an orbit ring. */}
      {node.isTarget && (
        <mesh rotation={[Math.PI / 2.2, 0, 0]}>
          <torusGeometry args={[node.radius + 0.22, 0.02, 8, 48]} />
          <meshBasicMaterial
            color={BRAND}
            transparent
            opacity={dimmed ? 0.08 : 0.8}
          />
        </mesh>
      )}

      {/* Selection halo. */}
      {selected && (
        <mesh>
          <sphereGeometry args={[node.radius + 0.16, 24, 24]} />
          <meshBasicMaterial color={BRAND} transparent opacity={0.18} />
        </mesh>
      )}

      <Html
        center
        distanceFactor={13}
        position={[0, node.radius + 0.42, 0]}
        style={{ pointerEvents: "none", transition: "opacity 200ms" }}
        zIndexRange={[10, 0]}
      >
        <div
          style={{
            opacity: dimmed ? 0.15 : inFog && !hovered && !selected ? 0.45 : 1,
            color: "#e8eaf0",
            fontSize: 11,
            fontWeight: selected ? 700 : 500,
            whiteSpace: "nowrap",
            textShadow: "0 1px 6px rgba(0,0,0,0.9)",
            textAlign: "center",
          }}
        >
          {node.name}
          {node.proficiency != null && (
            <span style={{ color: "#9aa4b2", marginLeft: 5, fontWeight: 400 }}>
              {Math.round(node.proficiency * 100)}%
            </span>
          )}
        </div>
      </Html>
    </group>
  );
}
