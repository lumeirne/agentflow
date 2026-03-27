"use client";

import { useEffect, useCallback, useState } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import { apiGet, apiPost } from "@/lib/auth";
import { useAppStore, ConnectedService } from "@/lib/store";
import ServiceStatus from "@/components/ServiceStatus";

export default function ConnectionsPage() {
  const { connectedServices, setConnectedServices } = useAppStore();
  const [connectError, setConnectError] = useState<string | null>(null);
  const [connectSuccess, setConnectSuccess] = useState<string | null>(null);
  const [connectingProvider, setConnectingProvider] = useState<string | null>(null);
  const searchParams = useSearchParams();
  const router = useRouter();

  const fetchConnections = useCallback(async () => {
    try {
      const data = await apiGet<ConnectedService[]>("/api/connections");
      setConnectedServices(data);
    } catch (err: any) {
      console.error("Failed to fetch connections:", err);
    }
  }, [setConnectedServices]);

  useEffect(() => {
    fetchConnections();
  }, [fetchConnections]);

  // Read OAuth callback result from URL query params
  useEffect(() => {
    const connected = searchParams.get("connected");
    const error = searchParams.get("error");
    const resume = searchParams.get("resume");

    if (connected) {
      setConnectSuccess(`${connected.charAt(0).toUpperCase() + connected.slice(1)} connected successfully!`);
      setTimeout(() => setConnectSuccess(null), 5000);
      fetchConnections();

      // If this connection was triggered from a run page, redirect back there
      if (resume) {
        router.replace(`/runs/${resume}?connected=${connected}&resume=${resume}`);
        return;
      }
    }
    if (error) {
      setConnectError(decodeURIComponent(error));
    }
    if (connected || error) {
      router.replace("/connections");
    }
  }, [searchParams, router, fetchConnections]);

  const handleConnect = async (provider: string) => {
    setConnectError(null);
    setConnectingProvider(provider);
    try {
      const data = await apiPost<{ redirect_url: string }>(
        `/api/connections/${provider}/start`
      );
      if (data.redirect_url) {
        window.location.href = data.redirect_url;
      } else {
        setConnectError("No redirect URL returned. Check your Auth0 Token Vault configuration.");
      }
    } catch (err: any) {
      const msg: string = err?.message || "Failed to start connection";
      if (msg.includes("502") || msg.toLowerCase().includes("backend")) {
        setConnectError(
          "Cannot reach the backend server. Make sure it is running at localhost:8000."
        );
      } else {
        setConnectError(msg);
      }
    } finally {
      setConnectingProvider(null);
    }
  };

  return (
    <div className="max-w-4xl mx-auto">
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-white mb-2">Connected Services</h1>
        <p className="text-gray-400">
          Connect your accounts to let AgentFlow orchestrate actions across services.
          Tokens are stored securely in Auth0 Token Vault.
        </p>
      </div>

      {/* Connection error banner */}
      {connectError && (
        <div className="mb-6 flex items-start gap-3 rounded-xl border border-red-500/30 bg-red-900/20 p-4">
          <span className="text-red-400 text-lg flex-shrink-0">⚠️</span>
          <div className="flex-1">
            <p className="text-sm font-semibold text-red-300">Connection failed</p>
            <p className="text-xs text-red-400 mt-0.5">{connectError}</p>
          </div>
          <button
            onClick={() => setConnectError(null)}
            className="text-red-400 hover:text-red-200 text-sm flex-shrink-0"
          >
            ✕
          </button>
        </div>
      )}

      {/* Connection success banner */}
      {connectSuccess && (
        <div className="mb-6 flex items-center gap-3 rounded-xl border border-emerald-500/30 bg-emerald-900/20 p-4">
          <span className="text-emerald-400 text-lg">✅</span>
          <p className="text-sm font-semibold text-emerald-300">{connectSuccess}</p>
        </div>
      )}

      <ServiceStatus
        services={connectedServices}
        onConnect={handleConnect}
        onRefresh={fetchConnections}
        connectingProvider={connectingProvider}
      />

      {/* Permission Matrix */}
      <div className="mt-12">
        <h2 className="text-lg font-semibold text-white mb-4">Permission Matrix</h2>
        <div className="rounded-2xl border border-white/5 bg-gray-900/50 overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-white/5">
                <th className="px-4 py-3 text-left text-gray-400 font-medium">Action</th>
                <th className="px-4 py-3 text-center text-gray-400 font-medium">Risk</th>
                <th className="px-4 py-3 text-center text-gray-400 font-medium">Approval</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-white/5">
              {[
                { action: "Read GitHub PRs",              risk: "Low",    approval: "Automatic" },
                { action: "Check calendar availability",  risk: "Low",    approval: "Automatic" },
                { action: "Create email draft",           risk: "Low",    approval: "Automatic" },
                { action: "Post to Slack channel",        risk: "Medium", approval: "In-App" },
                { action: "Create calendar event",        risk: "High",   approval: "CIBA / In-App" },
                { action: "Send email",                   risk: "High",   approval: "CIBA / In-App" },
                { action: "Send Slack DM",                risk: "High",   approval: "CIBA / In-App" },
              ].map((row, i) => (
                <tr key={i} className="hover:bg-white/[0.02]">
                  <td className="px-4 py-3 text-gray-300">{row.action}</td>
                  <td className="px-4 py-3 text-center">
                    <span className={`text-xs font-semibold px-2 py-0.5 rounded-full ${
                      row.risk === "Low" ? "bg-emerald-900/30 text-emerald-400" :
                      row.risk === "Medium" ? "bg-amber-900/30 text-amber-400" :
                      "bg-red-900/30 text-red-400"
                    }`}>
                      {row.risk}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-center text-gray-400">{row.approval}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
