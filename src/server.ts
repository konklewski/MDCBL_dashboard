import "./lib/error-capture";

import { readFile } from "node:fs/promises";
import path from "node:path";
import { consumeLastCapturedError } from "./lib/error-capture";
import { renderErrorPage } from "./lib/error-page";

type ServerEntry = {
  fetch: (request: Request, env: unknown, ctx: unknown) => Promise<Response> | Response;
};

let serverEntryPromise: Promise<ServerEntry> | undefined;
const researchSnapshotPath = path.join(process.cwd(), "backend", "research_pipeline", "cache", "research_snapshot.json");

async function getServerEntry(): Promise<ServerEntry> {
  if (!serverEntryPromise) {
    serverEntryPromise = import("@tanstack/react-start/server-entry").then(
      (m) => (m.default ?? m) as ServerEntry,
    );
  }
  return serverEntryPromise;
}

// h3 swallows in-handler throws into a normal 500 Response with body
// {"unhandled":true,"message":"HTTPError"} — try/catch alone never fires for those.
async function normalizeCatastrophicSsrResponse(response: Response): Promise<Response> {
  if (response.status < 500) return response;
  const contentType = response.headers.get("content-type") ?? "";
  if (!contentType.includes("application/json")) return response;

  const body = await response.clone().text();
  if (!body.includes('"unhandled":true') || !body.includes('"message":"HTTPError"')) {
    return response;
  }

  console.error(consumeLastCapturedError() ?? new Error(`h3 swallowed SSR error: ${body}`));
  return new Response(renderErrorPage(), {
    status: 500,
    headers: { "content-type": "text/html; charset=utf-8" },
  });
}

function jsonResponse(body: unknown, init: ResponseInit = {}): Response {
  return new Response(typeof body === "string" ? body : JSON.stringify(body, null, 2), {
    ...init,
    headers: {
      "content-type": "application/json; charset=utf-8",
      ...(init.headers ?? {}),
    },
  });
}

async function handleResearchApi(request: Request): Promise<Response | null> {
  const url = new URL(request.url);
  if (!url.pathname.startsWith("/api/research")) return null;

  try {
    const raw = await readFile(researchSnapshotPath, "utf-8");
    if (url.pathname === "/api/research/snapshot") {
      return jsonResponse(raw);
    }

    const snapshot = JSON.parse(raw);
    if (url.pathname === "/api/research/status") {
      return jsonResponse({
        generatedAt: snapshot.generatedAt,
        mode: snapshot.mode,
        computationTruth: snapshot.computationTruth,
        scope: snapshot.scope,
        audits: snapshot.audits,
        missingData: snapshot.missingData,
        commands: {
          refreshFromExisting: "python3 backend/research_pipeline/pipeline.py --mode from-existing",
          fullRecompute: "python3 -m pip install -r backend/research_pipeline/requirements.txt && python3 backend/research_pipeline/pipeline.py --mode full",
        },
      });
    }

    if (url.pathname === "/api/research/recompute") {
      return jsonResponse(
        {
          status: "manual_command_required",
          reason: "Full recompute reads about 10GB of parquet and requires pyarrow, scipy, and scikit-learn. It is intentionally not launched from an HTTP request.",
          command: "python3 backend/research_pipeline/pipeline.py --mode full",
        },
        { status: 409 },
      );
    }

    return jsonResponse({ error: "Unknown research API route" }, { status: 404 });
  } catch (error) {
    return jsonResponse(
      {
        error: "Research backend cache missing or unreadable",
        snapshotPath: researchSnapshotPath,
        detail: error instanceof Error ? error.message : String(error),
      },
      { status: 500 },
    );
  }
}

export default {
  async fetch(request: Request, env: unknown, ctx: unknown) {
    try {
      const researchResponse = await handleResearchApi(request);
      if (researchResponse) return researchResponse;

      const handler = await getServerEntry();
      const response = await handler.fetch(request, env, ctx);
      return await normalizeCatastrophicSsrResponse(response);
    } catch (error) {
      console.error(error);
      return new Response(renderErrorPage(), {
        status: 500,
        headers: { "content-type": "text/html; charset=utf-8" },
      });
    }
  },
};
