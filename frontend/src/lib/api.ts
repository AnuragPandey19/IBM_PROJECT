// Empty string means "same origin as the frontend" (production same-container deploy).
// Only fall back to localhost when the env var is truly unset (dev without .env.local).
const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

// Default request timeout — after this many ms, the request is aborted and the
// caller sees a `TimeoutError`. Chosen at 30 s because model inference is fast
// (~100 ms), the DB writes are fast, and everything else is small. If the
// backend is silent for 30 s something is genuinely wrong.
const DEFAULT_TIMEOUT_MS = 30_000;

type ApiOptions = {
  method?: string;
  body?: unknown;
  auth?: boolean;
  /** Override the default 30 s timeout. Pass 0 to disable. */
  timeoutMs?: number;
  /** External AbortSignal to compose with our timeout. */
  signal?: AbortSignal;
};

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
    this.name = "ApiError";
  }
}

export class TimeoutError extends Error {
  constructor(ms: number) {
    super(`Request timed out after ${ms} ms`);
    this.name = "TimeoutError";
  }
}

function composeAbort(external: AbortSignal | undefined, ms: number): {
  signal: AbortSignal;
  timer: ReturnType<typeof setTimeout> | null;
} {
  const controller = new AbortController();
  let timer: ReturnType<typeof setTimeout> | null = null;
  if (ms > 0) {
    timer = setTimeout(() => controller.abort(new TimeoutError(ms)), ms);
  }
  if (external) {
    if (external.aborted) controller.abort(external.reason);
    else external.addEventListener("abort", () => controller.abort(external.reason), { once: true });
  }
  return { signal: controller.signal, timer };
}

export async function api<T = unknown>(path: string, opts: ApiOptions = {}): Promise<T> {
  const headers: Record<string, string> = { "Content-Type": "application/json" };

  if (opts.auth !== false) {
    const token = typeof window !== "undefined" ? localStorage.getItem("chimera_token") : null;
    if (token) headers["Authorization"] = `Bearer ${token}`;
  }

  const timeoutMs = opts.timeoutMs ?? DEFAULT_TIMEOUT_MS;
  const { signal, timer } = composeAbort(opts.signal, timeoutMs);

  let res: Response;
  try {
    res = await fetch(`${API_URL}${path}`, {
      method: opts.method || "GET",
      headers,
      body: opts.body ? JSON.stringify(opts.body) : undefined,
      signal,
    });
  } catch (err) {
    if (timer) clearTimeout(timer);
    // AbortError raised by our timeout logic surfaces as TimeoutError
    if (err instanceof DOMException && err.name === "AbortError") {
      throw new TimeoutError(timeoutMs);
    }
    throw err;
  }
  if (timer) clearTimeout(timer);

  if (!res.ok) {
    let msg = res.statusText;
    try {
      const data = await res.json();
      msg = data.detail || msg;
    } catch {
      // response had no JSON body — keep statusText
    }
    throw new ApiError(res.status, msg);
  }

  // 204 No Content / empty body — return undefined-as-T rather than throwing on
  // an empty JSON parse. Callers that expect data for a 2xx never should get 204.
  if (res.status === 204) return undefined as T;
  const contentLength = res.headers.get("content-length");
  if (contentLength === "0") return undefined as T;

  // Try to parse JSON; if the body is genuinely empty, return undefined.
  const text = await res.text();
  if (!text) return undefined as T;
  try {
    return JSON.parse(text) as T;
  } catch {
    throw new ApiError(res.status, "Response body was not valid JSON");
  }
}
