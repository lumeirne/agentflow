"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { apiGet } from "@/lib/auth";
import { useAppStore, WorkflowRun, WorkflowStep } from "@/lib/store";
import { useWebSocket } from "@/hooks/useWebSocket";
import WorkflowTimeline from "@/components/WorkflowTimeline";

interface RunDetail {
  run: WorkflowRun;
  steps: WorkflowStep[];
  artifacts: any[];
}

export default function RunDetailPage() {
  const params = useParams();
  const runId = params.id as string;
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const { activeRun, setActiveRun, activeSteps, setActiveSteps } = useAppStore();

  // Connect WebSocket for real-time updates
  useWebSocket(runId);

  useEffect(() => {
    const fetchRun = async () => {
      try {
        const data = await apiGet<RunDetail>(`/api/runs/${runId}`);
        setActiveRun(data.run);
        setActiveSteps(data.steps);
      } catch (err: any) {
        setError(err.message || "Failed to load run");
      } finally {
        setLoading(false);
      }
    };

    fetchRun();
  }, [runId, setActiveRun, setActiveSteps]);

  if (loading) {
    return (
      <div className="max-w-4xl mx-auto">
        <div className="animate-pulse space-y-4">
          <div className="h-8 bg-gray-800 rounded-lg w-1/3" />
          <div className="h-20 bg-gray-800 rounded-xl" />
          <div className="h-16 bg-gray-800 rounded-xl" />
          <div className="h-16 bg-gray-800 rounded-xl" />
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="max-w-4xl mx-auto">
        <div className="p-6 rounded-xl bg-red-900/20 border border-red-500/30 text-red-300">
          {error}
        </div>
      </div>
    );
  }

  const RUN_STATUS_COLORS: Record<string, string> = {
    created: "text-gray-400",
    planning: "text-blue-400",
    running: "text-blue-400",
    waiting_for_approval: "text-amber-400",
    completed: "text-emerald-400",
    partially_completed: "text-amber-400",
    failed: "text-red-400",
  };

  return (
    <div className="max-w-4xl mx-auto">
      {/* Run Header */}
      <div className="mb-8">
        <div className="flex items-center gap-3 mb-2">
          <h1 className="text-2xl font-bold text-white">Workflow Run</h1>
          {activeRun && (
            <span className={`text-sm font-semibold px-3 py-1 rounded-full bg-gray-800 ${
              RUN_STATUS_COLORS[activeRun.status] || "text-gray-400"
            }`}>
              {activeRun.status.replace(/_/g, " ").toUpperCase()}
            </span>
          )}
        </div>
        {activeRun && (
          <div className="rounded-xl border border-white/5 bg-gray-900/50 p-4">
            <p className="text-gray-300 font-medium">&ldquo;{activeRun.prompt}&rdquo;</p>
            <p className="text-xs text-gray-500 mt-2">
              Started: {new Date(activeRun.created_at).toLocaleString()}
            </p>
          </div>
        )}
      </div>

      {/* Timeline */}
      <div className="mb-8">
        <h2 className="text-lg font-semibold text-white mb-4">Execution Timeline</h2>
        <WorkflowTimeline steps={activeSteps} />
      </div>

      {/* Result Summary */}
      {activeRun?.result_summary && (
        <div className="rounded-xl border border-white/10 bg-gradient-to-br from-emerald-900/20 to-emerald-800/10 p-6">
          <h3 className="text-sm font-semibold text-emerald-400 mb-3">📋 Result Summary</h3>
          <p className="text-gray-300 whitespace-pre-wrap">{activeRun.result_summary}</p>
        </div>
      )}
    </div>
  );
}
