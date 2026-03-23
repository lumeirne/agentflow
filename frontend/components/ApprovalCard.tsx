"use client";

import { useState } from "react";
import { useAppStore } from "@/lib/store";
import { apiPost } from "@/lib/auth";

interface ApprovalCardProps {
  stepId: string;
  runId: string;
}

export default function ApprovalCard({ stepId, runId }: ApprovalCardProps) {
  const { pendingApprovals, removeApproval, updateStep } = useAppStore();
  const [loading, setLoading] = useState(false);

  const approval = pendingApprovals.find((a) => a.step_id === stepId);

  if (!approval) {
    return (
      <div className="rounded-xl border border-amber-500/30 bg-amber-900/10 p-4">
        <div className="flex items-center gap-2 text-amber-400">
          <div className="w-4 h-4 border-2 border-amber-400 border-t-transparent rounded-full animate-spin" />
          <span className="text-sm font-medium">Waiting for out-of-band approval...</span>
        </div>
      </div>
    );
  }

  let preview: Record<string, any> = {};
  try {
    preview = approval.preview_json ? JSON.parse(approval.preview_json) : {};
  } catch {
    // ignore
  }

  const handleAction = async (action: "approve" | "reject") => {
    setLoading(true);
    try {
      await apiPost(`/api/approvals/${approval.id}/${action}`);
      removeApproval(approval.id);
      updateStep(stepId, {
        status: action === "approve" ? "running" : "skipped",
      });
    } catch (err) {
      console.error(`Failed to ${action}:`, err);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="rounded-xl border border-amber-500/30 bg-gradient-to-br from-amber-900/20 to-orange-900/10 p-5">
      <h4 className="text-sm font-semibold text-amber-300 mb-3">⚠️ Approval Required</h4>

      {/* Preview */}
      <div className="rounded-lg bg-black/30 p-3 mb-4 text-sm text-gray-300 font-mono">
        <p><span className="text-gray-500">Action:</span> {String(preview.action || "Unknown")}</p>
        <p><span className="text-gray-500">Risk:</span> {String(preview.risk_tier || "unknown").toUpperCase()}</p>
        {preview.preview && (
          <pre className="mt-2 text-xs overflow-auto max-h-32">
            {JSON.stringify(preview.preview as any, null, 2)}
          </pre>
        )}
      </div>

      {/* Actions */}
      <div className="flex gap-3">
        <button
          onClick={() => handleAction("approve")}
          disabled={loading}
          className="flex-1 py-2 px-4 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white font-medium text-sm transition-colors disabled:opacity-50"
        >
          ✓ Approve
        </button>
        <button
          onClick={() => handleAction("reject")}
          disabled={loading}
          className="flex-1 py-2 px-4 rounded-lg bg-red-600/80 hover:bg-red-500 text-white font-medium text-sm transition-colors disabled:opacity-50"
        >
          ✗ Reject
        </button>
      </div>
    </div>
  );
}
