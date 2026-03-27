"use client";

import { useEffect, useState, useCallback } from "react";
import { useParams, useRouter, useSearchParams } from "next/navigation";
import { apiGet, apiPost } from "@/lib/auth";
import { useAppStore, WorkflowRun, WorkflowStep } from "@/lib/store";
import { useWebSocket } from "@/hooks/useWebSocket";
import WorkflowTimeline from "@/components/WorkflowTimeline";
import RepoSelector from "@/components/RepoSelector";

interface RunDetail {
  run: WorkflowRun;
  steps: WorkflowStep[];
  artifacts: unknown[];
}

const RUN_STATUS_COLORS: Record<string, string> = {
  created:                "text-gray-400",
  planning:               "text-blue-400",
  running:                "text-blue-400",
  waiting_for_approval:   "text-amber-400",
  waiting_for_connection: "text-orange-400",
  completed:              "text-emerald-400",
  partially_completed:    "text-amber-400",
  failed:                 "text-red-400",
};

const PROVIDER_LABELS: Record<string, string> = {
  github: "GitHub",
  google: "Google",
  slack:  "Slack",
};

export default function RunDetailPage() {
  const params = useParams();
  const router = useRouter();
  const searchParams = useSearchParams();
  const runId = params.id as string;

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [reSubmitting, setReSubmitting] = useState(false);
  const [resumeError, setResumeError] = useState<string | null>(null);

  const {
    activeRun,
    setActiveRun,
    activeSteps,
    setActiveSteps,
    clarification,
    setClarification,
    providerRecovery,
    setProviderRecovery,
    updateProviderRecoveryPhase,
  } = useAppStore();

  useWebSocket(runId);

  // ── Initial data fetch ────────────────────────────────────────────────────
  useEffect(() => {
    const fetchRun = async () => {
      try {
        const data = await apiGet<RunDetail>(`/api/runs/${runId}`);
        setActiveRun(data.run);
        setActiveSteps(data.steps);

        // If the run is already waiting_for_connection, restore recovery state
        if (data.run.status === "waiting_for_connection") {
          const failedStep = data.steps.find((s) => s.status === "failed_recoverable");
          if (failedStep) {
            // Infer provider from step_type
            const provider = failedStep.step_type.includes("github")
              ? "github"
              : failedStep.step_type.includes("slack")
              ? "slack"
              : "google";
            setProviderRecovery({
              runId,
              provider,
              stepId: failedStep.id,
              stepKey: failedStep.step_key,
              phase: "missing_provider",
            });
          }
        }
      } catch (err: unknown) {
        setError((err as Error).message || "Failed to load run");
      } finally {
        setLoading(false);
      }
    };
    fetchRun();
  }, [runId, setActiveRun, setActiveSteps, setProviderRecovery]);

  // ── Handle callback redirect back to this run page ────────────────────────
  useEffect(() => {
    const connected = searchParams.get("connected");
    const resume = searchParams.get("resume");

    if (connected && resume === runId) {
      // Provider was just connected — auto-trigger resume
      updateProviderRecoveryPhase("connection_restored");
      // Clean URL
      router.replace(`/runs/${runId}`);
      // Trigger resume after a short delay to let the backend settle
      setTimeout(() => triggerResume(), 800);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [searchParams]);

  // ── Resume after connection ───────────────────────────────────────────────
  const triggerResume = useCallback(async () => {
    setResumeError(null);
    updateProviderRecoveryPhase("resuming_step");
    try {
      await apiPost(`/api/runs/${runId}/resume`, {});
      // WebSocket will update steps in real time; clear recovery state once run completes
    } catch (err: unknown) {
      const msg = (err as Error).message || "Failed to resume run";
      setResumeError(msg);
      updateProviderRecoveryPhase("resume_failed");
    }
  }, [runId, updateProviderRecoveryPhase]);

  // Clear recovery state when run completes or fails terminally
  useEffect(() => {
    if (
      activeRun &&
      ["completed", "partially_completed", "failed"].includes(activeRun.status)
    ) {
      setProviderRecovery(null);
    }
  }, [activeRun?.status, setProviderRecovery]);

  // ── Connect provider inline ───────────────────────────────────────────────
  const handleInlineConnect = useCallback(
    async (provider: string) => {
      setResumeError(null);
      updateProviderRecoveryPhase("connecting_provider");
      try {
        const data = await apiPost<{ redirect_url: string }>(
          `/api/connections/${provider}/start`,
          { return_to_run_id: runId }
        );
        if (data.redirect_url) {
          window.location.href = data.redirect_url;
        } else {
          setResumeError("No redirect URL returned from backend.");
          updateProviderRecoveryPhase("missing_provider");
        }
      } catch (err: unknown) {
        setResumeError((err as Error).message || "Failed to start connection");
        updateProviderRecoveryPhase("missing_provider");
      }
    },
    [runId, updateProviderRecoveryPhase]
  );

  // ── Fallback: open Connections page ──────────────────────────────────────
  const handleOpenConnectionsPage = useCallback(() => {
    router.push("/connections");
  }, [router]);

  // ── Repo selection ────────────────────────────────────────────────────────
  const handleSelectRepo = async (newPrompt: string) => {
    try {
      setReSubmitting(true);
      setClarification(null);
      const newRun = await apiPost<WorkflowRun>("/api/runs", { prompt: newPrompt });
      router.push(`/runs/${newRun.id}`);
    } catch (err: unknown) {
      setError((err as Error).message || "Failed to create new run with repository");
      setReSubmitting(false);
    }
  };

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

  return (
    <>
      {/* Repo Selector Modal */}
      {clarification && clarification.type === "repo_selection" && (
        <RepoSelector
          isOpen={true}
          originalPrompt={clarification.originalPrompt}
          onClose={() => setClarification(null)}
          onSelectRepo={handleSelectRepo}
        />
      )}

      {error ? (
        <div className="max-w-4xl mx-auto">
          <div className="p-6 rounded-xl bg-red-900/20 border border-red-500/30 text-red-300">
            {error}
          </div>
        </div>
      ) : (
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

          {/* ── Inline Provider Recovery Banner ── */}
          {providerRecovery && providerRecovery.runId === runId && (
            <div className="mb-8 rounded-xl border border-orange-500/30 bg-orange-900/20 p-5">
              <div className="flex items-start gap-3">
                <span className="text-orange-400 text-xl flex-shrink-0">🔌</span>
                <div className="flex-1">
                  {providerRecovery.phase === "missing_provider" && (
                    <>
                      <p className="text-sm font-semibold text-orange-300 mb-1">
                        {PROVIDER_LABELS[providerRecovery.provider] ?? providerRecovery.provider} connection required
                      </p>
                      <p className="text-xs text-orange-400 mb-3">
                        Step &ldquo;{providerRecovery.stepKey.replace(/_/g, " ")}&rdquo; needs access to your{" "}
                        {PROVIDER_LABELS[providerRecovery.provider] ?? providerRecovery.provider} account.
                        Connect it below — only this step will retry, no full restart needed.
                      </p>
                      {resumeError && (
                        <p className="text-xs text-red-400 mb-2">{resumeError}</p>
                      )}
                      <div className="flex gap-2 flex-wrap">
                        <button
                          onClick={() => handleInlineConnect(providerRecovery.provider)}
                          className="text-xs font-semibold px-4 py-2 rounded-lg bg-orange-500/30 text-orange-200 border border-orange-500/40 hover:bg-orange-500/40 transition-colors"
                        >
                          Connect {PROVIDER_LABELS[providerRecovery.provider] ?? providerRecovery.provider}
                        </button>
                        <button
                          onClick={handleOpenConnectionsPage}
                          className="text-xs font-semibold px-4 py-2 rounded-lg bg-gray-800 text-gray-300 border border-white/10 hover:bg-gray-700 transition-colors"
                        >
                          Open Connections page
                        </button>
                      </div>
                    </>
                  )}

                  {providerRecovery.phase === "connecting_provider" && (
                    <p className="text-sm text-orange-300">
                      Redirecting to {PROVIDER_LABELS[providerRecovery.provider] ?? providerRecovery.provider}…
                    </p>
                  )}

                  {providerRecovery.phase === "connection_restored" && (
                    <p className="text-sm text-emerald-300">
                      ✅ {PROVIDER_LABELS[providerRecovery.provider] ?? providerRecovery.provider} connected — preparing to resume…
                    </p>
                  )}

                  {providerRecovery.phase === "resuming_step" && (
                    <div className="flex items-center gap-2">
                      <div className="w-4 h-4 border-2 border-orange-400 border-t-transparent rounded-full animate-spin" />
                      <p className="text-sm text-orange-300">Resuming from failed step…</p>
                    </div>
                  )}

                  {providerRecovery.phase === "resume_failed" && (
                    <>
                      <p className="text-sm font-semibold text-red-300 mb-1">Resume failed</p>
                      {resumeError && <p className="text-xs text-red-400 mb-2">{resumeError}</p>}
                      <button
                        onClick={triggerResume}
                        className="text-xs font-semibold px-4 py-2 rounded-lg bg-red-500/20 text-red-300 border border-red-500/30 hover:bg-red-500/30 transition-colors"
                      >
                        Retry Resume
                      </button>
                    </>
                  )}
                </div>
              </div>
            </div>
          )}

          {/* Timeline */}
          <div className="mb-8">
            <h2 className="text-lg font-semibold text-white mb-4">Execution Timeline</h2>
            <WorkflowTimeline
              steps={activeSteps}
              recoverableProvider={providerRecovery?.runId === runId ? providerRecovery.provider : undefined}
              onReconnect={providerRecovery?.runId === runId ? handleInlineConnect : undefined}
            />
          </div>

          {/* Error Alert */}
          {activeRun?.status === "failed" && activeRun?.result_summary && (
            <div className="mb-8 rounded-xl border border-red-500/30 bg-red-900/20 p-6">
              <h3 className="text-sm font-semibold text-red-400 mb-2">⚠️ Workflow Failed</h3>
              <p className="text-gray-200 whitespace-pre-wrap">{activeRun.result_summary}</p>
            </div>
          )}

          {/* Result Summary */}
          {activeRun?.status !== "failed" && activeRun?.result_summary && (
            <div className="rounded-xl border border-white/10 bg-gradient-to-br from-emerald-900/20 to-emerald-800/10 p-6">
              <h3 className="text-sm font-semibold text-emerald-400 mb-3">📋 Result Summary</h3>
              <p className="text-gray-300 whitespace-pre-wrap">{activeRun.result_summary}</p>
            </div>
          )}
        </div>
      )}
    </>
  );
}
