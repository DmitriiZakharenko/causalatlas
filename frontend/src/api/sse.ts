import { api } from "./client";
import { PIPELINE_EVENT_TYPES, type PipelineEvent } from "./types";

/**
 * Subscribes to a run's live SSE feed. The backend names each SSE event
 * after its own `type` field (see backend/app/main.py's `stream_pipeline_run`),
 * so a plain `EventSource.onmessage` never fires for any of them -- this
 * wraps `addEventListener` for every known event name from `PIPELINE_EVENT_TYPES`
 * instead, and normalizes them all back into one `onEvent` callback.
 *
 * Returns an unsubscribe function. The browser's native EventSource retries
 * on its own after a dropped connection; `afterSeq` lets a caller resume
 * from where a previous subscription left off (e.g. after a page reload)
 * without replaying the entire history.
 */
export function subscribeToRun(
  runId: string,
  onEvent: (event: PipelineEvent) => void,
  options?: { afterSeq?: number; onError?: (err: Event) => void }
): () => void {
  const source = new EventSource(api.streamUrl(runId, options?.afterSeq));

  const listeners = PIPELINE_EVENT_TYPES.map((type) => {
    const handler = (raw: MessageEvent) => {
      try {
        const payload = JSON.parse(raw.data);
        onEvent({ ...payload, type } as PipelineEvent);
      } catch {
        // A malformed SSE payload must never crash the UI silently pretending
        // nothing happened -- surface it the same way a real error would be.
        onEvent({ type: "run_failed", reason: `unparseable SSE payload for ${type}: ${raw.data}` });
      }
    };
    source.addEventListener(type, handler);
    return { type, handler };
  });

  if (options?.onError) {
    source.addEventListener("error", options.onError);
  }

  return () => {
    for (const { type, handler } of listeners) {
      source.removeEventListener(type, handler);
    }
    source.close();
  };
}

export function isTerminalEvent(event: PipelineEvent): boolean {
  return event.type === "run_completed" || event.type === "run_failed" || event.type === "run_paused";
}
