/** OpenTelemetry boundary policy and small transport helpers.
 * Public browsers are not trusted trace issuers by default: accepting their trace
 * context would let them join arbitrary traces. Set BFF_TRUSTED_TRACE_CONTEXT=true
 * only behind an authenticated, trusted mesh ingress.
 */
import { randomBytes } from "node:crypto";
import { AsyncLocalStorage } from "node:async_hooks";

export type TraceContext = { traceparent: string; tracestate?: string };
const contextStore = new AsyncLocalStorage<TraceContext>();
const TRACEPARENT = /^00-[0-9a-f]{32}-[0-9a-f]{16}-[0-9a-f]{2}$/i;
const TRACESTATE_MAX = 512;

function freshTrace(): TraceContext {
  return { traceparent: `00-${randomBytes(16).toString("hex")}-${randomBytes(8).toString("hex")}-01` };
}

/** Extract only syntactically bounded W3C context from a trusted ingress. */
export function extractPublicTraceContext(headers: Record<string, string | string[] | undefined>, trusted = process.env.BFF_TRUSTED_TRACE_CONTEXT === "true"): TraceContext {
  const raw = headers.traceparent;
  const traceparent = Array.isArray(raw) ? raw[0] : raw;
  const state = headers.tracestate;
  const tracestate = (Array.isArray(state) ? state[0] : state)?.trim();
  if (trusted && traceparent && TRACEPARENT.test(traceparent.trim()) && (!tracestate || tracestate.length <= TRACESTATE_MAX)) {
    return { traceparent: traceparent.trim(), ...(tracestate ? { tracestate } : {}) };
  }
  return freshTrace();
}

export function runWithTrace<T>(trace: TraceContext, fn: () => T): T {
  return contextStore.run(trace, fn);
}

/** Inject W3C context into the private BFF-to-backend hop, never client headers. */
export function injectTraceContext(headers: Record<string, string>): void {
  const trace = contextStore.getStore() ?? freshTrace();
  headers.traceparent = trace.traceparent;
  if (trace.tracestate) headers.tracestate = trace.tracestate;
}

export function injectSuppliedTraceContext(headers: Record<string, string>, trace?: TraceContext): void {
  if (trace) {
    headers.traceparent = trace.traceparent;
    if (trace.tracestate) headers.tracestate = trace.tracestate;
    return;
  }
  injectTraceContext(headers);
}

export function traceLogFields(): Record<string, string> {
  const traceparent = contextStore.getStore()?.traceparent;
  if (!traceparent) return {};
  const [, traceId, spanId] = traceparent.split("-");
  return traceId && spanId ? { trace_id: traceId, span_id: spanId } : {};
}

/** Configuration is intentionally best-effort; disabled/misconfigured exporters never affect traffic. */
export async function startTelemetry(): Promise<void> {
  if (process.env.OTEL_SDK_DISABLED === "true" || !process.env.OTEL_EXPORTER_OTLP_ENDPOINT) return;
  try {
    // Variable specifiers keep the BFF operational when optional telemetry deps are absent.
    const sdkName = "@opentelemetry/sdk-node";
    const exporterName = "@opentelemetry/exporter-trace-otlp-proto";
    const [{ NodeSDK }, { OTLPTraceExporter }] = await Promise.all([import(sdkName), import(exporterName)]);
    const sdk = new NodeSDK({ traceExporter: new OTLPTraceExporter() });
    sdk.start();
    process.once("SIGTERM", () => void sdk.shutdown());
    process.once("SIGINT", () => void sdk.shutdown());
  } catch {
    // Telemetry is non-fatal by design; logging here could recursively expose config.
  }
}
