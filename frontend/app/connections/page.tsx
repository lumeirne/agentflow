"use client";

import { useEffect, useCallback } from "react";
import { apiGet, apiPost } from "@/lib/auth";
import { useAppStore, ConnectedService } from "@/lib/store";
import ServiceStatus from "@/components/ServiceStatus";

export default function ConnectionsPage() {
  const { connectedServices, setConnectedServices } = useAppStore();

  const fetchConnections = useCallback(async () => {
    try {
      const data = await apiGet<ConnectedService[]>("/api/connections");
      setConnectedServices(data);
    } catch (err) {
      console.error("Failed to fetch connections:", err);
    }
  }, [setConnectedServices]);

  useEffect(() => {
    fetchConnections();
  }, [fetchConnections]);

  const handleConnect = async (provider: string) => {
    try {
      const data = await apiPost<{ redirect_url: string }>(`/api/connections/${provider}/start`);
      window.location.href = data.redirect_url;
    } catch (err) {
      console.error("Failed to start connection:", err);
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

      <ServiceStatus
        services={connectedServices}
        onConnect={handleConnect}
        onRefresh={fetchConnections}
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
