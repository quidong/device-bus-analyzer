// api() against an HTTPS analyzer: trusted only with its CA file; verification is never disabled.
// Usage: DBA_URL=https://127.0.0.1:PORT DBA_TOKEN=... DBA_CA=/path/ca.crt node test/tls.mjs
import assert from "node:assert/strict";
import { api } from "../server/index.js";

const base = process.env.DBA_URL, token = process.env.DBA_TOKEN, ca = process.env.DBA_CA;
const ok = await api("/api/sources", {}, { base, token, caFile: ca });
assert.ok(Array.isArray(ok));
await assert.rejects(api("/api/sources", {}, { base, token, caFile: "" }), /certificate not trusted|self.signed|unable to verify/i);
await assert.rejects(api("/api/sources", {}, { base, token: "wrong", caFile: ca }), /401/);
await assert.rejects(api("/api/sources", {}, { base: "ftp://x", token, caFile: ca }), /https:\/\/ or http:\/\//);
console.log("tls OK");
