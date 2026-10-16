// The browser's probability maths must equal the pipeline's (pipeline/prob.py): node site/test/parity.mjs
import { execFileSync } from "node:child_process";
import { createRequire } from "node:module";
const EM = createRequire(import.meta.url)("../model.js");
const rows = JSON.parse(execFileSync("python3", ["-m", "pipeline.selftest", "--dump"], {encoding: "utf8"}));
let worst = 0;
for (const r of rows) {
  const [o, u] = EM.sides(r.line, r.m, r.sd);
  worst = Math.max(worst, Math.abs(o - r.over), Math.abs(u - r.under));
}
if (worst > 1e-6) { console.error(`parity FAILED: worst difference ${worst}`); process.exit(1); }
console.log(`parity ok: ${rows.length} cases, worst difference ${worst.toExponential(2)}`);
