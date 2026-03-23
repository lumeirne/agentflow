"use client";

import { WorkflowStep } from "@/lib/store";

interface StepCardProps {
  step: WorkflowStep;
}

const STATUS_STYLES: Record<string, { bg: string; text: string; label: string }> = {
  pending:            { bg: "bg-gray-800/50",    text: "text-gray-400",   label: "Pending" },
  running:            { bg: "bg-blue-900/30",    text: "text-blue-400",   label: "Running" },
  awaiting_approval:  { bg: "bg-amber-900/30",   text: "text-amber-400",  label: "Awaiting Approval" },
  completed:          { bg: "bg-emerald-900/30", text: "text-emerald-400", label: "Completed" },
  failed:             { bg: "bg-red-900/30",     text: "text-red-400",    label: "Failed" },
  skipped:            { bg: "bg-gray-800/30",    text: "text-gray-500",   label: "Skipped" },
};

const SERVICE_ICONS: Record<string, string> = {
  github:   "🐙",
  google:   "📅",
  gmail:    "📧",
  slack:    "💬",
  calendar: "📅",
  llm:      "🤖",
  identity: "👤",
};

function getServiceIcon(stepType: string): string {
  if (stepType.includes("github")) return SERVICE_ICONS.github;
  if (stepType.includes("calendar")) return SERVICE_ICONS.calendar;
  if (stepType.includes("gmail")) return SERVICE_ICONS.gmail;
  if (stepType.includes("slack")) return SERVICE_ICONS.slack;
  if (stepType.includes("llm")) return SERVICE_ICONS.llm;
  if (stepType.includes("identity")) return SERVICE_ICONS.identity;
  return "⚡";
}

function formatStepName(stepKey: string): string {
  return stepKey
    .replace(/_/g, " ")
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

export default function StepCard({ step }: StepCardProps) {
  const style = STATUS_STYLES[step.status] || STATUS_STYLES.pending;
  const icon = getServiceIcon(step.step_type);

  return (
    <div className={`rounded-xl border border-white/10 p-4 ${style.bg} transition-all duration-300`}>
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <span className="text-2xl">{icon}</span>
          <div>
            <h4 className="font-medium text-white">{formatStepName(step.step_key)}</h4>
            <p className="text-xs text-gray-400 mt-0.5">
              Risk: <span className={`font-semibold ${
                step.risk_tier === "high" ? "text-red-400" :
                step.risk_tier === "medium" ? "text-amber-400" : "text-emerald-400"
              }`}>{step.risk_tier.toUpperCase()}</span>
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          {step.status === "running" && (
            <div className="w-4 h-4 border-2 border-blue-400 border-t-transparent rounded-full animate-spin" />
          )}
          <span className={`text-xs font-semibold px-2.5 py-1 rounded-full ${style.bg} ${style.text} border border-current/20`}>
            {style.label}
          </span>
        </div>
      </div>

      {step.error_text && (
        <div className="mt-3 p-2 rounded-lg bg-red-900/20 border border-red-500/20">
          <p className="text-xs text-red-300">{step.error_text}</p>
        </div>
      )}
    </div>
  );
}
