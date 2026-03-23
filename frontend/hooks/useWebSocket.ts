"use client";

import { useEffect, useRef, useCallback } from "react";
import { RunWebSocket } from "@/lib/websocket";
import { useAppStore } from "@/lib/store";

/**
 * Hook that manages WebSocket connection lifecycle for a workflow run.
 * Dispatches events to the Zustand store automatically.
 */
export function useWebSocket(runId: string | null) {
  const wsRef = useRef<RunWebSocket | null>(null);
  const { updateStep, addApproval, setActiveRun, activeRun } = useAppStore();

  const connect = useCallback(
    (id: string) => {
      const ws = new RunWebSocket();

      ws.onStepUpdate((event) => {
        if (event.step_id) {
          updateStep(event.step_id, { status: event.status || "running" });
        }
      });

      ws.onApprovalRequired((event) => {
        if (event.step_id) {
          updateStep(event.step_id, { status: "awaiting_approval" });
        }
        addApproval({
          id: event.data.approval_id,
          run_id: event.run_id,
          step_id: event.step_id,
          approval_type: "in_app",
          preview_json: JSON.stringify(event.data.preview),
          status: "pending",
        });
      });

      ws.onRunComplete((event) => {
        if (activeRun && activeRun.id === event.run_id) {
          setActiveRun({
            ...activeRun,
            status: event.status,
            result_summary: event.data.summary,
          });
        }
      });

      ws.onError((event) => {
        console.error("Run error:", event.data.message);
      });

      ws.connect(id);
      wsRef.current = ws;
    },
    [updateStep, addApproval, setActiveRun, activeRun]
  );

  useEffect(() => {
    if (runId) {
      connect(runId);
    }

    return () => {
      wsRef.current?.disconnect();
      wsRef.current = null;
    };
  }, [runId, connect]);

  return wsRef.current;
}
