"use client";

import { WorkflowStep } from "@/lib/store";
import StepCard from "./StepCard";
import ApprovalCard from "@/components/ApprovalCard";

interface WorkflowTimelineProps {
  steps: WorkflowStep[];
  recoverableProvider?: string;
  onReconnect?: (provider: string) => void;
}

export default function WorkflowTimeline({ steps, recoverableProvider, onReconnect }: WorkflowTimelineProps) {
  if (steps.length === 0) {
    return (
      <div className="text-center py-12 text-gray-500">
        <p className="text-lg">No steps yet. Submit a prompt to get started.</p>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {steps.map((step, index) => (
        <div key={step.id} className="relative">
          {/* Timeline connector */}
          {index < steps.length - 1 && (
            <div className="absolute left-7 top-16 bottom-0 w-0.5 bg-white/10 -mb-3" />
          )}

          <StepCard
            step={step}
            recoverableProvider={step.status === "failed_recoverable" ? recoverableProvider : undefined}
            onReconnect={onReconnect}
          />

          {/* Inline approval card when step is awaiting approval */}
          {step.status === "awaiting_approval" && (
            <div className="ml-12 mt-2">
              <ApprovalCard stepId={step.id} runId={step.run_id} />
            </div>
          )}
        </div>
      ))}
    </div>
  );
}
