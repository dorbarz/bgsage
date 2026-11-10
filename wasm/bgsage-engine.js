// SPDX-License-Identifier: MPL-2.0
// Copyright (C) 2026 Mark Higgins
//
// JavaScript wrapper over the WebAssembly build of cpp/include/bgbot/mobile.h.
// Runs in a browser (best in a Web Worker: every call blocks until it is done)
// and in Node. Requests use the C struct's field names; answers are the same
// JSON the C boundary returns.
'use strict';

const REQUEST_FIELDS = ['die1', 'die2', 'ply', 'cube_value', 'cube_owner', 'away1', 'away2',
  'is_crawford', 'jacoby', 'beaver', 'budget_ms'];
const DEFAULTS = { die1: 0, die2: 0, ply: 1, cube_value: 1, cube_owner: 0, away1: 0, away2: 0,
  is_crawford: 0, jacoby: 0, beaver: 0, budget_ms: 30000 };

// factory: createBgsageWasm, from bgsage-wasm.js.
// model: {strategy, slots, hidden} as export_assets.py writes it to bgsage-model.json.
// files: {file name: ArrayBuffer or Uint8Array} for every weights file model.slots names.
// bearoff: the bearoff database (bearoff_1sided.db), or null to build it in memory.
async function createBgsageEngine(factory, model, files, bearoff, moduleOptions) {
  const M = await factory(moduleOptions || {});
  const error = () => new Error(M.UTF8ToString(M._bgsage_mobile_last_error()));
  const cstr = s => { const n = M.lengthBytesUTF8(s) + 1, p = M._malloc(n); M.stringToUTF8(s, p, n); return p; };
  const names = [...new Set(model.slots)];
  M.FS.mkdir('/bgsage');
  for (const name of names) {
    if (!files[name]) throw new Error('missing weights file ' + name);
    M.FS.writeFile('/bgsage/' + name, new Uint8Array(files[name]));
  }
  if (bearoff) M.FS.writeFile('/bgsage/bearoff.db', new Uint8Array(bearoff));
  const n = model.slots.length, paths = model.slots.map(s => cstr('/bgsage/' + s));
  const pathArray = M._malloc(4 * n), hidden = M._malloc(4 * n);
  paths.forEach((p, i) => { M.HEAP32[(pathArray >> 2) + i] = p; M.HEAP32[(hidden >> 2) + i] = model.hidden[i]; });
  const type = cstr(model.strategy), bearoffPath = cstr(bearoff ? '/bgsage/bearoff.db' : '');
  const engine = M._bgsage_mobile_create(type, pathArray, hidden, n, bearoffPath);
  [...paths, pathArray, hidden, type, bearoffPath].forEach(p => M._free(p));
  // the engine has read the files: drop the copies
  for (const name of names) M.FS.unlink('/bgsage/' + name);
  if (bearoff) M.FS.unlink('/bgsage/bearoff.db');
  if (!engine) throw error();

  const check26 = (b, what) => { if (!b || b.length !== 26) throw new Error(what + ' must be 26 numbers'); };
  function call(operation, request, play) {
    const r = Object.assign({}, DEFAULTS, request);
    check26(r.board, 'board'); if (play) check26(play, 'play');
    // BgsageMobileRequest (26 + 11 ints), then the play's 26 ints
    const p = M._malloc(4 * (26 + REQUEST_FIELDS.length + 26)), b = p >> 2, q = p + 4 * (26 + REQUEST_FIELDS.length);
    let out = 0;
    try {
      for (let i = 0; i < 26; i++) M.HEAP32[b + i] = r.board[i];
      REQUEST_FIELDS.forEach((k, i) => { M.HEAP32[b + 26 + i] = Number(r[k]) | 0; });
      if (play) for (let i = 0; i < 26; i++) M.HEAP32[(q >> 2) + i] = play[i];
      out = play ? M._bgsage_mobile_analyze_play(engine, p, q) : M._bgsage_mobile_analyze(engine, operation, p);
      if (!out) throw error();
      return JSON.parse(M.UTF8ToString(out));
    } finally {
      if (out) M._bgsage_mobile_free(out);
      M._free(p);
    }
  }
  let alive = true;
  const live = () => { if (!alive) throw new Error('engine destroyed'); };
  return {
    // every play of the roll, best first (operation 0)
    checker(request) { live(); return call(0, request); },
    // the cube action before the roll (operation 1)
    cube(request) { live(); return call(1, request); },
    // one play of the roll (board after it), as its entry in checker()
    play(request, play) { live(); return call(0, request, play); },
    destroy() { if (alive) { alive = false; M._bgsage_mobile_destroy(engine); } },
  };
}

if (typeof module !== 'undefined') module.exports = { createBgsageEngine };
