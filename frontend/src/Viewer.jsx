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

export default function Viewer({ url, partingLine, viewMode }) {
  return (
    <Canvas shadows camera={{ position: [0, 0, 100], fov: 50 }}>
      <color attach="background" args={['#0f172a']} />
      <ambientLight intensity={0.5} />
      <directionalLight position={[10, 10, 5]} intensity={1} castShadow />

      <React.Suspense fallback={null}>
        <Stage preset="soft" environment="city" intensity={0.5}>
          <Model url={url} />
          
          {/* Render parting planes if mode is 'parting' */}
          {viewMode === 'parting' && partingLine && partingLine.planes && (
            <group>
              {partingLine.planes.map((plane, idx) => {
                const s = Math.max(partingLine.bbox.xlen, partingLine.bbox.ylen, partingLine.bbox.zlen) * 2;
                
                let position = [partingLine.bbox.cx, partingLine.bbox.cy, partingLine.bbox.cz];
                let rotation = [0, 0, 0];
                
                if (plane.axis === "Z") {
                  position[2] = plane.offset;
                } else if (plane.axis === "X") {
                  position[0] = plane.offset;
                  rotation = [0, Math.PI / 2, 0];
                } else if (plane.axis === "Y") {
                  position[1] = plane.offset;
                  rotation = [Math.PI / 2, 0, 0];
                }

                return (
                  <mesh key={idx} position={position} rotation={rotation}>
                    <planeGeometry args={[s, s]} />
                    <meshBasicMaterial 
                      color={plane.color} 
                      transparent 
                      opacity={0.3} 
                      side={THREE.DoubleSide} 
                      depthWrite={false} 
                    />
                    {/* Optional: Add a wireframe edge to make the split more defined */}
                    <lineSegments>
                      <edgesGeometry args={[new THREE.PlaneGeometry(s, s)]} />
                      <lineBasicMaterial color={plane.color} />
                    </lineSegments>
                  </mesh>
                );
              })}
            </group>
          )}
        </Stage>
      </React.Suspense>

      <GizmoHelper alignment="bottom-right" margin={[60, 60]}>
        <GizmoViewport axisColors={['#ef4444', '#10b981', '#3b82f6']} labelColor="white" />
      </GizmoHelper>

      <OrbitControls makeDefault />
    </Canvas>
  );
}
