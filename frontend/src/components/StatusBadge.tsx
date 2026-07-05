import type { RunStatus } from "../api/types";

const LABELS: Record<RunStatus, string> = {
  pending: "Pending",
  running: "Running",
  paused: "Paused — awaiting decision",
  completed: "Completed",
  failed: "Failed",
};

export default function StatusBadge({ status }: { status: RunStatus }) {
  return <span className={`badge badge--${status}`}>{LABELS[status]}</span>;
}
