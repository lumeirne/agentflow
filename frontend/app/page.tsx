"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { apiPost, apiGet } from "@/lib/auth";
import { useAppStore, WorkflowRun } from "@/lib/store";
import { SAMPLE_PROMPTS } from "@/lib/sample_prompts";

export default function CommandConsole() {
  const [prompt, setPrompt] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const router = useRouter();
  const { runs, setRuns } = useAppStore();

  const handleSubmit = async (text: string) => {
    if (!text.trim()) return;
    setLoading(true);
    setError(null);

    try {
      const run = await apiPost<WorkflowRun>("/api/runs", { prompt: text.trim() });
      router.push(`/runs/${run.id}`);
    } catch (err: any) {
      setError(err.message || "Failed to create run");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="max-w-4xl mx-auto">
      {/* Hero */}
      <div className="text-center mb-12">
        <h1 className="text-5xl font-bold mb-4 bg-gradient-to-r from-blue-400 via-purple-400 to-pink-400 bg-clip-text text-transparent">
          AgentFlow
        </h1>
        <p className="text-lg text-gray-400 max-w-2xl mx-auto">
          Your AI-powered productivity co-pilot. Orchestrate GitHub, Calendar, Gmail, and Slack
          with a single natural-language command.
        </p>
      </div>

      {/* Prompt Input */}
      <div className="relative group mb-8">
        <div className="absolute -inset-0.5 bg-gradient-to-r from-blue-500 to-purple-600 rounded-2xl blur opacity-20 group-hover:opacity-40 transition duration-500" />
        <div className="relative rounded-2xl bg-gray-900 border border-white/10 p-1">
          <textarea
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                handleSubmit(prompt);
              }
            }}
            placeholder='Try: "Schedule a meeting with my team about the latest PR and notify everyone on Slack"'
            rows={3}
            className="w-full bg-transparent text-white placeholder-gray-500 px-4 py-3 rounded-xl focus:outline-none resize-none text-lg"
          />
          <div className="flex justify-between items-center px-4 pb-3">
            <p className="text-xs text-gray-600">Press Enter to submit • Shift+Enter for new line</p>
            <button
              onClick={() => handleSubmit(prompt)}
              disabled={loading || !prompt.trim()}
              className="px-6 py-2 rounded-xl bg-gradient-to-r from-blue-600 to-purple-600 hover:from-blue-500 hover:to-purple-500 text-white font-medium text-sm transition-all duration-300 disabled:opacity-40 disabled:cursor-not-allowed"
            >
              {loading ? (
                <span className="flex items-center gap-2">
                  <div className="w-4 h-4 border-2 border-white/40 border-t-white rounded-full animate-spin" />
                  Processing...
                </span>
              ) : (
                "🚀 Execute"
              )}
            </button>
          </div>
        </div>
      </div>

      {error && (
        <div className="mb-6 p-4 rounded-xl bg-red-900/20 border border-red-500/30 text-red-300 text-sm">
          {error}
        </div>
      )}

      {/* Sample Prompts */}
      <div className="mb-12">
        <h3 className="text-sm font-semibold text-gray-500 uppercase tracking-wider mb-3">
          Quick Actions
        </h3>
        <div className="flex flex-wrap gap-2">
          {SAMPLE_PROMPTS.map((sp, i) => (
            <button
              key={i}
              onClick={() => setPrompt(sp)}
              className="px-3 py-1.5 rounded-full bg-gray-800/60 hover:bg-gray-700/80 border border-white/5 hover:border-white/15 text-gray-400 hover:text-white text-xs transition-all duration-200"
            >
              {sp.slice(0, 60)}...
            </button>
          ))}
        </div>
      </div>

      {/* Information Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-12">
        <div className="rounded-2xl border border-white/5 bg-gradient-to-br from-blue-900/20 to-blue-800/10 p-6">
          <div className="text-3xl mb-3">🔒</div>
          <h3 className="font-semibold text-white mb-1">Secure by Design</h3>
          <p className="text-sm text-gray-400">Tokens stored in Auth0 Token Vault — never in the app database</p>
        </div>
        <div className="rounded-2xl border border-white/5 bg-gradient-to-br from-purple-900/20 to-purple-800/10 p-6">
          <div className="text-3xl mb-3">✋</div>
          <h3 className="font-semibold text-white mb-1">Step-Up Auth</h3>
          <p className="text-sm text-gray-400">CIBA approval for high-risk actions like sending emails</p>
        </div>
        <div className="rounded-2xl border border-white/5 bg-gradient-to-br from-pink-900/20 to-pink-800/10 p-6">
          <div className="text-3xl mb-3">⚡</div>
          <h3 className="font-semibold text-white mb-1">Real-Time</h3>
          <p className="text-sm text-gray-400">Live workflow execution tracking via WebSocket</p>
        </div>
      </div>
    </div>
  );
}
