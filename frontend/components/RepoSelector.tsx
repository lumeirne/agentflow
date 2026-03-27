"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { apiGet } from "@/lib/auth";

interface Repo {
  name: string;
  full_name: string;
  description?: string;
  url: string;
  updated_at: string;
}

interface RepoSelectorProps {
  isOpen: boolean;
  originalPrompt: string;
  onClose: () => void;
  onSelectRepo: (prompt: string) => void;
  githubConnected?: boolean;
}

type ErrorKind = "not_connected" | "token_expired" | "generic";

function classifyError(
  err: unknown,
  githubConnected: boolean
): { kind: ErrorKind; message: string } {
  const msg =
    err instanceof Error
      ? err.message
      : "Failed to load repositories. Please try again.";

  if (msg.toLowerCase().includes("github token not found")) {
    return {
      kind: "token_expired",
      message:
        "GitHub token not found. Reconnect GitHub and ensure repository access is granted.",
    };
  }

  if (
    msg.toLowerCase().includes("not connected") ||
    msg.toLowerCase().includes("connect your github") ||
    (err as any)?.status === 400
  ) {
    if (githubConnected) {
      return {
        kind: "token_expired",
        message:
          "GitHub is connected, but repository access is unavailable. Reconnect GitHub and make sure repository permissions are granted.",
      };
    }
    return { kind: "not_connected", message: msg };
  }

  if (
    msg.toLowerCase().includes("authorization failed") ||
    msg.toLowerCase().includes("reconnect") ||
    msg.toLowerCase().includes("token expired") ||
    msg.toLowerCase().includes("token not found") ||
    (err as any)?.status === 401
  ) {
    return {
      kind: "token_expired",
      message:
        msg.includes("401") || msg.includes("token")
          ? "Your GitHub token expired or is invalid. Please reconnect on the Connections page."
          : msg,
    };
  }

  return { kind: "generic", message: msg };
}

