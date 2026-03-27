"use client";

import { ConnectedService } from "@/lib/store";
import { apiDelete } from "@/lib/auth";

interface ServiceStatusProps {
  services: ConnectedService[];
  onConnect: (provider: string) => void;
  onRefresh: () => void;
  connectingProvider?: string | null;
}

const PROVIDERS = [
  { key: "github", name: "GitHub",  icon: "🐙", color: "from-gray-700 to-gray-800",           border: "border-gray-600" },
  { key: "google", name: "Google",  icon: "🔵", color: "from-blue-900/40 to-blue-800/30",      border: "border-blue-500/30" },
  { key: "slack",  name: "Slack",   icon: "💬", color: "from-purple-900/40 to-purple-800/30",  border: "border-purple-500/30" },
];

export default function ServiceStatus({
  services,
  onConnect,
  onRefresh,
  connectingProvider,
}: ServiceStatusProps) {
  const getStatus = (provider: string) => {
    const svc = services.find((s) => s.provider === provider);
    return svc?.status || "disconnected";
  };

  const handleDisconnect = async (provider: string) => {
    try {
      await apiDelete(`/api/connections/${provider}`);
      onRefresh();
    } catch (err) {
      console.error("Disconnect failed:", err);
    }
  };

  return (
    <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
      {PROVIDERS.map((provider) => {
        const status = getStatus(provider.key);
        const isConnected = status === "connected";
        const isConnecting = connectingProvider === provider.key;

        return (
          <div
            key={provider.key}
            className={`rounded-2xl border ${provider.border} bg-gradient-to-br ${provider.color} p-5 transition-all duration-300 hover:scale-[1.02]`}
          >
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-3">
                <span className="text-3xl">{provider.icon}</span>
                <div>
                  <h3 className="font-semibold text-white">{provider.name}</h3>
                  <div className="flex items-center gap-1.5 mt-1">
                    <div
                      className={`w-2 h-2 rounded-full ${
                        isConnected
                          ? "bg-emerald-400 animate-pulse"
                          : status === "expired"
                          ? "bg-amber-400"
                          : "bg-gray-500"
                      }`}
                    />
                    <span
                      className={`text-xs font-medium ${
                        isConnected
                          ? "text-emerald-400"
                          : status === "expired"
                          ? "text-amber-400"
                          : "text-gray-400"
                      }`}
                    >
                      {isConnecting
                        ? "Connecting…"
                        : status.charAt(0).toUpperCase() + status.slice(1)}
                    </span>
                  </div>
                </div>
              </div>
            </div>

            {isConnected ? (
              <button
                onClick={() => handleDisconnect(provider.key)}
                className="w-full py-2 px-3 rounded-lg bg-red-600/20 hover:bg-red-600/40 text-red-300 text-sm font-medium transition-colors border border-red-500/20"
              >
                Disconnect
              </button>
            ) : (
              <button
                onClick={() => onConnect(provider.key)}
                disabled={isConnecting}
                className="w-full py-2 px-3 rounded-lg bg-white/10 hover:bg-white/20 text-white text-sm font-medium transition-colors border border-white/10 disabled:opacity-60 disabled:cursor-wait flex items-center justify-center gap-2"
              >
                {isConnecting ? (
                  <>
                    <span className="w-3.5 h-3.5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                    Connecting…
                  </>
                ) : (
                  "Connect"
                )}
              </button>
            )}
          </div>
        );
      })}
    </div>
  );
}
