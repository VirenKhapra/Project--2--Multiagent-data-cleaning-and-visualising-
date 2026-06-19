import { useEffect } from "react";
import { websocketUrl } from "../api/client.js";

export function useWebSocket(channel, onMessage) {
  useEffect(() => {
    let socket;
    let reconnectTimer;
    let closedByEffect = false;

    const connect = () => {
      socket = new WebSocket(websocketUrl(channel));
      socket.onmessage = (event) => {
        try {
          onMessage(JSON.parse(event.data));
        } catch {
          onMessage({ event: "raw", payload: event.data });
        }
      };
      socket.onerror = () => socket.close();
      socket.onclose = () => {
        if (!closedByEffect) {
          reconnectTimer = window.setTimeout(connect, 3000);
        }
      };
    };

    connect();

    return () => {
      closedByEffect = true;
      window.clearTimeout(reconnectTimer);
      socket?.close();
    };
  }, [channel, onMessage]);
}
