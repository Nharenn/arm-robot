import { useState, useEffect, useRef } from "react";
import { JointData, HistoryEntry, LayoutMode } from "./types";
import { useRobotData } from "./hooks/useRobotData";
import { Card, CardLabel, SensorGauge, ParamSlider } from "./components/UIBlocks";
import { ChartPID, ChartTerms } from "./components/Charts";
import ConnectionSettings, { getInitialConfig, RemoteConfig } from "./components/ConnectionSettings";
import UR5Canvas from "./components/UR5Canvas";

export default function App() {
  const [remoteConfig, setRemoteConfig] = useState<RemoteConfig | null>(getInitialConfig);
  const [activeJoint, setActiveJoint] = useState<keyof JointData>("J2");
  const { pid, sensors, targetAngles, setTarget, setParams, setGripper, connectionStatus, bridgeStatus, msgRate } = useRobotData(activeJoint, remoteConfig?.mqttUrl);
  const [theme, setTheme] = useState<"light" | "dark">("light");
  const [history, setHistory] = useState<HistoryEntry[]>([]);
  const [mobileTab, setMobileTab] = useState<"control" | "viewer" | "charts">("control");
  const [layoutMode, setLayoutMode] = useState<LayoutMode>("desktop");

  const [kp, setKp] = useState<number>(1.0);
  const [ki, setKi] = useState<number>(0.1);
  const [kd, setKd] = useState<number>(0.05);
  const [gripClosed, setGripClosed] = useState<boolean>(false);
  const tick = useRef<number>(0);

  const isConnected = connectionStatus === "connected";
  const statusColor = isConnected ? "bg-emerald-500" : connectionStatus === "connecting" ? "bg-amber-500" : "bg-red-500";
  const statusText = isConnected
    ? (bridgeStatus.mode === "live" ? "Live" : bridgeStatus.mode === "demo" ? "Demo" : "Connected")
    : connectionStatus === "connecting" ? "Connecting..." : "Offline (Simulating)";

  const prevJointRef = useRef<keyof JointData>(activeJoint);
  useEffect(() => {
    if (prevJointRef.current !== activeJoint) {
      setHistory([]);
      prevJointRef.current = activeJoint;
    }
  }, [activeJoint]);

  useEffect(() => {
    setHistory(h => {
      const e: HistoryEntry = { t: tick.current++, sp: pid.setpoint, out: pid.output, err: pid.error, p: pid.p, i: pid.i, d: pid.d };
      const n = [...h, e]; return n.length > 250 ? n.slice(-250) : n;
    });
  }, [pid]);

  useEffect(() => { setParams({ kp, ki, kd }); }, [kp, ki, kd, setParams]);
  useEffect(() => {
    if (theme === "dark") document.documentElement.classList.add("dark");
    else document.documentElement.classList.remove("dark");
  }, [theme]);

  // ── DEVICE LAYOUT DETECTION ──
  useEffect(() => {
    const handleResize = () => {
      const w = window.innerWidth;
      if (w < 768) setLayoutMode("mobile");
      else if (w < 1100) setLayoutMode("tablet");
      else if (w < 1730) setLayoutMode("compact");
      else setLayoutMode("desktop");
    };
    handleResize();
    window.addEventListener("resize", handleResize);
    return () => window.removeEventListener("resize", handleResize);
  }, []);

  const jointKeys = Object.keys(targetAngles) as Array<keyof JointData>;
  const tempPct = Math.min(100, ((sensors.temp - 15) / 65) * 100);
  const forcePct = Math.min(100, (sensors.force / 20) * 100);
  const errPct = Math.min(100, (Math.abs(pid.error) / 45) * 100);

  // ── COMPONENT BUILDING BLOCKS ──

  const viewerMinH = layoutMode === 'mobile' ? 'min-h-[280px]' : layoutMode === 'tablet' ? 'min-h-[340px]' : layoutMode === 'compact' ? 'min-h-[380px]' : 'min-h-[480px]';

  const currentAngles = [
    targetAngles.J1, 
    targetAngles.J2, 
    targetAngles.J3, 
    targetAngles.J4, 
    targetAngles.J5, 
    targetAngles.J6
  ];

  const ViewerBlock = (
    <div className={`relative overflow-hidden shrink-0 w-full min-h-[300px] aspect-square sm:aspect-video lg:aspect-[21/9] rounded-2xl`}>
      <UR5Canvas angles={currentAngles} theme={theme} />
      
      <div className="absolute bottom-4 left-4 bg-black/60 shadow-md backdrop-blur-md rounded-full px-4 py-1.5 mt-auto text-xs text-slate-300 font-medium z-10 border border-slate-700">
        Model: <span className="text-blue-400 font-bold">UR5</span> · 6 DOF
        {bridgeStatus.mode === "live" && <span className="ml-2 text-emerald-400">LIVE</span>}
      </div>
      <div className="absolute top-4 right-4 bg-black/60 shadow-lg backdrop-blur-md rounded-xl p-2.5 flex flex-col gap-1 z-10 border border-slate-700">
        <div className={`text-xs font-mono font-bold flex items-center gap-1.5 ${isConnected ? 'text-emerald-400' : 'text-amber-400'}`}>
          <span className={`w-2 h-2 rounded-full ${statusColor} animate-pulse shadow-[0_0_8px_currentColor]`}></span>
          {statusText}
        </div>
        <div className="text-[10px] text-slate-400 font-mono tracking-wide">MQTT {msgRate} msg/s</div>
      </div>
    </div>
  );

  const SensorsBlock = (
    <Card>
      <CardLabel>Sensors</CardLabel>
      <SensorGauge label="Motor temp" value={sensors.temp} unit="°C" pct={tempPct} colorClass="text-amber-500" bgClass="bg-amber-500" />
      <SensorGauge label="Grip force" value={sensors.force} unit="N" pct={forcePct} colorClass="text-emerald-500" bgClass="bg-emerald-500" />
      <SensorGauge label="PID error" value={Math.abs(pid.error).toFixed(1)} unit="°" pct={errPct} colorClass="text-rose-500 flex-1" bgClass="bg-rose-500" />
    </Card>
  );

  const SetpointBlock = (
    <Card>
      <CardLabel>Setpoint — <span className="text-emerald-600 dark:text-emerald-400 ml-1 font-bold">{activeJoint}</span></CardLabel>
      <div className="flex gap-1 mb-5 bg-slate-100 dark:bg-slate-800 p-1 rounded-xl">
        {jointKeys.map(j => (
          <button
            key={j}
            onClick={() => setActiveJoint(j)}
            className={`flex-1 py-1.5 rounded-lg text-xs font-bold font-mono transition-all ${j === activeJoint
                ? "bg-white dark:bg-slate-700 text-blue-600 dark:text-blue-400 shadow-sm"
                : "text-slate-500 dark:text-slate-400 hover:bg-slate-200/50 dark:hover:bg-slate-700/50"
              }`}
          >
            {j}
          </button>
        ))}
      </div>

      <div className="flex justify-center items-baseline my-6 group">
        <input
          type="number"
          value={targetAngles[activeJoint]}
          onChange={e => setTarget(activeJoint, e.target.value === "" ? 0 : +e.target.value)}
          className="text-6xl font-black text-center text-emerald-600 dark:text-emerald-400 font-mono tabular-nums bg-transparent border-b-[3px] border-emerald-200 dark:border-emerald-900 focus:border-emerald-500 dark:focus:border-emerald-500 outline-none w-32 pb-1 transition-colors"
        />
        <span className="text-3xl font-medium text-slate-400 ml-1">°</span>
      </div>

      <input type="range" min={-90} max={90} step={1} value={targetAngles[activeJoint]}
        onChange={e => setTarget(activeJoint, +e.target.value)}
        className="w-full h-2 bg-slate-200 dark:bg-slate-700 rounded-lg appearance-none cursor-pointer accent-emerald-500" />

      <div className="flex justify-between mt-2 text-xs text-slate-400 font-medium">
        <span>-90°</span><span>+90°</span>
      </div>
      <div className="flex gap-1.5 mt-5 flex-wrap">
        {[-45, 0, 30, 45, 90].map(v => (
          <button key={v} onClick={() => setTarget(activeJoint, v)} className={`flex-1 min-w-[36px] py-2 rounded-lg text-xs font-semibold font-mono border transition-colors ${targetAngles[activeJoint] === v
              ? "border-emerald-300 dark:border-emerald-800 bg-emerald-50 dark:bg-emerald-900/30 text-emerald-600 dark:text-emerald-400 shadow-[inset_0_2px_4px_rgba(0,0,0,0.05)]"
              : "border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-500 hover:border-slate-300 dark:hover:border-slate-600 hover:bg-slate-50"
            }`}>
            {v}°
          </button>
        ))}
      </div>
    </Card>
  );

  const TuningBlock = (
    <Card>
      <div className="flex justify-between items-center mb-5">
        <div className="text-xs font-semibold text-slate-500 dark:text-slate-400 tracking-wide">PID TUNING ({activeJoint})</div>
        <span className="text-[10px] font-mono text-slate-400 bg-slate-100 dark:bg-slate-800 px-2 py-0.5 rounded-md">e(t) = sp - pv</span>
      </div>
      <ParamSlider label="Kp" value={kp} onChange={setKp} min={0} max={10} step={0.1} accentClass="text-blue-500 dark:text-blue-400" />
      <ParamSlider label="Ki" value={ki} onChange={setKi} min={0} max={5} step={0.05} accentClass="text-emerald-500 dark:text-emerald-400" />
      <ParamSlider label="Kd" value={kd} onChange={setKd} min={0} max={3} step={0.05} accentClass="text-amber-500 dark:text-amber-400" />
    </Card>
  );

  const GripperStatusBlock = (
    <div className="flex flex-col gap-4">
      <button 
        onClick={() => { setGripClosed(!gripClosed); setGripper(!gripClosed); }}
        className={`w-full py-4 px-4 shrink-0 rounded-2xl border flex items-center justify-center gap-3 text-sm font-bold shadow-sm transition-all focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-offset-white dark:focus:ring-offset-slate-900 focus:ring-emerald-500 ${
        gripClosed 
          ? "border-emerald-400 dark:border-emerald-800 bg-emerald-50 dark:bg-emerald-900/40 text-emerald-600 dark:text-emerald-400 shadow-[inset_0_2px_8px_rgba(16,185,129,0.1)]" 
          : "border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-600 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-slate-700 hover:shadow-md"
      }`}>
        <span className="text-xl drop-shadow-sm">{gripClosed ? "✊" : "🤲"}</span>
        {gripClosed ? "Gripper Locked" : "Gripper Open"}
      </button>

      <div className="px-5 py-3.5 shrink-0 rounded-xl bg-slate-100 dark:bg-slate-800/80 border border-slate-200 dark:border-slate-700 flex justify-between items-center text-xs text-slate-500 dark:text-slate-400 font-medium tracking-wide">
        <span>MQTT Status</span>
        <span className={`font-bold flex items-center gap-1.5 ${isConnected ? 'text-emerald-600 dark:text-emerald-400' : 'text-amber-600 dark:text-amber-400'}`}>
          <span className={`w-1.5 h-1.5 rounded-full ${statusColor} animate-pulse shadow-[0_0_6px_currentColor]`} />
          {statusText} {isConnected && `· ${msgRate} msg/s`}
        </span>
      </div>
    </div>
  );

  const ChartsBlock = (
    <div className={`grid gap-5 ${layoutMode === 'mobile' ? 'grid-cols-1' : 'grid-cols-2'} shrink-0`}>
      <Card className="h-[240px] flex flex-col p-5 w-full">
        <CardLabel>PID response ({activeJoint})</CardLabel>
        <div className="flex-1 w-full min-h-0 mt-2">
          <ChartPID data={history} />
        </div>
      </Card>
      <Card className="h-[240px] flex flex-col p-5 w-full">
        <CardLabel>P / I / D terms</CardLabel>
        <div className="flex-1 w-full min-h-0 mt-2">
          <ChartTerms data={history} />
        </div>
      </Card>
    </div>
  );

  const JointsBarBlock = (
    <Card className="p-5 md:p-6 grid grid-cols-1 xl:grid-cols-2 2xl:grid-cols-3 gap-6 shrink-0 z-10 w-full">
      {jointKeys.map(j => {
        const isActive = j === activeJoint;
        return (
          <div key={j} className="flex items-center gap-3 md:gap-4 w-full">
            <span className={`text-sm md:text-base font-bold font-mono min-w-[28px] ${isActive ? 'text-blue-600 dark:text-blue-400 drop-shadow-[0_0_8px_rgba(59,130,246,0.3)]' : 'text-slate-400 dark:text-slate-500'}`}>{j}</span>
            <input type="range" min={-180} max={180} step={1} value={targetAngles[j]}
              onChange={e => {
                setTarget(j, +e.target.value);
                setActiveJoint(j);
              }}
              className={`flex-1 h-2 rounded-lg appearance-none cursor-pointer bg-slate-200 dark:bg-slate-700 min-w-[60px] ${isActive ? 'accent-blue-500 shadow-sm' : 'accent-slate-400 dark:accent-slate-500'}`} />
            <div className="flex items-center bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700/80 rounded-lg px-2 py-1 shadow-inner shrink-0">
              <input 
                type="number"
                value={targetAngles[j]}
                onChange={e => {
                  setTarget(j, e.target.value === "" ? 0 : +e.target.value);
                  setActiveJoint(j);
                }}
                className="w-10 md:w-11 text-sm font-mono font-medium text-slate-700 dark:text-slate-200 bg-transparent border-none outline-none text-right flex-shrink-0"
              />
              <span className="text-sm font-bold text-slate-400 dark:text-slate-500 ml-0.5">°</span>
            </div>
          </div>
        );
      })}
    </Card>
  );

  const CompactJointsBarBlock = (
    <Card className="p-4 md:p-5 flex flex-wrap gap-3 shrink-0 z-10 w-full border border-slate-200 dark:border-slate-800 shadow-sm">
      {jointKeys.map(j => {
        const isActive = j === activeJoint;
        return (
          <div 
            key={j} 
            className={`flex flex-col flex-[1_1_30%] md:flex-[1_1_14%] p-3 rounded-xl border transition-all ${
              isActive 
                ? 'border-blue-400 dark:border-blue-700 bg-blue-50/50 dark:bg-blue-900/20 shadow-[inset_0_2px_4px_rgba(59,130,246,0.05)]' 
                : 'border-slate-200 dark:border-slate-800/80 bg-slate-50/50 dark:bg-slate-800/20'
            }`}
          >
            <div className="flex justify-between items-center mb-2">
              <span className={`text-[10px] md:text-xs font-bold font-mono ${isActive ? 'text-blue-600 dark:text-blue-400' : 'text-slate-500 dark:text-slate-400'}`}>{j}</span>
              {isActive && <span className="w-1.5 h-1.5 rounded-full bg-blue-500 animate-pulse shadow-[0_0_6px_rgba(59,130,246,0.5)]"></span>}
            </div>
            <div className="flex items-center w-full bg-white dark:bg-slate-900/80 border border-slate-200 dark:border-slate-700 rounded-lg px-2 py-1.5 shadow-sm">
              <input 
                type="number"
                value={targetAngles[j]}
                onChange={e => {
                  setTarget(j, e.target.value === "" ? 0 : +e.target.value);
                  setActiveJoint(j);
                }}
                className={`w-full text-base md:text-lg font-mono font-bold bg-transparent border-none outline-none text-right ${isActive ? 'text-slate-800 dark:text-slate-100' : 'text-slate-600 dark:text-slate-300'}`}
              />
              <span className="text-xs font-bold text-slate-400 dark:text-slate-500 ml-1">°</span>
            </div>
          </div>
        );
      })}
    </Card>
  );

  return (
    <div className={`flex flex-col bg-slate-50 dark:bg-slate-950 text-slate-800 dark:text-slate-200 font-sans transition-colors duration-300 ${layoutMode === 'mobile' ? 'h-[100dvh] overflow-hidden' : 'min-h-screen'}`}>

      {/* ── HEADER ── */}
      <header className="flex items-center justify-between px-4 md:px-6 py-3 shrink-0 bg-white/90 dark:bg-slate-900/90 backdrop-blur-md border-b border-slate-200 dark:border-slate-800 shadow-sm z-50 sticky top-0 transition-colors duration-300">
        <div className="flex items-center gap-4">
          <div className="h-12 md:h-16 flex items-center justify-center">
            <img src="/logo.png" alt="IUD Logo" className="h-full w-auto object-contain drop-shadow-sm" />
          </div>
          <div>
            <div className="text-sm md:text-base font-extrabold tracking-tight text-slate-900 dark:text-white uppercase">ARM CONTROL</div>
            {layoutMode !== "mobile" && <div className="text-[10px] text-slate-500 font-medium tracking-wide">CoppeliaSim · MQTT · PID</div>}
          </div>
        </div>
        <div className="flex items-center gap-4">
          <div className="hidden md:flex items-center gap-1.5 text-xs text-slate-600 dark:text-slate-400 font-medium">
            <span className={`w-2 h-2 rounded-full ${statusColor} animate-pulse`} />
            {statusText}
          </div>
          <button
            onClick={() => setTheme(theme === "light" ? "dark" : "light")}
            className="w-9 h-9 rounded-xl border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800 hover:bg-slate-100 dark:hover:bg-slate-700 flex items-center justify-center transition-all focus:outline-none focus:ring-2 focus:ring-blue-500/50"
          >
            {theme === "light" ? "🌙" : "☀️"}
          </button>
        </div>
      </header>

      {/* ── FULL DESKTOP (>= 1730px) ── */}
      {layoutMode === "desktop" && (
        <div className="flex-1 w-full max-w-[1920px] mx-auto p-6 grid grid-cols-[1fr_360px] gap-6 items-start">
          <div className="flex flex-col gap-6 min-w-0">
            {ViewerBlock}
            {ChartsBlock}
            {JointsBarBlock}
          </div>
          <div className="flex flex-col gap-6 sticky top-20">
            {SensorsBlock}
            {SetpointBlock}
            {TuningBlock}
            {GripperStatusBlock}
          </div>
        </div>
      )}

      {/* ── COMPACT DESKTOP (1100px - 1729px) ── */}
      {layoutMode === "compact" && (
        <div className="flex-1 w-full max-w-[1440px] mx-auto p-5 grid grid-cols-[1fr_300px] gap-5 items-start">
          <div className="flex flex-col gap-5 min-w-0">
            {ViewerBlock}
            {ChartsBlock}
            {CompactJointsBarBlock}
          </div>
          <div className="flex flex-col gap-5 sticky top-20">
            {SensorsBlock}
            {SetpointBlock}
            {TuningBlock}
            {GripperStatusBlock}
          </div>
        </div>
      )}

      {/* ── TABLET (768px - 1099px) ── */}
      {layoutMode === "tablet" && (
        <div className="flex flex-col gap-5 p-5 w-full max-w-[900px] mx-auto mb-8">
          {ViewerBlock}

          <div className="grid grid-cols-[1fr_1fr] gap-5">
            {SetpointBlock}
            {SensorsBlock}
          </div>

          {CompactJointsBarBlock}

          <div className="grid grid-cols-[1fr_1fr] gap-5">
            {TuningBlock}
            {GripperStatusBlock}
          </div>

          {ChartsBlock}
        </div>
      )}

      {/* ── MOBILE SCROLLABLE CONTENT (<768px) ── */}
      {layoutMode === "mobile" && (
        <div className="flex flex-col flex-1 p-4 pb-20 overflow-y-auto overflow-x-hidden gap-4 custom-scrollbar relative">
          {mobileTab === "control" && (
            <>
              {SetpointBlock}
              {JointsBarBlock}
              {TuningBlock}
              {GripperStatusBlock}
            </>
          )}

          {mobileTab === "viewer" && (
            <>
              {ViewerBlock}
              {SensorsBlock}
            </>
          )}

          {mobileTab === "charts" && (
            <>
              <div className="text-xl font-bold px-2 py-1 text-slate-700 dark:text-slate-200 flex items-center justify-between">
                <span>Targeted: <span className="text-indigo-600 dark:text-indigo-400">{activeJoint}</span></span>
              </div>
              {ChartsBlock}
            </>
          )}
        </div>
      )}

      {/* ── MOBILE BOTTOM NAVIGATION ── */}
      {layoutMode === "mobile" && (
        <nav className="shrink-0 bg-white/95 dark:bg-slate-900/95 backdrop-blur-lg border-t border-slate-200 dark:border-slate-800 flex justify-around items-center px-2 py-1 pb-[env(safe-area-inset-bottom)] z-50 shadow-[0_-8px_20px_rgba(0,0,0,0.04)] transition-colors absolute bottom-0 w-full">
          <button onClick={() => setMobileTab("control")} className={`flex flex-col items-center p-2 rounded-xl w-1/3 transition-colors ${mobileTab === 'control' ? 'text-blue-600 dark:text-blue-400' : 'text-slate-400 hover:bg-slate-50 dark:hover:bg-slate-800'}`}>
            <svg className="w-6 h-6 mb-1" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 6V4m0 2a2 2 0 100 4m0-4a2 2 0 110 4m-6 8a2 2 0 100-4m0 4a2 2 0 110-4m0 4v2m0-6V4m6 6v10m6-2a2 2 0 100-4m0 4a2 2 0 110-4m0 4v2m0-6V4" /></svg>
            <span className="text-[10px] font-bold tracking-wide">Control</span>
          </button>
          <button onClick={() => setMobileTab("viewer")} className={`flex flex-col items-center p-2 rounded-xl w-1/3 transition-colors ${mobileTab === 'viewer' ? 'text-emerald-600 dark:text-emerald-400' : 'text-slate-400 hover:bg-slate-50 dark:hover:bg-slate-800'}`}>
            <svg className="w-6 h-6 mb-1" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M14 10l-2 1m0 0l-2-1m2 1v2.5M20 7l-2 1m2-1l-2-1m2 1v2.5M14 4l-2-1-2 1M4 7l2-1M4 7l2 1M4 7v2.5M12 21l-2-1m2 1l2-1m-2 1v-2.5M6 18l-2-1v-2.5M18 18l2-1v-2.5" /></svg>
            <span className="text-[10px] font-bold tracking-wide">Robot</span>
          </button>
          <button onClick={() => setMobileTab("charts")} className={`flex flex-col items-center p-2 rounded-xl w-1/3 transition-colors ${mobileTab === 'charts' ? 'text-indigo-600 dark:text-indigo-400' : 'text-slate-400 hover:bg-slate-50 dark:hover:bg-slate-800'}`}>
            <svg className="w-6 h-6 mb-1" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 12l3-3 3 3 4-4M8 21l4-4 4 4M3 4h18M4 4h16v12a1 1 0 01-1 1H5a1 1 0 01-1-1V4z" /></svg>
            <span className="text-[10px] font-bold tracking-wide">Charts</span>
          </button>
        </nav>
      )}

      {/* CONNECTION SETTINGS */}
      <ConnectionSettings
        onConnect={setRemoteConfig}
        currentConfig={remoteConfig}
        connectionStatus={connectionStatus}
      />

      {/* GLOBAL CSS */}
      <style>{`
        input[type="number"]::-webkit-inner-spin-button, input[type="number"]::-webkit-outer-spin-button {
          -webkit-appearance: none; margin: 0;
        }
        input[type="number"] { -moz-appearance: textfield; }
        .custom-scrollbar::-webkit-scrollbar { width: 6px; height: 6px; }
        .custom-scrollbar::-webkit-scrollbar-track { background: transparent; }
        .custom-scrollbar::-webkit-scrollbar-thumb { background: #cbd5e1; border-radius: 3px; }
        .dark .custom-scrollbar::-webkit-scrollbar-thumb { background: #475569; }
      `}</style>
    </div>
  );
}
