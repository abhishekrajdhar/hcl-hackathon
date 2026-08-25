"use client";

// A drifting 3D starfield woven into the landing backdrop — the first hint of
// the Learning Universe the dashboard opens into. Pointer-events pass through;
// it is scenery, not UI.

import { Canvas, useFrame } from "@react-three/fiber";
import { Stars } from "@react-three/drei";
import { useRef } from "react";
import type * as THREE from "three";

function Drift() {
  const group = useRef<THREE.Group>(null);
  useFrame((state) => {
    if (!group.current) return;
    group.current.rotation.y = state.clock.elapsedTime * 0.012;
    group.current.rotation.x = Math.sin(state.clock.elapsedTime * 0.05) * 0.04;
  });
  return (
    <group ref={group}>
      <Stars radius={70} depth={50} count={2600} factor={3.4} saturation={0} fade speed={0.5} />
    </group>
  );
}

export function Starfield() {
  return (
    <div aria-hidden className="pointer-events-none absolute inset-0">
      <Canvas
        camera={{ position: [0, 0, 1], fov: 70 }}
        dpr={[1, 1.75]}
        gl={{ alpha: true, antialias: false }}
        style={{ background: "transparent" }}
      >
        <Drift />
      </Canvas>
    </div>
  );
}
