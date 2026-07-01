const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE_URL}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  if (!res.ok) {
    const body = await res.text().catch(() => "");
    throw new ApiError(res.status, body || res.statusText);
  }
  return res.json() as Promise<T>;
}

export const api = {
  health: () => request<{ status: string; service: string; phase: string; timestamp: string }>(
    "/api/health"
  ),
  runPipelineStub: (payload: { disease: string; gene?: string; autonomy_level?: string }) =>
    request<Record<string, unknown>>("/api/pipeline/run", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
};

export { API_BASE_URL };
