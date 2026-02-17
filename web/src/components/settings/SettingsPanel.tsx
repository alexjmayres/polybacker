"use client";

import { useState, useEffect } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useAccount } from "wagmi";
import { apiJson, apiFetch } from "@/lib/api";

interface ApiCreds {
  api_key: string;
  api_secret: string;
  api_passphrase: string;
  polymarket_address: string;
  has_creds: boolean;
  updated_at?: string;
}

export function SettingsPanel() {
  const queryClient = useQueryClient();
  const { address: walletAddress } = useAccount();

  // Fetch existing creds
  const { data: creds, isLoading } = useQuery<ApiCreds>({
    queryKey: ["api-creds"],
    queryFn: () => apiJson("/api/settings/api-creds"),
    staleTime: 30000,
  });

  // Form state
  const [apiKey, setApiKey] = useState("");
  const [apiSecret, setApiSecret] = useState("");
  const [apiPassphrase, setApiPassphrase] = useState("");
  const [pmAddress, setPmAddress] = useState("");
  const [showSecrets, setShowSecrets] = useState(false);

  // Populate form when creds load
  useEffect(() => {
    if (creds) {
      setApiKey(creds.api_key || "");
      setPmAddress(creds.polymarket_address || "");
      // Don't populate masked secrets — user must re-enter
    }
  }, [creds]);

  // Save mutation
  const saveMutation = useMutation({
    mutationFn: async () => {
      const body: Record<string, string> = {
        api_key: apiKey.trim(),
        polymarket_address: pmAddress.trim(),
      };
      // Only send secret/passphrase if the user entered new ones
      if (apiSecret && !apiSecret.includes("••••")) {
        body.api_secret = apiSecret.trim();
      }
      if (apiPassphrase && !apiPassphrase.includes("••••")) {
        body.api_passphrase = apiPassphrase.trim();
      }

      const res = await apiFetch("/api/settings/api-creds", {
        method: "PUT",
        body: JSON.stringify(body),
      });
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.error || "Failed to save");
      }
      return res.json();
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["api-creds"] });
      setApiSecret("");
      setApiPassphrase("");
    },
  });

  // Delete mutation
  const deleteMutation = useMutation({
    mutationFn: async () => {
      const res = await apiFetch("/api/settings/api-creds", {
        method: "DELETE",
      });
      if (!res.ok) throw new Error("Failed to delete");
      return res.json();
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["api-creds"] });
      setApiKey("");
      setApiSecret("");
      setApiPassphrase("");
      setPmAddress("");
    },
  });

  return (
    <div className="space-y-6 slide-up">
      {/* Header */}
      <div className="glass rounded-none p-4 sm:p-5">
        <h2 className="text-[10px] text-[var(--green-dark)] uppercase tracking-widest mb-2">
          // SETTINGS
        </h2>
        <p className="mono text-xs text-[var(--green-dim)] opacity-60">
          Configure your Polymarket Builder API credentials for trading.
        </p>
        {walletAddress && (
          <p className="mono text-[10px] text-[var(--cyan)] mt-2">
            WALLET: {walletAddress.slice(0, 8)}...{walletAddress.slice(-6)}
            <span className="text-[var(--green-dark)] ml-2">
              (all settings stored per wallet)
            </span>
          </p>
        )}
      </div>

      {/* Builder API Credentials */}
      <div className="glass rounded-none p-4 sm:p-6">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-[10px] text-[var(--green-dark)] uppercase tracking-widest">
            POLYMARKET BUILDER API
          </h3>
          {creds?.has_creds && (
            <span className="text-[10px] mono text-[var(--green)] bg-[var(--green)]/10 px-2 py-0.5">
              CONNECTED
            </span>
          )}
        </div>

        <p className="mono text-xs text-[var(--green-dim)] opacity-60 mb-6">
          Get your API credentials from{" "}
          <a
            href="https://polymarket.com/settings/builder"
            target="_blank"
            rel="noopener noreferrer"
            className="text-[var(--green)] underline"
          >
            polymarket.com/settings/builder
          </a>
          . The API secret and passphrase are shown only once when you create a
          new key.
        </p>

        {isLoading ? (
          <div className="mono text-xs text-[var(--green-dark)] animate-pulse">
            Loading credentials...
          </div>
        ) : (
          <div className="space-y-4">
            {/* API Key */}
            <div>
              <label className="block text-[10px] text-[var(--green-dark)] uppercase tracking-widest mb-1">
                API KEY
              </label>
              <input
                type="text"
                value={apiKey}
                onChange={(e) => setApiKey(e.target.value)}
                placeholder="019c647c-2017-79cb-..."
                className="w-full bg-black/50 border border-[var(--panel-border)] text-[var(--green)] mono text-xs px-3 py-2 focus:border-[var(--green)] focus:outline-none placeholder:text-[var(--green-dark)]/30"
              />
            </div>

            {/* API Secret */}
            <div>
              <label className="block text-[10px] text-[var(--green-dark)] uppercase tracking-widest mb-1">
                API SECRET
              </label>
              <div className="relative">
                <input
                  type={showSecrets ? "text" : "password"}
                  value={apiSecret}
                  onChange={(e) => setApiSecret(e.target.value)}
                  placeholder={creds?.has_creds ? "••••••••  (unchanged)" : "Enter API secret"}
                  className="w-full bg-black/50 border border-[var(--panel-border)] text-[var(--green)] mono text-xs px-3 py-2 pr-16 focus:border-[var(--green)] focus:outline-none placeholder:text-[var(--green-dark)]/30"
                />
                <button
                  type="button"
                  onClick={() => setShowSecrets(!showSecrets)}
                  className="absolute right-2 top-1/2 -translate-y-1/2 text-[10px] mono text-[var(--green-dark)] hover:text-[var(--green)]"
                >
                  {showSecrets ? "[HIDE]" : "[SHOW]"}
                </button>
              </div>
            </div>

            {/* API Passphrase */}
            <div>
              <label className="block text-[10px] text-[var(--green-dark)] uppercase tracking-widest mb-1">
                API PASSPHRASE
              </label>
              <input
                type={showSecrets ? "text" : "password"}
                value={apiPassphrase}
                onChange={(e) => setApiPassphrase(e.target.value)}
                placeholder={creds?.has_creds ? "••••••••  (unchanged)" : "Enter API passphrase"}
                className="w-full bg-black/50 border border-[var(--panel-border)] text-[var(--green)] mono text-xs px-3 py-2 focus:border-[var(--green)] focus:outline-none placeholder:text-[var(--green-dark)]/30"
              />
            </div>

            {/* Polymarket Address */}
            <div>
              <label className="block text-[10px] text-[var(--green-dark)] uppercase tracking-widest mb-1">
                POLYMARKET TRADING ADDRESS
              </label>
              <input
                type="text"
                value={pmAddress}
                onChange={(e) => setPmAddress(e.target.value)}
                placeholder="0x67c47d3be64bcd4d7e..."
                className="w-full bg-black/50 border border-[var(--panel-border)] text-[var(--green)] mono text-xs px-3 py-2 focus:border-[var(--green)] focus:outline-none placeholder:text-[var(--green-dark)]/30"
              />
              <p className="mono text-[10px] text-[var(--green-dark)]/50 mt-1">
                Your Polymarket proxy wallet address (from Builder Settings). Often different from your MetaMask EOA.
              </p>
            </div>

            {/* Status / Error */}
            {saveMutation.isError && (
              <div className="mono text-xs text-[var(--red)]">
                ERROR: {saveMutation.error?.message}
              </div>
            )}
            {saveMutation.isSuccess && (
              <div className="mono text-xs text-[var(--green)]">
                Credentials saved successfully.
              </div>
            )}

            {/* Actions */}
            <div className="flex gap-3 pt-2">
              <button
                onClick={() => saveMutation.mutate()}
                disabled={saveMutation.isPending || !apiKey.trim()}
                className="bg-[var(--green)] text-black font-bold mono text-xs px-6 py-2 hover:bg-[var(--green-bright)] disabled:opacity-30 disabled:cursor-not-allowed transition-all"
              >
                {saveMutation.isPending ? "SAVING..." : "[ SAVE CREDENTIALS ]"}
              </button>

              {creds?.has_creds && (
                <button
                  onClick={() => {
                    if (window.confirm("Remove your stored API credentials?")) {
                      deleteMutation.mutate();
                    }
                  }}
                  disabled={deleteMutation.isPending}
                  className="border border-[var(--red)]/50 text-[var(--red)] font-bold mono text-xs px-4 py-2 hover:bg-[var(--red)]/10 transition-all"
                >
                  [ CLEAR ]
                </button>
              )}
            </div>

            {creds?.updated_at && (
              <p className="mono text-[10px] text-[var(--green-dark)]/40">
                Last updated: {new Date(creds.updated_at + "Z").toLocaleString()}
              </p>
            )}
          </div>
        )}
      </div>

      {/* Info box */}
      <div className="glass rounded-none p-4 sm:p-5">
        <h3 className="text-[10px] text-[var(--green-dark)] uppercase tracking-widest mb-3">
          HOW IT WORKS
        </h3>
        <ul className="space-y-2 mono text-xs text-[var(--green-dim)] opacity-60">
          <li>
            <span className="text-[var(--green)]">1.</span> Go to{" "}
            <a
              href="https://polymarket.com/settings/builder"
              target="_blank"
              rel="noopener noreferrer"
              className="text-[var(--green)] underline"
            >
              Polymarket Builder Settings
            </a>
          </li>
          <li>
            <span className="text-[var(--green)]">2.</span> Create a new API key
            &mdash; copy the key, secret, and passphrase immediately
          </li>
          <li>
            <span className="text-[var(--green)]">3.</span> Paste them here and
            save. The secret and passphrase are encrypted at rest.
          </li>
          <li>
            <span className="text-[var(--green)]">4.</span> Your Polymarket trading
            address is shown on the same page (under &ldquo;Address&rdquo;).
          </li>
        </ul>
      </div>
    </div>
  );
}