export default function RepoSelector({
  isOpen,
  originalPrompt,
  onClose,
  onSelectRepo,
  githubConnected = false,
}: RepoSelectorProps) {
  const router = useRouter();
  const [repos, setRepos] = useState<Repo[]>([]);
  const [loading, setLoading] = useState(true);
  const [errorKind, setErrorKind] = useState<ErrorKind | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [selectedRepo, setSelectedRepo] = useState<string | null>(null);
  const [search, setSearch] = useState("");

  useEffect(() => {
    if (!isOpen) return;

    setRepos([]);
    setSelectedRepo(null);
    setSearch("");
    setErrorKind(null);
    setErrorMessage(null);

    const fetchRepos = async () => {
      try {
        const cached = localStorage.getItem("github_repos_cache");
        if (cached) {
          try {
            const cachedRepos = JSON.parse(cached) as Repo[];
            setRepos(cachedRepos);
            setLoading(false);
          } catch {
            // Ignore a bad cache entry.
          }
        }

        setLoading(true);
        const data = await apiGet<{ repos: Repo[]; total: number }>(
          "/api/github/repos"
        );
        setRepos(data.repos);
        localStorage.setItem("github_repos_cache", JSON.stringify(data.repos));
      } catch (err: unknown) {
        const result = classifyError(err, githubConnected);
        setErrorKind(result.kind);
        setErrorMessage(result.message);
      } finally {
        setLoading(false);
      }
    };

    fetchRepos();
  }, [isOpen, githubConnected]);

  const handleSelect = () => {
    if (!selectedRepo) return;
    const repo = repos.find((r) => r.full_name === selectedRepo);
    if (!repo) return;
    const newPrompt = `${originalPrompt} (Repository: ${repo.full_name})`;
    onSelectRepo(newPrompt);
    setSelectedRepo(null);
  };

  const goToConnections = () => {
    onClose();
    router.push("/connections");
  };

  const filteredRepos = search.trim()
    ? repos.filter(
        (r) =>
          r.full_name.toLowerCase().includes(search.toLowerCase()) ||
          (r.description || "").toLowerCase().includes(search.toLowerCase())
      )
    : repos;

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
      <div className="flex max-h-[90vh] w-full max-w-2xl flex-col rounded-2xl border border-white/10 bg-gray-900 shadow-2xl">
        <div className="flex items-start justify-between border-b border-white/5 p-6">
          <div>
            <h2 className="text-xl font-bold text-white">Select a Repository</h2>
            <p className="mt-1 text-sm text-gray-400">
              Your request needs a repository. Select one to continue:
            </p>
          </div>
          <button
            onClick={onClose}
            className="ml-4 rounded-lg p-1.5 text-gray-400 transition-colors hover:bg-white/10 hover:text-white"
            aria-label="Close"
          >
            ✕
          </button>
        </div>

        <div className="flex-1 overflow-y-auto p-6">
          {loading && (
            <div className="space-y-3">
              {[1, 2, 3, 4, 5].map((i) => (
                <div key={i} className="h-16 animate-pulse rounded-lg bg-gray-800" />
              ))}
            </div>
          )}

          {!loading && errorKind === "not_connected" && (
            <div className="flex flex-col items-center px-4 py-8 text-center">
              <div className="mb-4 flex h-16 w-16 items-center justify-center rounded-2xl border border-white/10 bg-gray-800 text-3xl">
                🐙
              </div>
              <h3 className="mb-2 text-lg font-semibold text-white">
                GitHub Not Connected
              </h3>
              <p className="mb-6 max-w-sm text-sm text-gray-400">
                Connect your GitHub account first so AgentFlow can access your
                repositories. Your token is stored securely in Auth0 Token Vault.
              </p>
              <button
                onClick={goToConnections}
                className="rounded-xl bg-gradient-to-r from-blue-600 to-purple-600 px-6 py-2.5 text-sm font-medium text-white transition-all duration-300 hover:from-blue-500 hover:to-purple-500"
              >
                Go to Connections →
              </button>
            </div>
          )}

          {!loading && errorKind === "token_expired" && (
            <div className="flex flex-col items-center px-4 py-8 text-center">
              <div className="mb-4 flex h-16 w-16 items-center justify-center rounded-2xl border border-amber-500/30 bg-amber-900/30 text-3xl">
                🔑
              </div>
              <h3 className="mb-2 text-lg font-semibold text-white">
                GitHub Token Issue
              </h3>
              <p className="mb-2 max-w-sm text-sm text-gray-400">
                {errorMessage || "Your GitHub authorization needs to be renewed."}
              </p>
              <p className="mb-6 max-w-sm text-xs text-gray-500">
                Reconnect GitHub once so the app can fetch repository permissions.
              </p>
              <button
                onClick={goToConnections}
                className="rounded-xl bg-gradient-to-r from-amber-600 to-orange-600 px-6 py-2.5 text-sm font-medium text-white transition-all duration-300 hover:from-amber-500 hover:to-orange-500"
              >
                Reconnect GitHub →
              </button>
            </div>
          )}

          {!loading && errorKind === "generic" && (
            <div className="rounded-xl border border-red-500/30 bg-red-900/20 p-5">
              <p className="mb-1 text-sm font-semibold text-red-300">
                Failed to load repositories
              </p>
              <p className="text-xs text-red-400">{errorMessage}</p>
              <button
                onClick={() => {
                  setErrorKind(null);
                  setErrorMessage(null);
                  setLoading(true);
                  apiGet<{ repos: Repo[]; total: number }>("/api/github/repos")
                    .then((data) => {
                      setRepos(data.repos);
                    })
                    .catch((err: unknown) => {
                      const result = classifyError(err, githubConnected);
                      setErrorKind(result.kind);
                      setErrorMessage(result.message);
                    })
                    .finally(() => {
                      setLoading(false);
                    });
                }}
                className="mt-3 rounded-lg border border-red-500/20 bg-red-600/20 px-4 py-1.5 text-xs font-medium text-red-300 transition-colors hover:bg-red-600/40"
              >
                Retry
              </button>
            </div>
          )}

          {!loading && !errorKind && repos.length > 0 && (
            <>
              <div className="mb-4">
                <input
                  type="text"
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  placeholder="Search repositories…"
                  className="w-full rounded-xl border border-white/10 bg-gray-800 px-4 py-2 text-sm text-white placeholder-gray-500 transition-colors focus:border-blue-500/50 focus:outline-none"
                />
              </div>

              <div className="space-y-2">
                {filteredRepos.length === 0 ? (
                  <p className="py-6 text-center text-sm text-gray-500">
                    No repositories match &ldquo;{search}&rdquo;
                  </p>
                ) : (
                  filteredRepos.map((repo) => (
                    <button
                      key={repo.full_name}
                      onClick={() => setSelectedRepo(repo.full_name)}
                      className={`w-full rounded-xl border p-4 text-left transition-all duration-150 ${
                        selectedRepo === repo.full_name
                          ? "border-blue-500 bg-blue-900/20"
                          : "border-white/10 bg-gray-800/50 hover:border-white/20 hover:bg-gray-800"
                      }`}
                    >
                      <div className="flex items-start justify-between">
                        <div className="min-w-0 flex-1">
                          <p className="truncate font-semibold text-white">
                            {repo.full_name}
                          </p>
                          {repo.description && (
                            <p className="mt-0.5 truncate text-xs text-gray-400">
                              {repo.description}
                            </p>
                          )}
                          <p className="mt-1 text-xs text-gray-500">
                            Updated {new Date(repo.updated_at).toLocaleDateString()}
                          </p>
                        </div>
                        <div
                          className={`ml-3 flex h-5 w-5 flex-shrink-0 items-center justify-center rounded border transition-colors ${
                            selectedRepo === repo.full_name
                              ? "border-blue-500 bg-blue-500"
                              : "border-white/20"
                          }`}
                        >
                          {selectedRepo === repo.full_name && (
                            <span className="text-xs font-bold text-white">✓</span>
                          )}
                        </div>
                      </div>
                    </button>
                  ))
                )}
              </div>
            </>
          )}

          {!loading && !errorKind && repos.length === 0 && (
            <div className="rounded-xl border border-yellow-500/30 bg-yellow-900/20 p-5 text-center">
              <p className="mb-2 text-2xl">📭</p>
              <p className="text-sm font-semibold text-yellow-300">
                No repositories found
              </p>
              <p className="mt-1 text-xs text-yellow-400">
                Make sure you have at least one repository on GitHub.
              </p>
            </div>
          )}
        </div>

        {!loading && !errorKind && repos.length > 0 && (
          <div className="flex justify-end gap-3 border-t border-white/5 p-6">
            <button
              onClick={onClose}
              className="rounded-xl border border-white/10 bg-gray-800 px-5 py-2 text-sm font-medium text-white transition-colors hover:bg-gray-700"
            >
              Cancel
            </button>
            <button
              onClick={handleSelect}
              disabled={!selectedRepo}
              className="rounded-xl bg-gradient-to-r from-blue-600 to-purple-600 px-5 py-2 text-sm font-medium text-white transition-all duration-300 disabled:cursor-not-allowed disabled:opacity-40 hover:from-blue-500 hover:to-purple-500"
            >
              Continue with this repo
            </button>
          </div>
        )}

        {!loading && errorKind && (
          <div className="flex justify-end border-t border-white/5 p-6">
            <button
              onClick={onClose}
              className="rounded-xl border border-white/10 bg-gray-800 px-5 py-2 text-sm font-medium text-white transition-colors hover:bg-gray-700"
            >
              Close
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
