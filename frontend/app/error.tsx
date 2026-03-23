"use client";

import { useEffect } from "react";

export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    // Log the error to an error reporting service
    console.error("Global React Error Boundry Caught:", error);
  }, [error]);

  return (
    <div className="min-h-screen bg-gray-950 flex flex-col items-center justify-center p-4">
      <div className="bg-red-950/20 border border-red-500/50 rounded-xl max-w-lg w-full p-8 text-center space-y-6 shadow-2xl backdrop-blur-sm">
        <div className="mx-auto w-16 h-16 bg-red-500/20 flex items-center justify-center rounded-full text-red-400">
          <svg className="w-8 h-8" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
          </svg>
        </div>
        
        <div>
          <h2 className="text-2xl font-semibold text-gray-100 mb-2">Something went wrong!</h2>
          <p className="text-gray-400 text-sm">
            We encountered an unexpected error while rendering this page.
          </p>
        </div>

        {error.message && (
          <div className="bg-black/50 p-3 rounded text-left overflow-auto text-xs text-red-300 font-mono border border-red-900/30">
            {error.message}
          </div>
        )}

        <button
          onClick={() => reset()}
          className="bg-red-600 hover:bg-red-500 text-white px-6 py-2.5 rounded-lg font-medium transition-colors focus:ring-2 focus:ring-red-500/50 outline-none"
        >
          Try again
        </button>
      </div>
    </div>
  );
}
