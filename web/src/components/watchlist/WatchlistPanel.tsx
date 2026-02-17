"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { apiJson, apiFetch } from "@/lib/api";
import { TraderProfile } from "@/components/copy/TraderProfile";

interface WatchlistEntry {
  id: number;
  user_address: string;
  trader_address: string;
  alias: string;
  notes: string;
  added_at: string;
}

export function WatchlistPanel() {
  const queryClient = useQueryClient();
  const [newAddress, setNewAddress] = useState("");
  const [newAlias, setNewAlias] = useState("");
  const [newNotes, setNewNotes] = useState("");
  const [expandedId, setExpandedId] = useState<number | null>(null);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [editAlias, setEditAlias] = useState("");
  const [editNotes, setEditNotes] = useState("");

  const { data: watchlist = [], isLoading } = useQuery<WatchlistEntry[]>({
    queryKey: ["watchlist"],
    queryFn: () => apiJson("/api/watchlist"),
    refetchInterval: 30000,
  });

  const addMutation = useMutation({
    mutationFn: async () => {
      const res = await apiFetch("/api/watchlist", {
        method: "POST",
        body: JSON.stringify({
          address: newAddress.trim(),
          alias: newAlias.trim(),
          notes: newNotes.trim(),
        }),
      });
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.error || "Failed to add");
      }
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["watchlist"] });
      setNewAddress("");
      setNewAlias("");
      setNewNotes("");
    },
  });

  const removeMutation = useMutation({
    mutationFn: async (id: number) => {
      const res = await apiFetch(`/api/watchlist/${id}`, { method: "DELETE" });
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.error || "Failed to remove");
      }
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["watchlist"] });
    },
  });

  const updateMutation = useMutation({
    mutationFn: async ({ id, alias, notes }: { id: number; alias: string; notes: string }) => {
      const res = await apiFetch(`/api/watchlist/${id}`, {
        method: "PATCH",
        body: JSON.stringify({ alias, notes }),
      });
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.error || "Failed to update");
      }
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["watchlist"] });
      setEditingId(null);
    },
  });

  const followMutation = useMutation({
    mutationFn: async (entry: WatchlistEntry) => {
      const res = await apiFetch("/api/copy/traders", {
        method: "POST",
        body: JSON.stringify({ address: entry.trader_address, alias: entry.alias }),
      });
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.error || "Failed to follow");
      }
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["copy-traders"] });
    },
  });

  const truncate = (addr: string) =>
    `${addr.slice(0, 8)}...${addr.slice(-6)}`;

  const timeAgo = (ts: string) => {
    const diff = Date.now() - new Date(ts + "Z").getTime();
    const mins = Math.floor(diff / 60000);
    if (mins < 60) return `${mins}m ago`;
    const hrs = Math.floor(mins / 60);
    if (hrs < 24) return `${hrs}h ago`;
    return `${Math.floor(hrs / 24)}d ago`;
  };

  const startEdit = (entry: WatchlistEntry) => {
    setEditingId(entry.id);
    setEditAlias(entry.alias || "");
    setEditNotes(entry.notes || "");
  };

  return (
    <div className="space-y-6 slide-up">
      {/* Stats row */}
      <div className="grid grid-cols-2 gap-3">
        <div className="glass rounded-none p-4 slide-up">
          <div className="text-[10px] text-[var(--green-dark)] uppercase tracking-widest mb-2">
            WATCHING
          </div>
          <div className="text-xl sm:text-2xl font-bold mono text-[var(--cyan)]">
            {watchlist.length}
          </div>
        </div>
        <div className="glass rounded-none p-4 slide-up">
          <div className="text-[10px] text-[var(--green-dark)] uppercase tracking-widest mb-2">
            WITH ALIAS
          </div>
          <div className="text-xl sm:text-2xl font-bold mono text-[var(--green)]">
            {watchlist.filter((e: { alias?: string }) => e.alias).length}
          </div>
        </div>
      </div>

      {/* Add to watchlist */}
      <div className="glass rounded-none p-4 sm:p-5">
        <h3 className="text-[10px] text-[var(--green-dark)] uppercase tracking-widest mb-4">
          // ADD TO WATCHLIST
        </h3>

        <div className="space-y-2">
          <div className="flex gap-2">
            <input
              type="text"
              placeholder="0x... wallet address"
              value={newAddress}
              onChange={(e) => setNewAddress(e.target.value)}
              className="flex-1 bg-transparent border border-[var(--panel-border)] rounded-none px-3 py-2 text-xs mono text-[var(--green)] focus:outline-none focus:border-[var(--green)]"
            />
            <input
              type="text"
              placeholder="alias"
              value={newAlias}
              onChange={(e) => setNewAlias(e.target.value)}
              className="w-24 bg-transparent border border-[var(--panel-border)] rounded-none px-3 py-2 text-xs text-[var(--green)] focus:outline-none focus:border-[var(--green)]"
            />
            <button
              onClick={() => addMutation.mutate()}
              disabled={!newAddress.trim() || addMutation.isPending}
              className="border border-[var(--cyan)] text-[var(--cyan)] hover:bg-[var(--cyan)] hover:text-black disabled:opacity-30 px-3 py-2 rounded-none text-xs font-bold transition-colors"
            >
              {addMutation.isPending ? "..." : "[+ADD]"}
            </button>
          </div>
          <input
            type="text"
            placeholder="notes (optional)"
            value={newNotes}
            onChange={(e) => setNewNotes(e.target.value)}
            className="w-full bg-transparent border border-[var(--panel-border)] rounded-none px-3 py-2 text-xs text-[var(--green-dim)] focus:outline-none focus:border-[var(--green)]"
          />
        </div>

        {addMutation.isError && (
          <p className="text-xs text-[var(--red)] mt-2 mono">
            ERR: {(addMutation.error as Error).message}
          </p>
        )}
        {addMutation.isSuccess && (
          <p className="text-xs text-[var(--green)] mt-2 mono">
            ADDED TO WATCHLIST
          </p>
        )}
      </div>

      {/* Watchlist entries */}
      <div className="glass rounded-none p-4 sm:p-5">
        <h3 className="text-[10px] text-[var(--green-dark)] uppercase tracking-widest mb-4">
          // WATCHLIST ({watchlist.length})
        </h3>

        {isLoading ? (
          <div className="text-center py-8">
            <span className="mono text-sm text-[var(--green-dim)]">
              LOADING WATCHLIST<span className="blink">_</span>
            </span>
          </div>
        ) : watchlist.length === 0 ? (
          <div className="text-center py-8">
            <span className="mono text-sm text-[var(--green-dark)]">
              no traders in watchlist — add an address above
            </span>
          </div>
        ) : (
          <div className="space-y-1">
            {watchlist.map((entry) => (
              <div key={entry.id} className="slide-up">
                {/* Entry header row */}
                <div
                  className="flex items-center justify-between border px-3 py-2 cursor-pointer transition-colors bg-[rgba(0,255,65,0.02)] border-[rgba(0,255,65,0.08)] hover:bg-[rgba(0,255,65,0.05)]"
                  onClick={() =>
                    setExpandedId(expandedId === entry.id ? null : entry.id)
                  }
                >
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="inline-block w-1.5 h-1.5 rounded-full shrink-0 bg-[var(--cyan)]" />
                      <span className="mono text-[10px] sm:text-sm text-[var(--cyan)] break-all">
                        {entry.trader_address}
                      </span>
                      {entry.alias && (
                        <span className="text-[10px] text-[var(--green-dim)]">
                          ({entry.alias})
                        </span>
                      )}
                      <span className="text-[8px] text-[var(--green-dark)] border border-[rgba(0,255,65,0.15)] px-1 rounded-none leading-tight">
                        WATCH
                      </span>
                    </div>
                    <div className="text-[10px] text-[var(--green-dark)] mono ml-3.5">
                      added {timeAgo(entry.added_at)}
                      {entry.notes && (
                        <span className="text-[var(--green-dim)] ml-2">
                          — {entry.notes.length > 40 ? entry.notes.slice(0, 40) + "..." : entry.notes}
                        </span>
                      )}
                    </div>
                  </div>
                  <div className="flex items-center gap-1">
                    <span className="text-[10px] text-[var(--green-dark)]">
                      {expandedId === entry.id ? "[-]" : "[+]"}
                    </span>
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        followMutation.mutate(entry);
                      }}
                      disabled={followMutation.isPending}
                      className="text-[var(--green-dark)] hover:text-[var(--green)] px-1 text-[10px] font-bold transition-colors disabled:opacity-30"
                      title="Follow this trader for copy trading"
                    >
                      {followMutation.isPending ? "[...]" : "[FOLLOW]"}
                    </button>
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        startEdit(entry);
                      }}
                      className="text-[var(--green-dark)] hover:text-[var(--amber)] px-1 text-xs font-bold transition-colors"
                    >
                      [e]
                    </button>
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        removeMutation.mutate(entry.id);
                      }}
                      className="text-[var(--green-dark)] hover:text-[var(--red)] px-1 text-xs font-bold transition-colors"
                    >
                      [x]
                    </button>
                  </div>
                </div>

                {/* Edit inline form */}
                {editingId === entry.id && (
                  <div className="border border-t-0 border-[rgba(255,176,0,0.15)] bg-[rgba(0,0,0,0.3)] px-3 py-3 space-y-2 slide-up">
                    <div className="text-[10px] text-[var(--amber)] uppercase tracking-widest">
                      EDIT ENTRY
                    </div>
                    <div className="flex items-center gap-2">
                      <label className="mono text-[10px] text-[var(--green-dim)] w-14 shrink-0">
                        ALIAS
                      </label>
                      <input
                        type="text"
                        value={editAlias}
                        onChange={(e) => setEditAlias(e.target.value)}
                        className="flex-1 bg-transparent border border-[var(--panel-border)] rounded-none px-2 py-1 text-[10px] mono text-[var(--green)] focus:outline-none focus:border-[var(--amber)] min-w-0"
                      />
                    </div>
                    <div className="flex items-center gap-2">
                      <label className="mono text-[10px] text-[var(--green-dim)] w-14 shrink-0">
                        NOTES
                      </label>
                      <input
                        type="text"
                        value={editNotes}
                        onChange={(e) => setEditNotes(e.target.value)}
                        className="flex-1 bg-transparent border border-[var(--panel-border)] rounded-none px-2 py-1 text-[10px] mono text-[var(--green)] focus:outline-none focus:border-[var(--amber)] min-w-0"
                      />
                    </div>
                    <div className="flex items-center gap-2">
                      <button
                        onClick={() =>
                          updateMutation.mutate({
                            id: entry.id,
                            alias: editAlias,
                            notes: editNotes,
                          })
                        }
                        disabled={updateMutation.isPending}
                        className="border border-[var(--amber)] text-[var(--amber)] hover:bg-[var(--amber)] hover:text-black disabled:opacity-30 px-3 py-1 rounded-none text-[10px] font-bold transition-colors"
                      >
                        {updateMutation.isPending ? "SAVING..." : "[SAVE]"}
                      </button>
                      <button
                        onClick={() => setEditingId(null)}
                        className="border border-[var(--green-dark)] text-[var(--green-dark)] hover:text-[var(--green)] px-3 py-1 rounded-none text-[10px] font-bold transition-colors"
                      >
                        [CANCEL]
                      </button>
                      {updateMutation.isSuccess && (
                        <span className="text-[10px] text-[var(--green)] mono">SAVED</span>
                      )}
                    </div>
                  </div>
                )}

                {/* Expanded trader profile */}
                {expandedId === entry.id && (
                  <div className="border border-t-0 border-[rgba(0,255,65,0.08)] bg-[rgba(0,0,0,0.3)] px-3 py-3 slide-up">
                    <TraderProfile address={entry.trader_address} />
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
