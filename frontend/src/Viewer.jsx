import React, { useRef, useEffect } from 'react';
import { Canvas } from '@react-three/fiber';
import { OrbitControls, Stage, useGLTF, GizmoHelper, GizmoViewport } from '@react-three/drei';
import * as THREE from 'three';

function Model({ url }) {
  const { scene } = useGLTF(url);

  useEffect(() => {
    if (!scene) return;
    scene.traverse((child) => {
      if (child.isMesh) {
        // Use vertex colors baked by the backend
        child.material = new THREE.MeshStandardMaterial({
          vertexColors: true,
          roughness: 0.55,
          metalness: 0.1,
          side: THREE.DoubleSide,
        });
      }
    });
  }, [scene]);

  return <primitive object={scene} />;
}

export default function Viewer({ url }) {
  return (
    <Canvas shadows camera={{ position: [0, 0, 100], fov: 50 }}>
      <color attach="background" args={['#0f172a']} />
      <ambientLight intensity={0.5} />
      <directionalLight position={[10, 10, 5]} intensity={1} castShadow />

      <React.Suspense fallback={null}>
        <Stage preset="soft" environment="city" intensity={0.5}>
          <Model url={url} />
        </Stage>
      </React.Suspense>

      <GizmoHelper alignment="bottom-right" margin={[60, 60]}>
        <GizmoViewport axisColors={['#ef4444', '#10b981', '#3b82f6']} labelColor="white" />
      </GizmoHelper>

      <OrbitControls makeDefault />
    </Canvas>
  );
}
