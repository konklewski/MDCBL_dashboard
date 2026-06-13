// Lightweight client-side error reporting hook used by the root error boundary.
// Keeps a single choke point so a real reporting backend can be wired in later;
// for now it forwards to the console on the client only.

export function reportClientError(error: unknown, context: Record<string, unknown> = {}) {
  if (typeof window === "undefined") return;
  console.error("[client error]", error, {
    route: window.location.pathname,
    ...context,
  });
}
