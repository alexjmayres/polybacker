"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { apiJson, apiFetch } from "@/lib/api";

interface StatusData {
  fund_manager?: string;
}

export function FundControls() {
  const [newName, setNewName] = useState("");
  const [newDesc, setNewDesc] = useState("");
  const queryClient = useQueryClient();

  const { data: status } = useQuery<StatusData>({
    queryKey: ["status"],
    queryFn: () => apiJson("/api/status"),
    refetchInterval: 5000,
  });

  const isRunning = status?.fund_manager === "running";

  const createMutation = useMutation({
    mutationFn: async () => {
      const res = await apiFetch("/api/funds", {
        method: "POST",
        body: JSON.stringify({ name: newName, description: newDesc }),
      });
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.error);
      }
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["funds"] });
      setNewName("");
      setNewDesc("");
    },
  });

  const engineMutation = useMutation({
    mutationFn: async (action: "start" | "stop") => {
      const res = await apiFetch(`/api/funds/engine/${action}`, {
        method: "POST",
        body: JSON.stringify({}),
      });
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.error);
      }
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["status"] });
    },
  });

  return (
    <div className="glass rounded-none p-5">
      <h3 className="text-[10px] text-[var(--green-dark)] uppercase tracking-widest mb-4">
        // FUND CONTROLS
      </h3>

      {/* Engine controls */}
      <div className="flex gap-2 mb-4">
        {!isRunning ? (
          <button
            onClick={() => engineMutation.mutate("start")}
            disabled={engineMutation.isPending}
            className="flex-1 border border-[var(--green)] text-[var(--green)] hover:bg-[var(--green)] hover:text-black disabled:opacity-30 py-2 px-3 rounded-none text-xs font-bold transition-colors"
          >
            [START FUND ENGINE]
          </button>
        ) : (
          <button
            onClick={() => engineMutation.mutate("stop")}
            disabled={engineMutation.isPending}
            className="flex-1 border border-[var(--red)] text-[var(--red)] hover:bg-[var(--red)] hover:text-black disabled:opacity-30 py-2 px-3 rounded-none text-xs font-bold transition-colors"
          >
            [STOP FUND ENGINE]
          </button>
        )}
      </div>

      {isRunning && (
        <div className="text-xs text-[var(--green)] mono mb-4 flex items-center gap-2">
          <span className="w-2 h-2 bg-[var(--green)] animate-pulse" />
          FUND ENGINE ACTIVE
        </div>
      )}

      {/* Create fund form */}
      <div className="border-t border-[var(--panel-border)] pt-4">
        <div className="text-[10px] text-[var(--green-dark)] uppercase tracking-widest mb-2">
          CREATE NEW FUND
        </div>
        <div className="space-y-2">
          <input
            type="text"
            placeholder="Fund name"
            value={newName}
            onChange={(e) => setNewName(e.target.value)}
            className="w-full bg-transparent border border-[var(--panel-border)] rounded-none px-3 py-2 text-xs mono text-[var(--green)] focus:outline-none focus:border-[var(--green)]"
          />
          <input
            type="text"
            placeholder="Description (optional)"
            value={newDesc}
            onChange={(e) => setNewDesc(e.target.value)}
            className="w-full bg-transparent border border-[var(--panel-border)] rounded-none px-3 py-2 text-xs mono text-[var(--green)] focus:outline-none focus:border-[var(--green)]"
          />
          <button
            onClick={() => createMutation.mutate()}
            disabled={!newName || createMutation.isPending}
            className="w-full border border-[var(--cyan)] text-[var(--cyan)] hover:bg-[var(--cyan)] hover:text-black disabled:opacity-30 py-2 px-3 rounded-none text-xs font-bold transition-colors"
          >
            [CREATE FUND]
          </button>
          {createMutation.isError && (
            <p className="text-xs text-[var(--red)] mono">
              ERR: {createMutation.error?.message}
            </p>
          )}
        </div>
      </div>
    </div>
  );
}
