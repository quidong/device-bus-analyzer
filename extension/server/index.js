#!/usr/bin/env node
// MCP server (stdio) for Claude Desktop. Talks only to the Device Bus Analyzer's read-only HTTP API: every tool is a GET.
import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { z } from "zod";

const BASE = (process.env.DBA_URL || "").replace(/\/+$/, "");
const TOKEN = process.env.DBA_TOKEN || "";
const TIMEOUT_MS = 20000;

export async function api(path, params = {}, { base = BASE, token = TOKEN } = {}) {
  if (!base || !token) throw new Error("DBA_URL and DBA_TOKEN must be configured in the extension settings");
  const url = new URL(base + path);
  for (const [k, v] of Object.entries(params)) {
    if (v !== undefined && v !== null && v !== "" && v !== false) url.searchParams.set(k, String(v));
  }
  const res = await fetch(url, { headers: { Authorization: `Bearer ${token}` }, signal: AbortSignal.timeout(TIMEOUT_MS) });
  const text = await res.text();
  if (!res.ok) throw new Error(`Analyzer answered ${res.status}: ${text.slice(0, 300)}`);
  return JSON.parse(text);
}

const READ_ONLY = { readOnlyHint: true, destructiveHint: false, idempotentHint: true, openWorldHint: false };
const text = (data) => ({ content: [{ type: "text", text: JSON.stringify(data, null, 1) }] });
const wrap = (fn) => async (args) => {
  try {
    return text(await fn(args));
  } catch (e) {
    return { isError: true, content: [{ type: "text", text: String(e.message || e) }] };
  }
};
const hex = (n) => z.string().regex(new RegExp(`^[0-9a-fA-F]{1,${n}}$`)).describe(`hex, up to ${n} digits`);
const when = z.string().optional().describe("ISO 8601 (local time of the analyzer) or epoch seconds");

export function buildServer(call = api) {
  const server = new McpServer({ name: "device-bus-analyzer", version: "0.1.0" });
  const tool = (name, description, shape, fn) =>
    server.registerTool(name, { description, inputSchema: shape, annotations: READ_ONLY }, wrap(fn));

  tool("list_sources", "List recorded devices: name, protocol, number of bursts and frames, first/last timestamp (epoch seconds).",
    {}, () => call("/api/sources"));
  tool("get_findings",
    "Protocol specification: nodes (sender/receiver derivation), ACK nodes and commands, each with status confirmed / assumed / unknown and evidence. protocol: bshdbus or macs.",
    { protocol: z.enum(["bshdbus", "macs"]) }, ({ protocol }) => call(`/api/spec/${protocol}`));
  tool("list_runs",
    "Runs (program cycles) grouped from the telegrams: id, start/end, duration, program, remaining time, frame count. Start and end are derived and carry a status (assumed). Pass the id as `run` to timeline, frames or raw_bursts.",
    { source: z.string() }, ({ source }) => call(`/api/${encodeURIComponent(source)}/runs`));
  tool("command_overview", "All (destination, command) pairs seen on a device with counts, distinct values, decode status and derived sender.",
    { source: z.string() }, ({ source }) => call(`/api/${encodeURIComponent(source)}/commands`));
  tool("command_values", "Distinct data values of one command with counts and first/last time.",
    { source: z.string(), ds: hex(2), cmd: hex(4), limit: z.number().int().min(1).max(500).default(50) },
    ({ source, ds, cmd, limit }) => call(`/api/${encodeURIComponent(source)}/commands/${ds}/${cmd}/values`, { limit }));
  tool("timeline", "Value changes per command in time order (what you need to understand a run).",
    { source: z.string(), run: z.number().int().optional().describe("run id from list_runs"), since: when, until: when,
      limit: z.number().int().min(1).max(20000).default(500) },
    ({ source, ...q }) => call(`/api/${encodeURIComponent(source)}/timeline`, q));
  tool("frames",
    "Decoded telegrams with sender, receiver, ACK node and per-field status. Every derived value carries a status: confirmed / assumed / unknown (value null = unknown).",
    { source: z.string(), run: z.number().int().optional().describe("run id from list_runs"), ds: hex(2).optional(), cmd: hex(4).optional(), since: when, until: when,
      bad_only: z.boolean().default(false).describe("CRC failures only"), limit: z.number().int().min(1).max(5000).default(100),
      offset: z.number().int().min(0).default(0) },
    ({ source, ...q }) => call(`/api/${encodeURIComponent(source)}/frames`, q));
  tool("raw_bursts", "Raw received bursts (hex) with sequence number and microsecond spacing, for reverse engineering.",
    { source: z.string(), run: z.number().int().optional().describe("run id from list_runs"), since: when, until: when, limit: z.number().int().min(1).max(5000).default(50), offset: z.number().int().min(0).default(0) },
    ({ source, ...q }) => call(`/api/${encodeURIComponent(source)}/bursts`, q));
  tool("data_quality", "Frame counts, CRC errors, frames without ACK, board restarts and detected gaps.",
    { source: z.string() }, ({ source }) => call(`/api/${encodeURIComponent(source)}/quality`));
  tool("list_markers", "Companion markers (what was done at the appliance, with server time): id, label, kind, start/end.",
    { source: z.string() }, ({ source }) => call(`/api/${encodeURIComponent(source)}/markers`));
  tool("learn_analysis", "Findings derived from the markers: byte changes per action with repeats and status, plus display-value candidates.",
    { source: z.string() }, ({ source }) => call(`/api/${encodeURIComponent(source)}/learn`));
  tool("device_state", "Current value of everything taught for a device (door, remaining time ...), as Home Assistant reads it.",
    { source: z.string() }, ({ source }) => call(`/api/${encodeURIComponent(source)}/state`));
  return server;
}

if (import.meta.url === `file://${process.argv[1]}` || process.argv[1]?.endsWith("server/index.js")) {
  await buildServer().connect(new StdioServerTransport());
}
