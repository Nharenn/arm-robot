/**
 * Panel de configuración de conexión remota.
 * Permite al profesor (o cualquier usuario remoto) ingresar
 * las URLs de Ngrok para conectarse al broker MQTT y al video stream
 * que corren en la Mac del estudiante.
 */

import { useState, useEffect } from "react";

// ── Detectar si estamos en localhost o en la nube ──
const isLocalhost = typeof window !== "undefined" &&
  (window.location.hostname === "localhost" || window.location.hostname === "127.0.0.1");

// ── Defaults ──
const DEFAULT_MQTT = isLocalhost ? `ws://localhost:9001` : "";
const DEFAULT_STREAM = isLocalhost ? `http://localhost:8081` : "";

// ── Leer desde URL params (permite compartir link preconfigurado) ──
function getFromURL(key: string): string {
  if (typeof window === "undefined") return "";
  const params = new URLSearchParams(window.location.search);
  return params.get(key) || "";
}

export interface RemoteConfig {
  mqttUrl: string;
}

interface Props {
  onConnect: (config: RemoteConfig) => void;
  currentConfig: RemoteConfig | null;
  connectionStatus: string;
}

export function getInitialConfig(): RemoteConfig | null {
  // 1. Check URL params first (for shareable links)
  const mqttParam = getFromURL("mqtt");
  if (mqttParam) {
    return {
      mqttUrl: mqttParam.startsWith("ws") ? mqttParam : `wss://${mqttParam}`,
    };
  }

  // 2. If localhost, auto-connect
  if (isLocalhost) {
    return { mqttUrl: DEFAULT_MQTT };
  }

  // 3. Otherwise, show settings panel
  return null;
}

