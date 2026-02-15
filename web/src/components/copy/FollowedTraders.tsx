"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { apiJson, apiFetch } from "@/lib/api";
import { TraderProfile } from "./TraderProfile";

interface Trader {
  address: string;
  alias: string;
  active: number;
  total_copied: number;
  total_spent: number;
  added_at: string;
  copy_percentage: number | null;
  min_copy_size: number | null;
  max_copy_size: number | null;
  max_daily_spend: number | null;
}

interface TraderSettingsForm {
  copy_percentage: string;
  min_copy_size: string;
  max_copy_size: string;
  max_daily_spend: string;
}

function TraderSettings({
  trader,
  onClose,
}: {
  trader: Trader;
  onClose: () => void;
}) {
  const queryClient = useQueryClient();
  const [form, setForm] = useState<TraderSettingsForm>({
    copy_percentage: trader.copy_percentage != null ? String(trader.copy_percentage * 100) : "",
    min_copy_size: trader.min_copy_size != null ? String(trader.min_copy_size) : "",
    max_copy_size: trader.max_copy_size != null ? String(trader.max_copy_size) : "",
    max_daily_spend: trader.max_daily_spend != null ? String(trader.max_daily_spend) : "",
  });

  const saveMutation = useMutation({
    mutationFn: async () => {
      const body: Record<string, number | null> = {};

      if (form.copy_percentage !== "") {
        body.copy_percentage = parseFloat(form.copy_percentage) / 100;
      } else {
        body.copy_percentage = null;
      }
      if (form.min_copy_size !== "") {
        body.min_copy_size = parseFloat(form.min_copy_size);
      } else {
        body.min_copy_size = null;
      }
      if (form.max_copy_size !== "") {
        body.max_copy_size = parseFloat(form.max_copy_size);
      } else {
        body.max_copy_size = null;
      }
      if (form.max_daily_spend !== "") {
        body.max_daily_spend = parseFloat(form.max_daily_spend);
      } else {
        body.max_daily_spend = null;
      }

      const res = await apiFetch(`/api/copy/traders/${trader.address}`, {
        method: "PATCH",
        body: JSON.stringify(body),
      });
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.error);
      }
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["copy-traders"] });
    },
  });

  const toggleMutation = useMutation({
    mutationFn: async (active: boolean) => {
      const res = await apiFetch(`/api/copy/traders/${trader.address}`, {
        method: "PATCH",
        body: JSON.stringify({ active }),
      });
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.error);
      }
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["copy-traders"] });
    },
  });

  const clearField = (field: keyof TraderSettingsForm) => {
    setForm((prev) => ({ ...prev, [field]: "" }));
  };

  return (
    <div className="border border-t-0 border-[rgba(0,255,65,0.08)] bg-[rgba(0,0,0,0.3)] px-3 py-3 space-y-3 slide-up">
      {/* Active toggle */}
      <div className="flex items-center justify-between">
        <span className="text-[10px] text-[var(--green-dark)] uppercase tracking-widest">
          STATUS
        </span>
        <button
          onClick={() => toggleMutation.mutate(!trader.active)}
          className={`crt-toggle ${trader.active ? "active" : ""}`}
        >
          <span className="crt-toggle-slider" />
        </button>
      </div>

      {/* Settings fields */}
      <div className="space-y-2">
        <div className="text-[10px] text-[var(--green-dark)] uppercase tracking-widest">
          PER-TRADER OVERRIDES
        </div>

        {/* Copy Percentage */}
        <div className="flex items-center gap-2">
          <label className="mono text-[10px] text-[var(--green-dim)] w-20 shrink-0">
            COPY %
          </label>
          <input
            type="number"
            min="1"
            max="100"
            step="1"
            placeholder="GLOBAL: 10%"
            value={form.copy_percentage}
            onChange={(e) => setForm((p) => ({ ...p, copy_percentage: e.target.value }))}
            className="flex-1 bg-transparent border border-[var(--panel-border)] rounded-none px-2 py-1 text-[10px] mono text-[var(--green)] focus:outline-none focus:border-[var(--green)] min-w-0"
          />
          <button
            onClick={() => clearField("copy_percentage")}
            className="text-[9px] text-[var(--green-dark)] hover:text-[var(--red)] transition-colors"
          >
            [CLR]
          </button>
        </div>

        {/* Min Size */}
        <div className="flex items-center gap-2">
          <label className="mono text-[10px] text-[var(--green-dim)] w-20 shrink-0">
            MIN $
          </label>
          <input
            type="number"
            min="0"
            step="1"
            placeholder="GLOBAL: $5"
            value={form.min_copy_size}
            onChange={(e) => setForm((p) => ({ ...p, min_copy_size: e.target.value }))}
            className="flex-1 bg-transparent border border-[var(--panel-border)] rounded-none px-2 py-1 text-[10px] mono text-[var(--green)] focus:outline-none focus:border-[var(--green)] min-w-0"
          />
          <button
            onClick={() => clearField("min_copy_size")}
            className="text-[9px] text-[var(--green-dark)] hover:text-[var(--red)] transition-colors"
          >
            [CLR]
          </button>
        </div>

        {/* Max Size */}
        <div className="flex items-center gap-2">
          <label className="mono text-[10px] text-[var(--green-dim)] w-20 shrink-0">
            MAX $
          </label>
          <input
            type="number"
            min="0"
            step="1"
            placeholder="GLOBAL: $100"
            value={form.max_copy_size}
            onChange={(e) => setForm((p) => ({ ...p, max_copy_size: e.target.value }))}
            className="flex-1 bg-transparent border border-[var(--panel-border)] rounded-none px-2 py-1 text-[10px] mono text-[var(--green)] focus:outline-none focus:border-[var(--green)] min-w-0"
          />
          <button
            onClick={() => clearField("max_copy_size")}
            className="text-[9px] text-[var(--green-dark)] hover:text-[var(--red)] transition-colors"
          >
            [CLR]
          </button>
        </div>

        {/* Daily Budget */}
        <div className="flex items-center gap-2">
          <label className="mono text-[10px] text-[var(--green-dim)] w-20 shrink-0">
            DAILY $
          </label>
          <input
            type="number"
            min="0"
            step="10"
            placeholder="GLOBAL: $500"
            value={form.max_daily_spend}
            onChange={(e) => setForm((p) => ({ ...p, max_daily_spend: e.target.value }))}
            className="flex-1 bg-transparent border border-[var(--panel-border)] rounded-none px-2 py-1 text-[10px] mono text-[var(--green)] focus:outline-none focus:border-[var(--green)] min-w-0"
          />
          <button
            onClick={() => clearField("max_daily_spend")}
            className="text-[9px] text-[var(--green-dark)] hover:text-[var(--red)] transition-colors"
          >
            [CLR]
          </button>
        </div>
      </div>

      {/* Save/error */}
      <div className="flex items-center gap-2 pt-1">
        <button
          onClick={() => saveMutation.mutate()}
          disabled={saveMutation.isPending}
          className="border border-[var(--green)] text-[var(--green)] hover:bg-[var(--green)] hover:text-black disabled:opacity-30 px-3 py-1 rounded-none text-[10px] font-bold transition-colors"
        >
          {saveMutation.isPending ? "SAVING..." : "[SAVE]"}
        </button>
        {saveMutation.isSuccess && (
          <span className="text-[10px] text-[var(--green)] mono">SAVED</span>
        )}
        {saveMutation.isError && (
          <span className="text-[10px] text-[var(--red)] mono">
            ERR: {saveMutation.error?.message}
          </span>
        )}
      </div>

      {/* Trader Profile: positions + PnL charts */}
      <div className="pt-2 border-t border-[var(--panel-border)]">
        <TraderProfile address={trader.address} />
      </div>
    </div>
  );
}

