import { useState, useEffect, useRef, useCallback } from "react";
import { JointData, PIDData, SensorData } from "../types";
import { useMQTT } from "./useMQTT";

const ZERO_JOINTS: JointData = { J1: 0, J2: 0, J3: 0, J4: 0, J5: 0, J6: 0 };

export function useRobotData(activeJoint: keyof JointData, brokerUrl?: string) {
  const [joints, setJoints] = useState<JointData>(ZERO_JOINTS);
  const [pid, setPid] = useState<PIDData>({ setpoint: 0, error: 0, output: 0, p: 0, i: 0, d: 0 });
  const [sensors, setSensors] = useState<SensorData>({ temp: 28, force: 0 });
  const [targetAngles, setTargetAngles] = useState<JointData>(ZERO_JOINTS);

  // targetsRef es la fuente de verdad — siempre actualizado síncronamente
  // Evita la condición de carrera donde React aún no ha aplicado setTargetAngles
  const targetsRef = useRef<JointData>({ ...ZERO_JOINTS });
  const activeJRef = useRef<keyof JointData>(activeJoint);
  const pidParamsRef = useRef({ kp: 1.0, ki: 0.1, kd: 0.05 });

  // true una vez que el usuario mueve algo — evita que clientes nuevos publiquen al conectar
  const userInteractedRef = useRef(false);
  // true después de recibir el primer mensaje de joints — sincroniza UI con posición real
  const syncedRef = useRef(false);

  // Simulation fallback refs
  const intRef = useRef<number>(0);
  const prevErr = useRef<number>(0);

  useEffect(() => { activeJRef.current = activeJoint; }, [activeJoint]);

  // ── MQTT Connection ──
  const { connectionStatus, bridgeStatus, msgRate, publishJoints, publishGripper, publishPID } =
    useMQTT({
      brokerUrl,
      onJoints: (data) => {
        const incoming = data as unknown as JointData;
        setJoints(incoming);

        // Primera vez que llegan joints: sincronizar targets con posición real del robot
        // Solo si el usuario no ha interactuado (evita sobreescribir sus comandos)
        if (!syncedRef.current && !userInteractedRef.current) {
          syncedRef.current = true;
          targetsRef.current = { ...incoming };  // actualizar ref síncronamente
          setTargetAngles({ ...incoming });       // actualizar estado para UI
        }
      },
      onPID: (data) => setPid(data as unknown as PIDData),
      onSensors: (data) => setSensors(data as unknown as SensorData),
    });

  const isConnected = connectionStatus === "connected";

  // Al desconectar sin haber interactuado → resetear sync para re-sincronizar al reconectar
  useEffect(() => {
    if (!isConnected && !userInteractedRef.current) {
      syncedRef.current = false;
    }
  }, [isConnected]);

  // ── Local Fallback Simulation (when MQTT is disconnected) ──
  useEffect(() => {
    if (isConnected) return;
    const id = setInterval(() => {
      setJoints(prev => {
        const next = { ...prev };
        for (const k of Object.keys(prev) as Array<keyof JointData>) {
          const t = targetsRef.current[k] ?? 0;
          next[k] = +(prev[k] + 0.06 * (t - prev[k]) + (Math.random() - 0.5) * 0.2).toFixed(2);
        }
        const active = activeJRef.current;
        const sp = targetsRef.current[active];
        const m = next[active];
        const err = sp - m;
        const { kp, ki, kd } = pidParamsRef.current;
        intRef.current = Math.max(-20, Math.min(20, intRef.current + err * 0.05));
        const dE = (err - prevErr.current) / 0.05;
        prevErr.current = err;
        setPid({ setpoint: sp, error: +err.toFixed(2), output: +m.toFixed(2),
          p: +(kp * err).toFixed(2), i: +(ki * intRef.current).toFixed(2),
          d: +(kd * dE).toFixed(2) });
        setSensors(s => ({
          temp: +Math.max(20, Math.min(80, s.temp + (Math.random() - 0.48) * 0.15)).toFixed(1),
          force: +Math.max(0, Math.min(20, s.force + (Math.random() - 0.5) * 0.3)).toFixed(1),
        }));
        return next;
      });
    }, 50);
    return () => clearInterval(id);
  }, [isConnected]);

  // ── Public API ──

  const setTarget = useCallback((j: keyof JointData, v: number) => {
    userInteractedRef.current = true;

    // Usar targetsRef.current (siempre actualizado) para construir el payload completo
    // Esto evita la condición de carrera con el estado de React
    const updated: JointData = { ...targetsRef.current, [j]: v };
    targetsRef.current = updated;        // actualizar ref inmediatamente (síncrono)
    setTargetAngles({ ...updated });     // actualizar UI

    if (isConnected) {
      publishJoints(updated as unknown as { [key: string]: number }, activeJRef.current);
    }
  }, [isConnected, publishJoints]);

  const setParams = useCallback((p: Partial<{ kp: number; ki: number; kd: number }>) => {
    pidParamsRef.current = { ...pidParamsRef.current, ...p };
    if (isConnected) publishPID(p);
  }, [isConnected, publishPID]);

  const setGripper = useCallback((closed: boolean) => {
    if (isConnected) publishGripper(closed);
  }, [isConnected, publishGripper]);

  return { joints, pid, sensors, targetAngles, setTarget, setParams, setGripper,
    connectionStatus, bridgeStatus, msgRate };
}
