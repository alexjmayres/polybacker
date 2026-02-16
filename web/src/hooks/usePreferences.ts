"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { apiJson, apiFetch } from "@/lib/api";

interface UserPreferences {
  activeTab?: string;
  autoRedeem?: boolean;
  redeemInterval?: number;
  [key: string]: unknown;
}

/**
 * Hook to load and save user preferences to the backend.
 * Falls back to empty object if not authenticated or on error.
 */
export function usePreferences() {
  const queryClient = useQueryClient();

  const { data: prefs = {} } = useQuery<UserPreferences>({
    queryKey: ["preferences"],
    queryFn: async () => {
      try {
        return await apiJson<UserPreferences>("/api/preferences");
      } catch {
        return {};
      }
    },
    staleTime: 60000,
    retry: false,
  });

  const saveMutation = useMutation({
    mutationFn: async (updates: Partial<UserPreferences>) => {
      const res = await apiFetch("/api/preferences", {
        method: "PATCH",
        body: JSON.stringify(updates),
      });
      if (!res.ok) throw new Error("Failed to save preferences");
      return res.json();
    },
    onSuccess: (_data, variables) => {
      // Optimistically update the cache
      queryClient.setQueryData<UserPreferences>(["preferences"], (old) => ({
        ...old,
        ...variables,
      }));
    },
  });

  const savePrefs = (updates: Partial<UserPreferences>) => {
    saveMutation.mutate(updates);
  };

  return { prefs, savePrefs };
}
