"use client";

import { useEffect, useRef, useCallback } from "react";
import { useAppStore } from "@/lib/store";
import { apiGet } from "@/lib/auth";

/**
 * Polling fallback for approvals when WebSocket is disconnected.
 */
export function useApproval(pollInterval = 5000) {
  const { setPendingApprovals } = useAppStore();
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const fetchApprovals = useCallback(async () => {
    try {
      const approvals = await apiGet<any[]>("/api/approvals");
      setPendingApprovals(
        approvals.map((a) => ({
          id: a.id,
          run_id: a.run_id,
          step_id: a.step_id,
          approval_type: a.approval_type,
          preview_json: a.preview_json,
          status: a.status,
        }))
      );
    } catch {
      // Silently fail — WebSocket is the primary mechanism
    }
  }, [setPendingApprovals]);

  useEffect(() => {
    fetchApprovals();
    intervalRef.current = setInterval(fetchApprovals, pollInterval);

    return () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
      }
    };
  }, [fetchApprovals, pollInterval]);
}
