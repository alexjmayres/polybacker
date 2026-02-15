"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { apiJson, apiFetch } from "@/lib/api";

interface WhitelistEntry {
  address: string;
  added_by: string;
  added_at: string;
}

interface WhitelistSettings {
  enabled: boolean;
}

export function WhitelistPanel() {
  const [newAddress, setNewAddress] = useState("");
  const queryClient = useQueryClient();

  /* ── Whitelist enabled/disabled state ── */
  const { data: wlSettings } = useQuery<WhitelistSettings>({
    queryKey: ["whitelist-settings"],
    queryFn: () => apiJson("/api/whitelist/settings"),
    refetchInterval: 30000,
  });

  const toggleMutation = useMutation({
    mutationFn: async (enabled: boolean) => {
      const res = await apiFetch("/api/whitelist/settings", {
        method: "PATCH",
        body: JSON.stringify({ enabled }),
      });
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.error);
      }
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["whitelist-settings"] });
    },
  });

  const whitelistEnabled = wlSettings?.enabled ?? true;

  /* ── Whitelist entries ── */
  const { data: whitelist = [], isLoading } = useQuery<WhitelistEntry[]>({
    queryKey: ["whitelist"],
    queryFn: () => apiJson("/api/whitelist"),
    refetchInterval: 30000,
  });

  const addMutation = useMutation({
    mutationFn: async () => {
      const res = await apiFetch("/api/whitelist", {
        method: "POST",
        body: JSON.stringify({ address: newAddress.trim() }),
      });
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.error);
      }
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["whitelist"] });
      setNewAddress("");
    },
  });

  const removeMutation = useMutation({
    mutationFn: async (address: string) => {
      const res = await apiFetch(`/api/whitelist/${address}`, {
        method: "DELETE",
      });
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.error);
      }
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["whitelist"] });
    },
  });

  const truncate = (addr: string) =>
    `${addr.slice(0, 10)}...${addr.slice(-6)}`;

  const timeAgo = (ts: string) => {
    const diff = Date.now() - new Date(ts + "Z").getTime();
    const mins = Math.floor(diff / 60000);
    if (mins < 60) return `${mins}m ago`;
    const hrs = Math.floor(mins / 60);
    if (hrs < 24) return `${hrs}h ago`;
    return `${Math.floor(hrs / 24)}d ago`;
  };

  return (
    <div className="glass rounded-none p-4 sm:p-5">
      <h3 className="text-[10px] text-[var(--green-dark)] uppercase tracking-widest mb-4">
        // WALLET WHITELIST
      </h3>

      {/* Enable/Disable toggle */}
      <div className="flex items-center justify-between mb-4 pb-4 border-b border-[var(--panel-border)]">
        <div>
          <div className="mono text-xs text-[var(--green)]">
            WHITELIST ENFORCEMENT
          </div>
          <p className="mono text-[10px] text-[var(--green-dim)] opacity-60 mt-1">
            {whitelistEnabled
              ? "Only whitelisted wallets can authenticate"
              : "All wallets can authenticate freely"}
          </p>
        </div>
        <button
          onClick={() => toggleMutation.mutate(!whitelistEnabled)}
          disabled={toggleMutation.isPending}
          className={`crt-toggle ${whitelistEnabled ? "active" : ""}`}
        >
          <span className="crt-toggle-slider" />
        </button>
      </div>

      {/* Status banner when disabled */}
      {!whitelistEnabled && (
        <div className="bg-[rgba(255,200,0,0.05)] border border-[var(--amber)] px-3 py-2 mb-4">
          <span className="mono text-[10px] text-[var(--amber)]">
            WARNING: Whitelist is OFF — any wallet can connect to your terminal
          </span>
        </div>
      )}

      {/* Add address form */}
      <div className="flex gap-2 mb-4">
        <input
          type="text"
          placeholder="0x... wallet address"
          value={newAddress}
          onChange={(e) => setNewAddress(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && newAddress.trim()) addMutation.mutate();
          }}
          className="flex-1 bg-transparent border border-[var(--panel-border)] rounded-none px-3 py-2 text-xs mono text-[var(--green)] focus:outline-none focus:border-[var(--green)] placeholder:text-[var(--green-dark)]"
        />
        <button
          onClick={() => addMutation.mutate()}
          disabled={!newAddress.trim() || addMutation.isPending}
          className="border border-[var(--cyan)] text-[var(--cyan)] hover:bg-[var(--cyan)] hover:text-black disabled:opacity-30 px-4 py-2 rounded-none text-xs font-bold transition-colors"
        >
          {addMutation.isPending ? "..." : "[+ ADD]"}
        </button>
      </div>

      {/* Error messages */}
      {addMutation.isError && (
        <p className="text-xs text-[var(--red)] mb-3 mono">
          ERR: {addMutation.error?.message}
        </p>
      )}
      {removeMutation.isError && (
        <p className="text-xs text-[var(--red)] mb-3 mono">
          ERR: {removeMutation.error?.message}
        </p>
      )}
      {toggleMutation.isError && (
        <p className="text-xs text-[var(--red)] mb-3 mono">
          ERR: {toggleMutation.error?.message}
        </p>
      )}

      {/* Whitelist table */}
      <div className="space-y-1 max-h-[400px] overflow-y-auto">
        {isLoading ? (
          <p className="mono text-sm text-[var(--green-dim)] text-center py-4">
            LOADING<span className="blink">_</span>
          </p>
        ) : whitelist.length === 0 ? (
          <p className="mono text-sm text-[var(--green-dark)] text-center py-4">
            no addresses whitelisted
          </p>
        ) : (
          whitelist.map((entry) => (
            <div
              key={entry.address}
              className="flex items-center justify-between bg-[rgba(0,255,65,0.02)] border border-[rgba(0,255,65,0.08)] px-3 py-2 slide-up"
            >
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <span className="inline-block w-1.5 h-1.5 rounded-full shrink-0 bg-[var(--green)]" />
                  <span className="mono text-sm text-[var(--cyan)]">
                    {truncate(entry.address)}
                  </span>
                </div>
                <div className="text-[10px] text-[var(--green-dark)] mono ml-3.5">
                  added by{" "}
                  {entry.added_by === "system"
                    ? "SYSTEM"
                    : truncate(entry.added_by)}{" "}
                  // {timeAgo(entry.added_at)}
                </div>
              </div>
              <button
                onClick={() => removeMutation.mutate(entry.address)}
                disabled={removeMutation.isPending}
                className="text-[var(--green-dark)] hover:text-[var(--red)] px-2 text-xs font-bold transition-colors disabled:opacity-30"
                title="Remove from whitelist"
              >
                [x]
              </button>
            </div>
          ))
        )}
      </div>

      {/* Count */}
      {whitelist.length > 0 && (
        <div className="mt-3 mono text-[10px] text-[var(--green-dark)] opacity-50">
          {whitelist.length} address{whitelist.length !== 1 ? "es" : ""}{" "}
          whitelisted
        </div>
      )}
    </div>
  );
}
