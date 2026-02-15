"use client";

import { useEffect, useState } from "react";
import { apiFetch } from "@/lib/api";

interface AuthState {
  address: string | null;
  role: string | null;
  isAuthenticated: boolean;
  isOwner: boolean;
  isLoading: boolean;
}

export function useAuth(): AuthState {
  const [state, setState] = useState<AuthState>({
    address: null,
    role: null,
    isAuthenticated: false,
    isOwner: false,
    isLoading: true,
  });

  useEffect(() => {
    const token = localStorage.getItem("polybacker_token");
    if (!token) {
      setState((s) => ({ ...s, isLoading: false }));
      return;
    }

    apiFetch("/api/auth/session")
      .then((res) => {
        if (!res.ok) throw new Error("Invalid session");
        return res.json();
      })
      .then((data) => {
        setState({
          address: data.address,
          role: data.role,
          isAuthenticated: true,
          isOwner: data.role === "owner",
          isLoading: false,
        });
      })
      .catch(() => {
        localStorage.removeItem("polybacker_token");
        setState({
          address: null,
          role: null,
          isAuthenticated: false,
          isOwner: false,
          isLoading: false,
        });
      });
  }, []);

  return state;
}
