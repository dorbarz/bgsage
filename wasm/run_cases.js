// SPDX-License-Identifier: MPL-2.0
// Copyright (C) 2026 Mark Higgins
//
// Runs a list of requests through the WebAssembly build, for test_parity.py.
// node wasm/run_cases.js <cases.json>  ->  one JSON array on stdout.
// cases.json: {build, model: {strategy, slots: [weights paths], hidden}, bearoff,
//              cases: [{engine: "file"|"generated", op: "checker"|"cube"|"play", request, play}]}
'use strict';
const fs = require('fs');
const path = require('path');
const { createBgsageEngine } = require('./bgsage-engine.js');

async function main() {
  const spec = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
  const factory = require(path.resolve(spec.build, 'bgsage-wasm.js'));
  const files = {};
  for (const p of spec.model.slots) files[path.basename(p)] = fs.readFileSync(p);
  const model = { strategy: spec.model.strategy, slots: spec.model.slots.map(p => path.basename(p)), hidden: spec.model.hidden };
  const engines = {}, initialization_ms = {};
  const engine = async kind => {
    if (!engines[kind]) {
      const started = performance.now();
      engines[kind] = await createBgsageEngine(factory, model, files, kind === 'file' ? fs.readFileSync(spec.bearoff) : null);
      initialization_ms[kind] = performance.now() - started;
    }
    return engines[kind];
  };
  const results = [];
  for (const c of spec.cases) {
    const e = await engine(c.engine || 'file'), started = performance.now();
    try {
      const value = c.op === 'play' ? e.play(c.request, c.play) : e[c.op](c.request);
      results.push({ ok: true, value, ms: performance.now() - started });
    } catch (err) {
      results.push({ ok: false, error: String(err.message || err), ms: performance.now() - started });
    }
  }
  Object.values(engines).forEach(e => e.destroy());
  process.stdout.write(JSON.stringify({ results, initialization_ms }));
}

main().catch(err => { console.error(err); process.exit(1); });
