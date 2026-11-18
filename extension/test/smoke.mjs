// Smoke test: start the server over stdio, list tools, call them against a running analyzer.
// Usage: DBA_URL=http://127.0.0.1:PORT DBA_TOKEN=... node test/smoke.mjs
import { Client } from "@modelcontextprotocol/sdk/client/index.js";
import { StdioClientTransport } from "@modelcontextprotocol/sdk/client/stdio.js";
import { fileURLToPath } from "node:url";
import assert from "node:assert/strict";

const entry = fileURLToPath(new URL("../server/index.js", import.meta.url));
const run = async (env) => {
  const c = new Client({ name: "smoke", version: "1" });
  await c.connect(new StdioClientTransport({ command: "node", args: [entry], env: { ...process.env, ...env } }));
  return c;
};
const j = (r) => JSON.parse(r.content[0].text);

const c = await run({ DBA_URL: process.env.DBA_URL, DBA_TOKEN: process.env.DBA_TOKEN });
const tools = (await c.listTools()).tools;
assert.deepEqual(tools.map((t) => t.name).sort(),
  ["command_overview", "command_values", "data_quality", "frames", "get_findings", "list_runs", "list_sources", "raw_bursts", "timeline"]);
assert.ok(tools.every((t) => t.annotations?.readOnlyHint === true), "all tools must be read-only");

assert.equal(j(await c.callTool({ name: "list_sources", arguments: {} }))[0].name, "dw");
const f = j(await c.callTool({ name: "frames", arguments: { source: "dw", cmd: "2008" } }))[0];
assert.equal(f.decoded.values.remaining_min, 160);
assert.equal(f.decoded.sender.value, "power module");
assert.equal(f.decoded.sender.status, "assumed");
assert.equal(f.decoded.acked_by.status, "assumed");
assert.equal(j(await c.callTool({ name: "command_values", arguments: { source: "dw", ds: "25", cmd: "2008" } }))[0].n, 1);
assert.ok(j(await c.callTool({ name: "get_findings", arguments: { protocol: "bshdbus" } })).nodes["1x"]);
assert.equal(j(await c.callTool({ name: "data_quality", arguments: { source: "dw" } })).ok, 2);
const runs = j(await c.callTool({ name: "list_runs", arguments: { source: "dw" } }));
assert.equal(runs.length, 1);
assert.equal(runs[0].start_status, "assumed");
const inRun = j(await c.callTool({ name: "frames", arguments: { source: "dw", run: runs[0].id } }));
assert.ok(inRun.length >= 1);
const bad = await c.callTool({ name: "frames", arguments: { source: "nobody" } });
assert.equal(bad.isError, true);
assert.match(bad.content[0].text, /404/);
const badArg = await c.callTool({ name: "frames", arguments: { source: "dw", cmd: "zz" } }).catch((e) => ({ isError: true, e }));
assert.equal(badArg.isError, true);
await c.close();

const wrong = await run({ DBA_URL: process.env.DBA_URL, DBA_TOKEN: "wrong" });
const denied = await wrong.callTool({ name: "list_sources", arguments: {} });
assert.equal(denied.isError, true);
assert.match(denied.content[0].text, /401/);
await wrong.close();

const unconfigured = await run({ DBA_URL: "", DBA_TOKEN: "" });
const r = await unconfigured.callTool({ name: "list_sources", arguments: {} });
assert.equal(r.isError, true);
assert.match(r.content[0].text, /must be configured/);
await unconfigured.close();
console.log("smoke OK");
