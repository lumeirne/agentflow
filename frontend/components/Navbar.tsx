"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";

const NAV_ITEMS = [
  { path: "/",            label: "Console",     icon: "⚡" },
  { path: "/connections", label: "Connections",  icon: "🔗" },
  { path: "/approvals",   label: "Approvals",   icon: "✋" },
  { path: "/settings",    label: "Settings",    icon: "⚙️" },
];

export default function Navbar() {
  const pathname = usePathname();
  const [isAuthenticated, setIsAuthenticated] = useState<boolean | null>(null);

  useEffect(() => {
    let isMounted = true;

    fetch("/api/auth/session", { cache: "no-store" })
      .then((res) => {
        if (isMounted) {
          setIsAuthenticated(res.ok);
        }
      })
      .catch(() => {
        if (isMounted) {
          setIsAuthenticated(false);
        }
      });

    return () => {
      isMounted = false;
    };
  }, []);

  return (
    <nav className="fixed top-0 left-0 right-0 z-50 backdrop-blur-xl bg-gray-950/80 border-b border-white/5">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-16">
          {/* Logo */}
          <Link href="/" className="flex items-center gap-2 group">
            <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-blue-500 to-purple-600 flex items-center justify-center text-white font-bold text-sm group-hover:scale-110 transition-transform">
              AF
            </div>
            <span className="text-lg font-bold bg-gradient-to-r from-blue-400 to-purple-400 bg-clip-text text-transparent">
              AgentFlow
            </span>
          </Link>

          {/* Nav links */}
          <div className="flex items-center gap-2">
            {NAV_ITEMS.map((item) => {
              const isActive = pathname === item.path;
              return (
                <Link
                  key={item.path}
                  href={item.path}
                  className={`px-3 py-2 rounded-lg text-sm font-medium transition-all duration-200 ${
                    isActive
                      ? "bg-white/10 text-white"
                      : "text-gray-400 hover:text-white hover:bg-white/5"
                  }`}
                >
                  <span className="mr-1.5">{item.icon}</span>
                  {item.label}
                </Link>
              );
            })}

            {isAuthenticated !== null && (
              <a
                href={isAuthenticated ? "/api/auth/logout" : "/api/auth/login"}
                className="ml-2 px-3 py-2 rounded-lg text-sm font-medium border border-white/10 text-gray-300 hover:text-white hover:border-white/25 hover:bg-white/5 transition-all duration-200"
              >
                {isAuthenticated ? "Sign out" : "Sign in"}
              </a>
            )}
          </div>
        </div>
      </div>
    </nav>
  );
}