export function FollowedTraders() {
  const [newAddress, setNewAddress] = useState("");
  const [newAlias, setNewAlias] = useState("");
  const [expandedAddr, setExpandedAddr] = useState<string | null>(null);
  const queryClient = useQueryClient();

  const { data: traders = [] } = useQuery<Trader[]>({
    queryKey: ["copy-traders"],
    queryFn: () => apiJson("/api/copy/traders?include_inactive=true"),
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

  const hasOverride = (t: Trader) =>
    t.copy_percentage != null ||
    t.min_copy_size != null ||
    t.max_copy_size != null ||
    t.max_daily_spend != null;

  return (
    <div className="glass rounded-none p-4 sm:p-5">
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
      <div className="space-y-1 max-h-[400px] overflow-y-auto">
        {traders.length === 0 ? (
          <p className="mono text-sm text-[var(--green-dark)] text-center py-4">
            no traders followed
          </p>
        ) : (
          traders.map((trader) => (
            <div key={trader.address} className="slide-up">
              {/* Trader header row */}
              <div
                className={`flex items-center justify-between border px-3 py-2 cursor-pointer transition-colors ${
                  trader.active
                    ? "bg-[rgba(0,255,65,0.02)] border-[rgba(0,255,65,0.08)]"
                    : "bg-[rgba(255,0,0,0.02)] border-[rgba(255,0,0,0.08)] opacity-60"
                }`}
                onClick={() =>
                  setExpandedAddr(
                    expandedAddr === trader.address ? null : trader.address
                  )
                }
              >
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    {/* Active indicator dot */}
                    <span
                      className={`inline-block w-1.5 h-1.5 rounded-full shrink-0 ${
                        trader.active ? "bg-[var(--green)]" : "bg-[var(--red)]"
                      }`}
                    />
                    <span className="mono text-sm text-[var(--cyan)]">
                      {truncate(trader.address)}
                    </span>
                    {trader.alias && (
                      <span className="text-[10px] text-[var(--green-dim)]">
                        ({trader.alias})
                      </span>
                    )}
                    {hasOverride(trader) && (
                      <span className="text-[8px] text-[var(--amber)] border border-[var(--amber)] px-1 rounded-none leading-tight">
                        CUSTOM
                      </span>
                    )}
                  </div>
                  <div className="text-[10px] text-[var(--green-dark)] mono ml-3.5">
                    {trader.total_copied} trades // ${trader.total_spent.toFixed(2)} spent
                  </div>
                </div>
                <div className="flex items-center gap-1">
                  <span className="text-[10px] text-[var(--green-dark)]">
                    {expandedAddr === trader.address ? "[-]" : "[+]"}
                  </span>
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      removeMutation.mutate(trader.address);
                    }}
                    className="text-[var(--green-dark)] hover:text-[var(--red)] px-1 text-xs font-bold transition-colors"
                  >
                    [x]
                  </button>
                </div>
              </div>

              {/* Expanded settings panel */}
              {expandedAddr === trader.address && (
                <TraderSettings
                  trader={trader}
                  onClose={() => setExpandedAddr(null)}
                />
              )}
            </div>
          ))
        )}
      </div>
    </div>
  );
}
