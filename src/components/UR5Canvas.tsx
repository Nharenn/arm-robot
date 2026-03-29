import { Canvas } from '@react-three/fiber';
import { OrbitControls, Environment, ContactShadows, Grid } from '@react-three/drei';
import RobotArm3D from './RobotArm3D';
import { Suspense } from 'react';

interface UR5CanvasProps {
  angles: number[];
  theme: "light" | "dark";
}

export default function UR5Canvas({ angles, theme }: UR5CanvasProps) {
  const isDark = theme === "dark";

  return (
    <div className={`w-full h-full relative rounded-xl overflow-hidden ${isDark ? 'bg-slate-900 shadow-inset-dark' : 'bg-slate-50 shadow-inner border border-slate-200'}`}>
      <Canvas camera={{ position: [8, 5, 8], fov: 45 }}>
        <color attach="background" args={[isDark ? '#0f172a' : '#f1f5f9']} />
        <ambientLight intensity={0.5} />
        <directionalLight position={[10, 10, 5]} intensity={1} castShadow />
        <directionalLight position={[-10, 5, -5]} intensity={0.5} color="#00f2fe" />
        
        {/* Holographic floor grid */}
        <Grid 
          infiniteGrid 
          fadeDistance={20} 
          sectionColor={isDark ? "#00f2fe" : "#94a3b8"} 
          cellColor={isDark ? "#334155" : "#cbd5e1"} 
          position={[0, -2, 0]} 
        />
        
        <ContactShadows resolution={1024} scale={20} blur={2} opacity={0.5} far={10} color="#000000" position={[0, -1.9, 0]} />

        <Suspense fallback={null}>
          <Environment preset="city" />
          <RobotArm3D angles={angles} theme={theme} />
        </Suspense>

        <OrbitControls 
          enablePan={false} 
          minDistance={5} 
          maxDistance={25}
          maxPolarAngle={Math.PI / 2 - 0.05} // Prevent camera going below floor
        />
      </Canvas>
      <div className="absolute top-4 left-4 z-10 pointer-events-none">
        <span className={`text-xs font-mono px-3 py-1 rounded-full border backdrop-blur-md ${isDark ? 'bg-slate-800/80 text-cyan-400 border-cyan-500/30 shadow-[0_0_10px_rgba(0,242,254,0.2)]' : 'bg-white/80 text-slate-600 border-slate-300 shadow-sm'}`}>
          3D HOLOGRAPHIC VIEW
        </span>
      </div>
    </div>
  );
}
