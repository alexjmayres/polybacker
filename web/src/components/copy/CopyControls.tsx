"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiFetch, apiJson } from "@/lib/api";
import { useAuth } from "@/hooks/useAuth";

interface Status {
  copy_trading: string;
  arbitrage: string;
}

export function CopyControls() {
  const { isOwner } = useAuth();
  const queryClient = useQueryClient();

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

  if (!isOwner) return null;

  return (
    <div className="glass rounded-none p-5">
      <h3 className="text-[10px] text-[var(--green-dark)] uppercase tracking-widest mb-4">
        // BOT CONTROLS
      </h3>
      <div className="flex gap-2">
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
      </div>
      {isRunning && (
        <p className="text-xs text-[var(--green)] mt-3 mono">
          <span className="blink">&#9608;</span> COPY ENGINE ACTIVE
        </p>
      )}
    </div>
  );
}
