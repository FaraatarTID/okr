import Fastify from "fastify";
import { pathToFileURL } from "node:url";

import { isAllowlistedRoute, normalizeBackendPath, requiresActorHeader } from "./allowlist.js";
import type { BffConfig } from "./config.js";
import { readConfig } from "./config.js";
import { proxyToBackend } from "./proxy.js";

type WildcardParams = { "*": string };

const RESPONSE_HEADER_BLOCKLIST = new Set([
  "connection",
  "content-length",
  "keep-alive",
  "proxy-authenticate",
  "proxy-authorization",
  "te",
  "trailer",
  "transfer-encoding",
  "upgrade",
]);

function firstHeaderValue(raw: string | string[] | undefined): string {
  if (Array.isArray(raw)) {
    return String(raw[0] ?? "").trim();
  }
  return String(raw ?? "").trim();
}

export function createServer(
  config: BffConfig,
  deps?: { fetchFn?: typeof fetch },
) {
  const app = Fastify({
    logger: {
      level: process.env.BFF_LOG_LEVEL || "info",
    },
    trustProxy: true,
  });

  app.get("/healthz", async () => {
    return {
      status: "ok",
      service: "spa-bff",
      backendApiUrl: config.backendApiUrl,
    };
  });

  app.route<{ Params: WildcardParams }>({
    method: ["GET", "POST", "PATCH", "PUT", "DELETE"],
    url: "/api/backend/*",
    handler: async (request, reply) => {
      const rawWildcardPath = request.params["*"];
      const backendPath = normalizeBackendPath(rawWildcardPath);
      if (!backendPath) {
        return reply.code(400).send({ error: "Invalid backend path." });
      }

      if (!isAllowlistedRoute(request.method, backendPath)) {
        return reply.code(403).send({ error: "Route not allowlisted by spa-bff policy." });
      }

      if (requiresActorHeader(request.method, backendPath)) {
        const actor = firstHeaderValue(request.headers["x-okr-actor"]);
        if (!actor) {
          return reply.code(400).send({
            error: "Missing required x-okr-actor header for this route.",
          });
        }
      }

      const queryIndex = request.url.indexOf("?");
      const queryString = queryIndex >= 0 ? request.url.slice(queryIndex) : "";

      try {
        const result = await proxyToBackend(
          config,
          {
            method: request.method,
            path: backendPath,
            queryString,
            body: request.body,
            incomingHeaders: request.headers,
          },
          deps,
        );

        for (const [headerName, headerValue] of result.headers.entries()) {
          if (RESPONSE_HEADER_BLOCKLIST.has(headerName.toLowerCase())) {
            continue;
          }
          reply.header(headerName, headerValue);
        }

        reply.code(result.status);
        if (result.body.length === 0) {
          return reply.send();
        }
        return reply.send(result.body);
      } catch (error) {
        request.log.error({ err: error }, "BFF backend proxy failure");
        return reply.code(502).send({
          error: "Backend proxy request failed.",
        });
      }
    },
  });

  return app;
}

async function start(): Promise<void> {
  const config = readConfig(process.env);
  const app = createServer(config);
  try {
    await app.listen({ host: config.host, port: config.port });
    app.log.info({ host: config.host, port: config.port }, "spa-bff started");
  } catch (error) {
    app.log.error({ err: error }, "spa-bff startup failure");
    process.exit(1);
  }
}

const isEntrypoint = process.argv[1]
  ? import.meta.url === pathToFileURL(process.argv[1]).href
  : false;

if (isEntrypoint) {
  void start();
}
