/**
 * ╔══════════════════════════════════════════════════╗
 * ║  Robot Data Hook — MQTT-Connected                 ║
 * ║                                                   ║
 * ║  Receives real-time joint positions, PID state,   ║
 * ║  and sensor data from the Python bridge via MQTT. ║
 * ║  Sends control commands back to CoppeliaSim.      ║
 * ║                                                   ║
 * ║  Falls back to local simulation if MQTT is down.  ║
 * ╚══════════════════════════════════════════════════╝
 */

import { useState, useEffect, useRef, useCallback } from "react";
import { JointData, PIDData, SensorData } from "../types";
import { useMQTT, ConnectionStatus, BridgeStatus } from "./useMQTT";

export function useRobotData(activeJoint: keyof JointData, brokerUrl?: string) {
  const [joints, setJoints] = useState<JointData>({ J1: 0, J2: 0, J3: 0, J4: 0, J5: 0, J6: 0 });
  const [pid, setPid] = useState<PIDData>({ setpoint: 45, error: 0, output: 0, p: 0, i: 0, d: 0 });
  const [sensors, setSensors] = useState<SensorData>({ temp: 28, force: 0 });
  const [targetAngles, setTargetAngles] = useState<JointData>({ J1: 10, J2: 45, J3: -30, J4: 15, J5: 0, J6: 0 });

  const targetsRef = useRef<JointData>(targetAngles);
  const activeJRef = useRef<keyof JointData>(activeJoint);
  const pidParamsRef = useRef({ kp: 2, ki: 0.5, kd: 0.1 });
  // Solo publicar cuando el usuario mueve algo — evita que dos clientes se pisen al conectar
  const userInteractedRef = useRef(false);

  // For local fallback simulation
  const intRef = useRef<number>(0);
  const prevErr = useRef<number>(0);

  useEffect(() => { targetsRef.current = targetAngles; }, [targetAngles]);
  useEffect(() => { activeJRef.current = activeJoint; }, [activeJoint]);

  // ── MQTT Connection ──
  const {
    connectionStatus,
    bridgeStatus,
    msgRate,
    publishJoints,
    publishGripper,
    publishPID,
  } = useMQTT({
    brokerUrl,
    onJoints: (data) => {
      setJoints(data as unknown as JointData);
    },
    onPID: (data) => {
      setPid(data as unknown as PIDData);
    },
    onSensors: (data) => {
      setSensors(data as unknown as SensorData);
    },
  });

  const isConnected = connectionStatus === "connected";

  // ── Send targets to bridge solo cuando el usuario interactuó activamente ──
  // Evita que un segundo cliente publique sus valores por defecto al conectar
  useEffect(() => {
    if (isConnected && userInteractedRef.current) {
      publishJoints({ ...targetAngles }, activeJoint);
    }
  }, [targetAngles, activeJoint, isConnected, publishJoints]);

  // ── Local Fallback Simulation (when MQTT is disconnected) ──
  useEffect(() => {
    if (isConnected) return; // Don't run simulation when MQTT is active

    const id = setInterval(() => {
      setJoints(prev => {
        const next = { ...prev };
        for (const k of Object.keys(prev) as Array<keyof JointData>) {
          const t = targetsRef.current[k] ?? 0;
          next[k] = +(prev[k] + 0.06 * (t - prev[k]) + (Math.random() - 0.5) * 0.2).toFixed(2);
        }

        const currentActive = activeJRef.current;
        const sp = targetsRef.current[currentActive];
        const m = next[currentActive];
        const err = sp - m;
        const { kp, ki, kd } = pidParamsRef.current;

        intRef.current = Math.max(-50, Math.min(50, intRef.current + err * 0.05));
        const dE = (err - prevErr.current) / 0.05;
        prevErr.current = err;

        setPid({
          setpoint: sp,
          error: +err.toFixed(2),
          output: +m.toFixed(2),
          p: +(kp * err).toFixed(2),
          i: +(ki * intRef.current).toFixed(2),
          d: +(kd * dE).toFixed(2),
        });

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
    userInteractedRef.current = true; // marcar que el usuario movió algo
    setTargetAngles(p => {
      const updated = { ...p, [j]: v };
      if (isConnected) {
        publishJoints(updated, activeJRef.current);
      }
      return updated;
    });
  }, [isConnected, publishJoints]);

  const setParams = useCallback((p: Partial<{ kp: number; ki: number; kd: number }>) => {
    pidParamsRef.current = { ...pidParamsRef.current, ...p };
    // Send PID params to bridge
    if (isConnected) {
      publishPID(p);
    }
  }, [isConnected, publishPID]);

  const setGripper = useCallback((closed: boolean) => {
    if (isConnected) {
      publishGripper(closed);
    }
  }, [isConnected, publishGripper]);

  return {
    joints,
    pid,
    sensors,
    targetAngles,
    setTarget,
    setParams,
    setGripper,
    // Connection info for UI
    connectionStatus,
    bridgeStatus,
    msgRate,
  };
}
