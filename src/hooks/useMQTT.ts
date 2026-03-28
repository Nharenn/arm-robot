/**
 * ╔══════════════════════════════════════════════════╗
 * ║  MQTT Connection Hook                             ║
 * ║  Handles WebSocket connection to Mosquitto        ║
 * ║  broker and message pub/sub.                      ║
 * ╚══════════════════════════════════════════════════╝
 */

import { useEffect, useRef, useCallback, useState } from "react";
import mqtt, { MqttClient } from "mqtt";

// ── MQTT Topics ──
export const TOPICS = {
  CMD_JOINTS:    "ur5/cmd/joints",
  CMD_GRIPPER:   "ur5/cmd/gripper",
  CMD_PID:       "ur5/cmd/pid",
  STATE_JOINTS:  "ur5/state/joints",
  STATE_PID:     "ur5/state/pid",
  STATE_SENSORS: "ur5/state/sensors",
  STATUS:        "ur5/status",
} as const;

export type ConnectionStatus = "connecting" | "connected" | "disconnected" | "error";

export interface BridgeStatus {
  connected: boolean;
  coppelia: boolean;
  mode: "live" | "demo" | "offline";
}

interface UseMQTTOptions {
  brokerUrl?: string;
  onJoints?: (data: Record<string, number>) => void;
  onPID?: (data: Record<string, number>) => void;
  onSensors?: (data: Record<string, number>) => void;
  onStatus?: (data: BridgeStatus) => void;
}

export function useMQTT(options: UseMQTTOptions = {}) {
  const {
    brokerUrl,
    onJoints,
    onPID,
    onSensors,
    onStatus,
  } = options;

  const clientRef = useRef<MqttClient | null>(null);
  const [connectionStatus, setConnectionStatus] = useState<ConnectionStatus>("disconnected");
  const [bridgeStatus, setBridgeStatus] = useState<BridgeStatus>({
    connected: false, coppelia: false, mode: "offline"
  });
  const [msgRate, setMsgRate] = useState(0);
  const msgCountRef = useRef(0);

  // Store callbacks in refs to avoid re-subscribing
  const callbacksRef = useRef({ onJoints, onPID, onSensors, onStatus });
  callbacksRef.current = { onJoints, onPID, onSensors, onStatus };

  useEffect(() => {
    if (!brokerUrl) {
      setConnectionStatus("disconnected");
      return;
    }

    setConnectionStatus("connecting");

    const client = mqtt.connect(brokerUrl, {
      clientId: `ur5_frontend_${Math.random().toString(16).slice(2, 8)}`,
      clean: true,
      reconnectPeriod: 3000,
      connectTimeout: 5000,
    });

    clientRef.current = client;

    client.on("connect", () => {
      console.log("✅ MQTT: Connected to broker");
      setConnectionStatus("connected");

      // Subscribe to state topics from the bridge
      client.subscribe([
        TOPICS.STATE_JOINTS,
        TOPICS.STATE_PID,
        TOPICS.STATE_SENSORS,
        TOPICS.STATUS,
      ], { qos: 0 });
    });

    client.on("reconnect", () => {
      setConnectionStatus("connecting");
    });

    client.on("error", (err) => {
      console.error("❌ MQTT:", err.message);
      setConnectionStatus("error");
    });

    client.on("close", () => {
      setConnectionStatus("disconnected");
    });

    client.on("message", (topic, payload) => {
      try {
        const data = JSON.parse(payload.toString());
        msgCountRef.current++;

        switch (topic) {
          case TOPICS.STATE_JOINTS:
            callbacksRef.current.onJoints?.(data);
            break;
          case TOPICS.STATE_PID:
            callbacksRef.current.onPID?.(data);
            break;
          case TOPICS.STATE_SENSORS:
            callbacksRef.current.onSensors?.(data);
            break;
          case TOPICS.STATUS:
            setBridgeStatus(data);
            callbacksRef.current.onStatus?.(data);
            break;
        }
      } catch {
        // Ignore malformed messages
      }
    });

    // Message rate counter (updates every second)
    const rateInterval = setInterval(() => {
      setMsgRate(msgCountRef.current);
      msgCountRef.current = 0;
    }, 1000);

    return () => {
      clearInterval(rateInterval);
      client.end(true);
      clientRef.current = null;
    };
  }, [brokerUrl]);

  // ── Publish Commands ──

  const publishJoints = useCallback((targets: { [key: string]: number }, activeJoint?: string) => {
    clientRef.current?.publish(
      TOPICS.CMD_JOINTS,
      JSON.stringify({ ...targets, activeJoint }),
      { qos: 0 }
    );
  }, []);

  const publishGripper = useCallback((closed: boolean) => {
    clientRef.current?.publish(
      TOPICS.CMD_GRIPPER,
      JSON.stringify({ closed }),
      { qos: 1 }
    );
  }, []);

  const publishPID = useCallback((params: { kp?: number; ki?: number; kd?: number }) => {
    clientRef.current?.publish(
      TOPICS.CMD_PID,
      JSON.stringify(params),
      { qos: 1 }
    );
  }, []);

  return {
    connectionStatus,
    bridgeStatus,
    msgRate,
    publishJoints,
    publishGripper,
    publishPID,
  };
}
