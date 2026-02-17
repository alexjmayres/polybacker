"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiFetch, apiJson } from "@/lib/api";

interface Status {
  copy_trading: string;
  arbitrage: string;
}

interface TestResult {
  status: string;
  message: string;
  error?: string;
  trader?: string;
  trade?: {
    side: string;
    market: string;
    price: number;
    size: number;
  };
  copy?: {
    copy_size_usd: number;
    order_mode: string;
    dry_run: boolean;
    limit_price?: number;
    num_shares?: number;
  };
}

export function CopyControls() {
  const queryClient = useQueryClient();
  const [testResult, setTestResult] = useState<TestResult | null>(null);

  const { data: status } = useQuery<Status>({
    queryKey: ["status"],
    queryFn: () => apiJson("/api/status"),
    refetchInterval: 5000,
  });

  const isRunning = status?.copy_trading === "running";

  const startMutation = useMutation({
    mutationFn: (dryRun: boolean) =>
      apiFetch("/api/copy/start", {
        method: "POST",
        body: JSON.stringify({ dry_run: dryRun }),
      }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["status"] }),
  });

  const stopMutation = useMutation({
    mutationFn: () => apiFetch("/api/copy/stop", { method: "POST" }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["status"] }),
  });

  const testMutation = useMutation({
    mutationFn: async () => {
      const res = await apiFetch("/api/copy/test-trade", {
        method: "POST",
        body: JSON.stringify({ live: false }),
      });
      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.error || `Test failed: ${res.status}`);
      }
      return data as TestResult;
    },
    onSuccess: (data) => {
      setTestResult(data);
      queryClient.invalidateQueries({ queryKey: ["activity-log"] });
      queryClient.invalidateQueries({ queryKey: ["copy-trades"] });
    },
    onError: (err: Error) => {
      setTestResult({
        status: "error",
        message: err.message,
        error: err.message,
      });
    },
  });

  const resultColor = (status: string) => {
    switch (status) {
      case "dry_run":
        return "text-[var(--green)]";
      case "executed":
        return "text-[var(--green)]";
      case "skipped":
        return "text-[var(--amber)]";
      case "failed":
      case "error":
        return "text-[var(--red)]";
      default:
        return "text-[var(--green-dim)]";
    }
  };

  return (
    <div className="glass rounded-none p-5">
      <h3 className="text-[10px] text-[var(--green-dark)] uppercase tracking-widest mb-4">
        // BOT CONTROLS
      </h3>
      <div className="flex flex-wrap gap-2">
        {isRunning ? (
          <button
            onClick={() => stopMutation.mutate()}
            disabled={stopMutation.isPending}
            className="flex items-center gap-2 border border-[var(--red)] text-[var(--red)] hover:bg-[var(--red)] hover:text-black disabled:opacity-50 px-4 py-2 rounded-none text-xs font-bold uppercase tracking-wider transition-colors"
          >
            [STOP]
          </button>
        ) : (
          <>
            <button
              onClick={() => startMutation.mutate(false)}
              disabled={startMutation.isPending}
              className="flex items-center gap-2 border border-[var(--green)] text-[var(--green)] hover:bg-[var(--green)] hover:text-black disabled:opacity-50 px-4 py-2 rounded-none text-xs font-bold uppercase tracking-wider transition-colors"
            >
              [START]
            </button>
            <button
              onClick={() => startMutation.mutate(true)}
              disabled={startMutation.isPending}
              className="flex items-center gap-2 border border-[var(--amber)] text-[var(--amber)] hover:bg-[var(--amber)] hover:text-black disabled:opacity-50 px-4 py-2 rounded-none text-xs font-bold uppercase tracking-wider transition-colors"
            >
              [DRY RUN]
            </button>
          </>
        )}

        {/* Test Trade button — always visible */}
        <button
          onClick={() => {
            setTestResult(null);
            testMutation.mutate();
          }}
          disabled={testMutation.isPending}
          className="flex items-center gap-2 border border-[var(--cyan)] text-[var(--cyan)] hover:bg-[var(--cyan)] hover:text-black disabled:opacity-50 px-4 py-2 rounded-none text-xs font-bold uppercase tracking-wider transition-colors"
        >
          {testMutation.isPending ? (
            <>
              TESTING<span className="blink">_</span>
            </>
          ) : (
            "[TEST TRADE]"
          )}
        </button>
      </div>

      {/* Engine status */}
      {isRunning && (
        <p className="text-xs text-[var(--green)] mt-3 mono">
          <span className="blink">&#9608;</span> COPY ENGINE ACTIVE
        </p>
      )}

      {/* Test result */}
      {testResult && (
        <div className="mt-3 border border-[var(--panel-border)] p-3">
          <div className={`text-xs mono ${resultColor(testResult.status)}`}>
            {testResult.status === "error" ? "✗ " : testResult.status === "dry_run" || testResult.status === "executed" ? "✓ " : "⚠ "}
            {testResult.message}
          </div>
          {testResult.trade && (
            <div className="mt-2 text-[10px] text-[var(--green-dim)] mono space-y-0.5">
              <div>
                TRADER: <span className="text-[var(--magenta)]">{testResult.trader}</span>
              </div>
              <div>
                SIDE: <span className={testResult.trade.side === "BUY" ? "text-[var(--green)]" : "text-[var(--red)]"}>{testResult.trade.side}</span>
                {" | "}
                PRICE: <span className="text-[var(--cyan)]">{testResult.trade.price?.toFixed(4)}</span>
                {" | "}
                SIZE: <span className="text-[var(--cyan)]">{testResult.trade.size?.toFixed(2)}</span>
              </div>
              {testResult.copy && (
                <div>
                  COPY: <span className="text-[var(--cyan)]">${testResult.copy.copy_size_usd?.toFixed(2)}</span>
                  {" | "}
                  MODE: <span className="text-[var(--amber)]">{testResult.copy.order_mode?.toUpperCase()}</span>
                  {testResult.copy.limit_price != null && (
                    <>
                      {" | "}
                      LIMIT: <span className="text-[var(--cyan)]">{testResult.copy.limit_price?.toFixed(4)}</span>
                    </>
                  )}
                </div>
              )}
            </div>
          )}
          <button
            onClick={() => setTestResult(null)}
            className="mt-2 text-[9px] text-[var(--green-dark)] hover:text-[var(--green)] uppercase tracking-wider"
          >
            [dismiss]
          </button>
        </div>
      )}
    </div>
  );
}
