"use client";

import { useAuth } from "@/hooks/useAuth";
import { WhitelistPanel } from "./WhitelistPanel";

export function AdminPanel() {
  const { isOwner } = useAuth();

  if (!isOwner) {
    return (
      <div className="glass rounded-none p-8 text-center slide-up">
        <div className="mono text-sm text-[var(--red)] mb-2">
          ACCESS DENIED
        </div>
        <p className="mono text-xs text-[var(--green-dark)]">
          Only the owner wallet can access admin settings.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-6 slide-up">
      {/* Section header */}
      <div className="glass rounded-none p-4 sm:p-5">
        <h2 className="text-[10px] text-[var(--green-dark)] uppercase tracking-widest mb-2">
          // ADMIN SETTINGS
        </h2>
        <p className="mono text-xs text-[var(--green-dim)] opacity-60">
          Manage terminal access, authentication, and system configuration.
        </p>
      </div>

      {/* Whitelist Management */}
      <WhitelistPanel />
    </div>
  );
}
