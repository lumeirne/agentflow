"use client";

import { useAppStore } from "@/lib/store";
import { useApproval } from "@/hooks/useApproval";
import ApprovalCard from "@/components/ApprovalCard";

export default function ApprovalsPage() {
  const { pendingApprovals } = useAppStore();
  useApproval();

  return (
    <div className="max-w-4xl mx-auto">
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-white mb-2">Pending Approvals</h1>
        <p className="text-gray-400">
          Review and approve high-risk actions before AgentFlow executes them.
        </p>
      </div>

      {pendingApprovals.length === 0 ? (
        <div className="text-center py-16 rounded-2xl border border-white/5 bg-gray-900/30">
          <div className="text-5xl mb-4">✅</div>
          <p className="text-lg text-gray-400">No pending approvals</p>
          <p className="text-sm text-gray-600 mt-1">All clear! New approvals will appear here automatically.</p>
        </div>
      ) : (
        <div className="space-y-4">
          {pendingApprovals.map((approval) => (
            <ApprovalCard
              key={approval.id}
              stepId={approval.step_id}
              runId={approval.run_id}
            />
          ))}
        </div>
      )}
    </div>
  );
}
