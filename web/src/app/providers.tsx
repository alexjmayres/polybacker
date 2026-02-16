"use client";

import { ReactNode, useEffect, useMemo, useState } from "react";
import {
  RainbowKitProvider,
  darkTheme,
  RainbowKitAuthenticationProvider,
  createAuthenticationAdapter,
  type AuthenticationStatus,
} from "@rainbow-me/rainbowkit";
import { WagmiProvider } from "wagmi";
import { polygon } from "wagmi/chains";
import { getDefaultConfig } from "@rainbow-me/rainbowkit";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { SiweMessage } from "siwe";

import "@rainbow-me/rainbowkit/styles.css";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "";

const config = getDefaultConfig({
  appName: "Polybacker",
  projectId: process.env.NEXT_PUBLIC_WALLETCONNECT_PROJECT_ID || "PLACEHOLDER",
  chains: [polygon],
  ssr: true,
});

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,        // Data is fresh for 30s
      gcTime: 5 * 60 * 1000,    // Keep unused data in cache for 5 min
      refetchOnWindowFocus: true,
      retry: 1,
    },
  },
});

export function Providers({ children }: { children: ReactNode }) {
  const [authStatus, setAuthStatus] =
    useState<AuthenticationStatus>("unauthenticated");

  // Check for existing session on mount
  useEffect(() => {
    const token = localStorage.getItem("polybacker_token");
    if (!token) {
      setAuthStatus("unauthenticated");
      return;
    }

    setAuthStatus("loading");
    fetch(`${API_BASE}/api/auth/session`, {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then((res) => {
        if (res.ok) {
          setAuthStatus("authenticated");
        } else {
          localStorage.removeItem("polybacker_token");
          setAuthStatus("unauthenticated");
        }
      })
      .catch(() => {
        setAuthStatus("unauthenticated");
      });
  }, []);

  const authAdapter = useMemo(
    () =>
      createAuthenticationAdapter({
        getNonce: async () => {
          try {
            const res = await fetch(`${API_BASE}/api/auth/nonce`, { method: "POST" });
            if (!res.ok) throw new Error(`Nonce request failed: ${res.status}`);
            const data = await res.json();
            return data.nonce;
          } catch (err) {
            console.error("[Polybacker] Failed to fetch nonce:", err);
            throw err;
          }
        },

        createMessage: ({ nonce, address, chainId }) => {
          return new SiweMessage({
            domain: window.location.host,
            address,
            statement:
              "Sign in to Polybacker to manage your copy trading dashboard.",
            uri: window.location.origin,
            version: "1",
            chainId,
            nonce,
          }).prepareMessage();
        },

        verify: async ({ message, signature }) => {
          try {
            const res = await fetch(`${API_BASE}/api/auth/verify`, {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({
                message,
                signature,
              }),
            });

            if (!res.ok) {
              console.error("[Polybacker] Verify failed:", res.status);
              return false;
            }

            const data = await res.json();
            localStorage.setItem("polybacker_token", data.token);
            setAuthStatus("authenticated");
            return true;
          } catch (err) {
            console.error("[Polybacker] Verify error:", err);
            return false;
          }
        },

        signOut: async () => {
          localStorage.removeItem("polybacker_token");
          localStorage.removeItem("polybacker_view");
          setAuthStatus("unauthenticated");
        },
      }),
    []
  );

  return (
    <WagmiProvider config={config}>
      <QueryClientProvider client={queryClient}>
        <RainbowKitAuthenticationProvider
          adapter={authAdapter}
          status={authStatus}
        >
          <RainbowKitProvider
            theme={darkTheme({
              accentColor: "#00ff41",
              accentColorForeground: "#0a0a0a",
              borderRadius: "none",
              fontStack: "system",
              overlayBlur: "small",
            })}
          >
            {children}
          </RainbowKitProvider>
        </RainbowKitAuthenticationProvider>
      </QueryClientProvider>
    </WagmiProvider>
  );
}