export default function ConnectionSettings({ onConnect, currentConfig, connectionStatus }: Props) {
  const [mqttUrl, setMqttUrl] = useState(currentConfig?.mqttUrl || DEFAULT_MQTT);
  const [showPanel, setShowPanel] = useState(!currentConfig && !isLocalhost);

  // If no config and not localhost, force panel open
  useEffect(() => {
    if (!currentConfig && !isLocalhost) {
      setShowPanel(true);
    }
  }, [currentConfig]);

  const handleConnect = () => {
    const mqtt = mqttUrl.trim();
    if (!mqtt) return;
    onConnect({
      mqttUrl: mqtt.startsWith("ws") ? mqtt : `wss://${mqtt}`,
    });
    setShowPanel(false);
  };

  const statusDot = connectionStatus === "connected"
    ? "bg-emerald-500" : connectionStatus === "connecting"
    ? "bg-amber-500 animate-pulse" : "bg-red-500";

  // ── Fullscreen setup panel (when no config) ──
  if (showPanel && !currentConfig) {
    return (
      <div className="fixed inset-0 z-[100] bg-slate-950/95 backdrop-blur-xl flex items-center justify-center p-4">
        <div className="bg-slate-900 border border-slate-700 rounded-3xl shadow-2xl p-8 max-w-md w-full">
          <div className="text-center mb-6">
            <div className="text-4xl mb-3">🤖</div>
            <h2 className="text-xl font-bold text-white">UR5 Control Station</h2>
            <p className="text-slate-400 text-sm mt-2">
              Conectar al servidor del brazo robótico
            </p>
          </div>

          <div className="space-y-4">
            <div>
              <label className="block text-xs font-semibold text-slate-400 mb-1.5 tracking-wide">
                MQTT BROKER (WebSocket URL)
              </label>
              <input
                type="text"
                value={mqttUrl}
                onChange={e => setMqttUrl(e.target.value)}
                placeholder="wss://abc123.ngrok-free.app"
                className="w-full px-4 py-3 bg-slate-800 border border-slate-600 rounded-xl text-white text-sm font-mono placeholder:text-slate-600 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              />
              <p className="text-[10px] text-slate-500 mt-1">
                Pegar la URL del túnel Ngrok para el puerto 9001
              </p>
            </div>
          </div>

          <button
            onClick={handleConnect}
            disabled={!mqttUrl.trim()}
            className="w-full mt-6 py-3.5 bg-blue-600 hover:bg-blue-500 disabled:bg-slate-700 disabled:text-slate-500 text-white font-bold rounded-xl transition-colors text-sm tracking-wide"
          >
            Conectar al Robot
          </button>

          <button
            onClick={() => { onConnect({ mqttUrl: "" }); setShowPanel(false); }}
            className="w-full mt-3 py-3.5 bg-slate-800 hover:bg-slate-700 text-slate-300 font-bold rounded-xl transition-colors text-sm tracking-wide border border-slate-600 flex justify-center items-center gap-2"
          >
            <span>✨</span> Entrar en Modo Demostración (Simulado)
          </button>

          {isLocalhost && (
            <button
              onClick={() => { onConnect({ mqttUrl: DEFAULT_MQTT }); setShowPanel(false); }}
              className="w-full mt-4 py-2.5 text-slate-400 hover:text-white text-xs font-medium transition-colors"
            >
              Usar conexión local (localhost)
            </button>
          )}

          <div className="mt-6 p-3 bg-slate-800/50 rounded-xl border border-slate-700/50">
            <p className="text-[11px] text-slate-500 leading-relaxed">
              <span className="text-slate-400 font-semibold">Nota:</span> El estudiante debe ejecutar{" "}
              <code className="text-blue-400 bg-slate-800 px-1 rounded">./start.sh</code> y{" "}
              <code className="text-blue-400 bg-slate-800 px-1 rounded">./start_remote.sh</code> en su Mac para generar las URLs de Ngrok.
            </p>
          </div>
        </div>
      </div>
    );
  }

  // ── Small floating settings button (when already connected) ──
  if (!showPanel) {
    return (
      <button
        onClick={() => setShowPanel(true)}
        className="fixed bottom-4 right-4 z-50 w-10 h-10 rounded-full bg-slate-800/80 backdrop-blur-md border border-slate-700 flex items-center justify-center hover:bg-slate-700 transition-colors shadow-lg group"
        title="Configuración de conexión"
      >
        <span className={`absolute top-1 right-1 w-2.5 h-2.5 rounded-full ${statusDot} shadow-[0_0_6px_currentColor]`} />
        <svg className="w-4 h-4 text-slate-400 group-hover:text-white transition-colors" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.066 2.573c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.573 1.066c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.066-2.573c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
        </svg>
      </button>
    );
  }

  // ── Floating panel (edit existing connection) ──
  return (
    <div className="fixed inset-0 z-[100] bg-black/60 backdrop-blur-sm flex items-center justify-center p-4" onClick={() => setShowPanel(false)}>
      <div className="bg-slate-900 border border-slate-700 rounded-2xl shadow-2xl p-6 max-w-sm w-full" onClick={e => e.stopPropagation()}>
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-sm font-bold text-white">Conexión Remota</h3>
          <div className="flex items-center gap-2">
            <span className={`w-2 h-2 rounded-full ${statusDot}`} />
            <span className="text-xs text-slate-400 capitalize">{connectionStatus}</span>
          </div>
        </div>

        <div className="space-y-3">
          <div>
            <label className="block text-[10px] font-semibold text-slate-500 mb-1 tracking-wide">MQTT BROKER</label>
            <input type="text" value={mqttUrl} onChange={e => setMqttUrl(e.target.value)}
              className="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded-lg text-white text-xs font-mono focus:outline-none focus:ring-1 focus:ring-blue-500" />
          </div>
        </div>

        <div className="flex gap-2 mt-4">
          <button onClick={() => setShowPanel(false)}
            className="flex-1 py-2 text-slate-400 hover:text-white text-xs font-medium border border-slate-700 rounded-lg transition-colors">
            Cerrar
          </button>
          <button onClick={handleConnect}
            className="flex-1 py-2 bg-blue-600 hover:bg-blue-500 text-white text-xs font-bold rounded-lg transition-colors">
            Reconectar
          </button>
        </div>
      </div>
    </div>
  );
}
