import { useRef } from 'react';
import { useFrame } from '@react-three/fiber';
import * as THREE from 'three';

interface RobotArm3DProps {
  angles: number[]; // Array of 6 angles in degrees
  theme: "light" | "dark";
}

export default function RobotArm3D({ angles, theme }: RobotArm3DProps) {
  const isDark = theme === "dark";

  // Convert angles from degrees to radians
  const rads = angles.map(a => THREE.MathUtils.degToRad(a));

  const baseRef = useRef<THREE.Group>(null);
  const shoulderRef = useRef<THREE.Group>(null);
  const elbowRef = useRef<THREE.Group>(null);
  const w1Ref = useRef<THREE.Group>(null);
  const w2Ref = useRef<THREE.Group>(null);
  const w3Ref = useRef<THREE.Group>(null);

  useFrame((state, delta) => {
    const speed = 5 * delta;
    if (baseRef.current) baseRef.current.rotation.y = THREE.MathUtils.damp(baseRef.current.rotation.y, rads[0], speed, delta);
    
    // Invertimos las rotaciones (-rads) porque el eje Z de Three.js (WebGL) está espejado respecto a CoppeliaSim
    if (shoulderRef.current) shoulderRef.current.rotation.z = THREE.MathUtils.damp(shoulderRef.current.rotation.z, -rads[1], speed, delta);
    if (elbowRef.current) elbowRef.current.rotation.z = THREE.MathUtils.damp(elbowRef.current.rotation.z, -rads[2], speed, delta);
    if (w1Ref.current) w1Ref.current.rotation.z = THREE.MathUtils.damp(w1Ref.current.rotation.z, -rads[3], speed, delta);
    
    if (w2Ref.current) w2Ref.current.rotation.y = THREE.MathUtils.damp(w2Ref.current.rotation.y, -rads[4], speed, delta); 
    if (w3Ref.current) w3Ref.current.rotation.z = THREE.MathUtils.damp(w3Ref.current.rotation.z, -rads[5], speed, delta);
  });

  // ── MATERIALS ──
  // Main Silver/Aluminum Body
  const metalMaterial = new THREE.MeshStandardMaterial({
    color: isDark ? '#64748b' : '#cbd5e1', 
    roughness: 0.3,
    metalness: 0.8,
    envMapIntensity: 1.5
  });

  // Characteristic "Blue Caps" of the UR5
  const capMaterial = new THREE.MeshStandardMaterial({
    color: isDark ? '#0ea5e9' : '#1e3a8a', // Cyan in dark, Deep Blue in light
    roughness: 0.5,
    metalness: 0.2,
    emissive: isDark ? '#0284c7' : '#000000',
    emissiveIntensity: isDark ? 0.4 : 0
  });

  const darkJointMaterial = new THREE.MeshStandardMaterial({
    color: '#1e293b', 
    roughness: 0.7,
    metalness: 0.5,
  });

  // ── SCALED D-H DIMENSIONS ──
  // Approximated & visually tuned for WebGL 10x Scale
  const D1 = 1.5;   // Base height
  const A2 = 4.25;  // Upper arm length
  const A3 = 3.92;  // Lower arm length
  const D4 = 1.09;  // Wrist 1
  const D5 = 0.94;  // Wrist 2
  const D6 = 0.82;  // Wrist 3
  
  const R_L = 0.5;  // Radius of Links
  const R_J = 0.65; // Radius of Joints

  return (
    <group position={[0, -2, 0]}>
      
      {/* 0. BASE PEDESTAL */}
      <mesh position={[0, D1/2, 0]}>
        <cylinderGeometry args={[R_J+0.2, R_J+0.4, D1, 32]} />
        <primitive object={metalMaterial} />
      </mesh>

      {/* 1. J1: BASE Y-ROTATION */}
      <group position={[0, D1, 0]} ref={baseRef}>
        <mesh position={[0, 0, 0]} rotation={[Math.PI/2, 0, 0]}>
          <cylinderGeometry args={[R_J, R_J, 1.6, 32]} />
          <primitive object={capMaterial} />
        </mesh>
        
        {/* J1 Housing */}
        <mesh position={[0, R_J, 0]}>
           <cylinderGeometry args={[R_L, R_L, R_J*2, 32]} />
           <primitive object={metalMaterial} />
        </mesh>

        {/* 2. J2: SHOULDER Z-ROTATION */}
        {/* Offset sideways so the link doesn't collide */}
        <group position={[0, R_J*2, 0.8]} ref={shoulderRef}>
          <mesh rotation={[Math.PI/2, 0, 0]}>
            <cylinderGeometry args={[R_J, R_J, 1.8, 32]} />
            <primitive object={capMaterial} />
          </mesh>

          {/* Upper Arm Link */}
          <mesh position={[0, A2/2, -0.4]}>
            <cylinderGeometry args={[R_L, R_L, A2, 32]} />
            <primitive object={metalMaterial} />
          </mesh>

          {/* 3. J3: ELBOW Z-ROTATION */}
          <group position={[0, A2, -0.8]} ref={elbowRef}>
            <mesh rotation={[Math.PI/2, 0, 0]}>
              <cylinderGeometry args={[R_J-0.1, R_J-0.1, 1.6, 32]} />
              <primitive object={capMaterial} />
            </mesh>

            {/* Lower Arm Link */}
            <mesh position={[0, A3/2, 0.3]}>
              <cylinderGeometry args={[R_L-0.1, R_L-0.1, A3, 32]} />
              <primitive object={metalMaterial} />
            </mesh>

            {/* 4. J4: WRIST 1 Z-ROTATION */}
            <group position={[0, A3, 0.3]} ref={w1Ref}>
              <mesh rotation={[Math.PI/2, 0, 0]}>
                <cylinderGeometry args={[R_J-0.15, R_J-0.15, 1.4, 32]} />
                <primitive object={capMaterial} />
              </mesh>
              
              {/* Connection to W2 */}
              <mesh position={[0, 0.5, 0]}>
                 <cylinderGeometry args={[R_L-0.2, R_L-0.2, D4, 32]} />
                 <primitive object={metalMaterial} />
              </mesh>

              {/* 5. J5: WRIST 2 Y-ROTATION */}
              <group position={[0, D4, 0]} ref={w2Ref}>
                {/* Note: In real UR5, W2 rotates perpendicular to W1 */}
                <mesh rotation={[0, 0, Math.PI/2]}>
                  <cylinderGeometry args={[R_J-0.2, R_J-0.2, 1.2, 32]} />
                  <primitive object={capMaterial} />
                </mesh>
                
                <mesh position={[0.4, 0, 0]} rotation={[0, 0, Math.PI/2]}>
                   <cylinderGeometry args={[R_L-0.25, R_L-0.25, D5, 32]} />
                   <primitive object={metalMaterial} />
                </mesh>

                {/* 6. J6: WRIST 3 Z-ROTATION */}
                <group position={[D5, 0, 0]} ref={w3Ref}>
                  <mesh rotation={[Math.PI/2, 0, 0]}>
                    <cylinderGeometry args={[R_J-0.25, R_J-0.25, 1.0, 32]} />
                    <primitive object={capMaterial} />
                  </mesh>
                  
                  {/* Tool Flange */}
                  <mesh position={[0, 0.2, 0]}>
                    <cylinderGeometry args={[R_J-0.05, R_J-0.05, 0.2, 32]} />
                    <primitive object={darkJointMaterial} />
                  </mesh>

                  {/* Gripper Placeholder */}
                  <mesh position={[-0.2, 0.5, 0]}>
                    <boxGeometry args={[0.05, 0.6, 0.2]} />
                    <primitive object={metalMaterial} />
                  </mesh>
                  <mesh position={[0.2, 0.5, 0]}>
                    <boxGeometry args={[0.05, 0.6, 0.2]} />
                    <primitive object={metalMaterial} />
                  </mesh>

                </group>
              </group>
            </group>
          </group>
        </group>
      </group>
    </group>
  );
}
