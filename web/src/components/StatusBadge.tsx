"use client";

interface StatusBadgeProps {
  status: "running" | "stopped" | "loading";
  label: string;
}

export function StatusBadge({ status, label }: StatusBadgeProps) {
  const colors = {
    running: "text-[var(--green)]",
    stopped: "text-[var(--red)]",
    loading: "text-[var(--amber)]",
  };

  const indicators = {
    running: "ONLINE",
    stopped: "OFFLINE",
    loading: "SYNC..",
  };

  return (
    <div className="glass px-2 py-1 rounded-none mono text-[10px] flex items-center gap-1.5">
      <span className={`${colors[status]} ${status === "running" ? "blink" : ""}`}>&#9608;</span>
      <span className="text-[var(--green-dim)]">{label}</span>
      <span className={`${colors[status]}`}>[{indicators[status]}]</span>
    </div>
  );
}
