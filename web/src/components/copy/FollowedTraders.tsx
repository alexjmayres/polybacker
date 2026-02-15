"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { apiJson, apiFetch } from "@/lib/api";

interface Trader {
  address: string;
  alias: string;
  total_copied: number;
  total_spent: number;
  added_at: string;
}

export function FollowedTraders() {
  const [newAddress, setNewAddress] = useState("");
  const [newAlias, setNewAlias] = useState("");
  const queryClient = useQueryClient();

  const { data: traders = [] } = useQuery<Trader[]>({
    queryKey: ["copy-traders"],
    queryFn: () => apiJson("/api/copy/traders"),
    refetchInterval: 15000,
  });

  const addMutation = useMutation({
    mutationFn: async () => {
      const res = await apiFetch("/api/copy/traders", {
        method: "POST",
        body: JSON.stringify({ address: newAddress, alias: newAlias }),
      });
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.error);
      }
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["copy-traders"] });
      setNewAddress("");
      setNewAlias("");
    },
  });

  const removeMutation = useMutation({
    mutationFn: async (address: string) => {
      await apiFetch(`/api/copy/traders/${address}`, { method: "DELETE" });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["copy-traders"] });
    },
  });

  const truncate = (addr: string) =>
    `${addr.slice(0, 8)}...${addr.slice(-6)}`;

  return (
    <div className="glass rounded-none p-5">
      <h3 className="text-[10px] text-[var(--green-dark)] uppercase tracking-widest mb-4">
        // FOLLOWED TRADERS
      </h3>

      {/* Add trader form */}
      <div className="flex gap-2 mb-4">
        <input
          type="text"
          placeholder="0x... address"
          value={newAddress}
          onChange={(e) => setNewAddress(e.target.value)}
          className="flex-1 bg-transparent border border-[var(--panel-border)] rounded-none px-3 py-2 text-xs mono text-[var(--green)] focus:outline-none focus:border-[var(--green)]"
        />
        <input
          type="text"
          placeholder="alias"
          value={newAlias}
          onChange={(e) => setNewAlias(e.target.value)}
          className="w-20 bg-transparent border border-[var(--panel-border)] rounded-none px-3 py-2 text-xs text-[var(--green)] focus:outline-none focus:border-[var(--green)]"
        />
        <button
          onClick={() => addMutation.mutate()}
          disabled={!newAddress || addMutation.isPending}
          className="border border-[var(--cyan)] text-[var(--cyan)] hover:bg-[var(--cyan)] hover:text-black disabled:opacity-30 px-3 py-2 rounded-none text-xs font-bold transition-colors"
        >
          [+]
        </button>
      </div>

      {addMutation.isError && (
        <p className="text-xs text-[var(--red)] mb-2 mono">
          ERR: {addMutation.error?.message}
        </p>
      )}

      {/* Trader list */}
      <div className="space-y-1 max-h-64 overflow-y-auto">
        {traders.length === 0 ? (
          <p className="mono text-sm text-[var(--green-dark)] text-center py-4">
            no traders followed
          </p>
        ) : (
          traders.map((trader) => (
            <div
              key={trader.address}
              className="flex items-center justify-between bg-[rgba(0,255,65,0.02)] border border-[rgba(0,255,65,0.08)] px-3 py-2 slide-up"
            >
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <span className="mono text-sm text-[var(--cyan)]">
                    {truncate(trader.address)}
                  </span>
                  {trader.alias && (
                    <span className="text-[10px] text-[var(--green-dim)]">
                      ({trader.alias})
                    </span>
                  )}
                </div>
                <div className="text-[10px] text-[var(--green-dark)] mono">
                  {trader.total_copied} trades // ${trader.total_spent.toFixed(2)} spent
                </div>
              </div>
              <button
                onClick={() => removeMutation.mutate(trader.address)}
                className="text-[var(--green-dark)] hover:text-[var(--red)] px-2 text-xs font-bold transition-colors"
              >
                [x]
              </button>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
