import React, { useState, useEffect, useRef } from 'react';
import { Canvas, useFrame } from '@react-three/fiber';
import { OrbitControls, Stage, useGLTF, GizmoHelper, GizmoViewport } from '@react-three/drei';
import * as THREE from 'three';

const API_BASE = "http://localhost:8000";

function MoldBlock({ url, color, positionOffset }) {
  const { scene } = useGLTF(url);
  const groupRef = useRef();

  // Clone scene so we don't mutate a cached copy in unexpected ways
  const clonedScene = React.useMemo(() => scene.clone(), [scene]);

  useEffect(() => {
    clonedScene.traverse((child) => {
      if (child.isMesh) {
        child.material = new THREE.MeshStandardMaterial({
          color: new THREE.Color(color),
          transparent: true,
          opacity: 0.6,
          roughness: 0.3,
          metalness: 0.1,
          side: THREE.DoubleSide,
        });
        
        // Ensure edges are visible
        const edges = new THREE.EdgesGeometry(child.geometry);
        const line = new THREE.LineSegments(
          edges,
          new THREE.LineBasicMaterial({ color: 0xffffff, linewidth: 1, transparent: true, opacity: 0.5 })
        );
        child.add(line);
      }
    });
  }, [clonedScene, color]);

  useFrame((state, delta) => {
    if (groupRef.current) {
      // Smoothly interpolate the translation for exploded view
      const lerpFactor = 10 * delta; // Adjust damping factor based on delta time
      groupRef.current.position.x = THREE.MathUtils.lerp(groupRef.current.position.x, positionOffset[0], lerpFactor);
      groupRef.current.position.y = THREE.MathUtils.lerp(groupRef.current.position.y, positionOffset[1], lerpFactor);
      groupRef.current.position.z = THREE.MathUtils.lerp(groupRef.current.position.z, positionOffset[2], lerpFactor);
    }
  });

  return (
    <group ref={groupRef}>
      <primitive object={clonedScene} />
    </group>
  );
}

export default function ExplodedViewer({ jobId }) {
  const [explodeDistance, setExplodeDistance] = useState(0.0);

  const topCavityUrl = `${API_BASE}/analyze/${jobId}/mesh?mode=mold_top_cavity`;
  const bottomCoreUrl = `${API_BASE}/analyze/${jobId}/mesh?mode=mold_bottom_core`;
  const leftSliderUrl = `${API_BASE}/analyze/${jobId}/mesh?mode=mold_left_slider`;
  const rightSliderUrl = `${API_BASE}/analyze/${jobId}/mesh?mode=mold_right_slider`;

  return (
    <div style={{ width: '100%', height: '100%', position: 'relative' }}>
      <Canvas shadows camera={{ position: [0.1, 0.1, 0.2], fov: 50 }}>
        <color attach="background" args={['#0f172a']} />
        
        <React.Suspense fallback={null}>
          <Stage preset="soft" environment="city" intensity={0.5}>
            <group>
              {/* Top Cavity (+Z offset) - Light Blue. Starts at Z=0.022m */}
              <MoldBlock 
                url={topCavityUrl} 
                color="#3b82f6" 
                positionOffset={[0, 0, explodeDistance]} 
              />
              {/* Bottom Core (-Z offset) - Slate Gray. Thin up to Z=0.004609m */}
              <MoldBlock 
                url={bottomCoreUrl} 
                color="#64748b" 
                positionOffset={[0, 0, -explodeDistance]} 
              />
              {/* Left Slider (-X offset) - Amber. Middle segment */}
              <MoldBlock 
                url={leftSliderUrl} 
                color="#f59e0b" 
                positionOffset={[-explodeDistance, 0, 0]} 
              />
              {/* Right Slider (+X offset) - Yellow. Middle segment */}
              <MoldBlock 
                url={rightSliderUrl} 
                color="#facc15" 
                positionOffset={[explodeDistance, 0, 0]} 
              />
            </group>
          </Stage>
        </React.Suspense>

        <GizmoHelper alignment="bottom-right" margin={[60, 60]}>
          <GizmoViewport axisColors={['#ef4444', '#10b981', '#3b82f6']} labelColor="white" />
        </GizmoHelper>

        <OrbitControls makeDefault />
      </Canvas>

      {/* Explode Slider UI */}
      <div style={{
        position: 'absolute',
        bottom: '20px',
        left: '20px',
        background: 'rgba(15, 23, 42, 0.8)',
        padding: '16px',
        borderRadius: '8px',
        color: 'white',
        border: '1px solid #334155',
        width: '300px',
        display: 'flex',
        flexDirection: 'column',
        gap: '8px'
      }}>
        <div style={{ display: 'flex', justifyContent: 'space-between' }}>
          <label style={{ fontSize: '14px', fontWeight: 'bold' }}>Explode Tooling</label>
          <span style={{ fontSize: '14px' }}>{explodeDistance.toFixed(1)} mm</span>
        </div>
        <input 
          type="range" 
          min="0" 
          max="80" 
          step="0.5" 
          value={explodeDistance}
          onChange={(e) => setExplodeDistance(parseFloat(e.target.value))}
          style={{ width: '100%', accentColor: 'var(--accent)' }}
        />
      </div>
    </div>
  );
}
