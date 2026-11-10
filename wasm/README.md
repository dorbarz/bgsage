# Open Sage in the browser (WebAssembly)

The C boundary in `cpp/include/bgbot/mobile.h`, built with Emscripten for web pages and Node:
checker play, cube actions and single plays at 1 to 3 ply. Single-threaded, no Python, no server.
It gives the x86 build's numbers (within 2e-6 on the parity test below).

## Build

With an activated [emsdk](https://emscripten.org/docs/getting_started/downloads.html):

```
bash wasm/build.sh                         # wasm/build/bgsage-wasm.js + bgsage-wasm.wasm (~360 KB)
python wasm/export_assets.py wasm/assets   # weights (8 MB), bgsage-model.json, bearoff database (4.9 MB)
```

`export_assets.py` needs bgsage importable (installed, or `--build` as below). With `--no-bearoff`
it leaves the bearoff database out, and the engine builds it in memory as it starts (about 8 s).

`build.sh` passes `-mavx2 -mfma`, so `neural_net.cpp` takes its AVX2 path, which Emscripten
translates to WebAssembly SIMD (every current browser has it). The portable path is no faster
here, and its lookup-table sigmoid moves probabilities by up to 3e-4 from what x86 computes.
It also raises the request limits (`BGSAGE_MOBILE_MAX_PLY=3`, `BGSAGE_MOBILE_MAX_BUDGET_MS=120000`),
since a web page has no cloud to fall back to.

## Use

Every call blocks until it is done, so run the engine in a Web Worker. With `bgsage-wasm.js`,
`bgsage-wasm.wasm`, `bgsage-engine.js` and this `worker.js` in one folder and the assets in `assets/`:

```js
importScripts('bgsage-wasm.js', 'bgsage-engine.js');
const get = async (name, json) => { const r = await fetch('assets/' + name); return json ? r.json() : r.arrayBuffer(); };
const ready = (async () => {
  const model = await get('bgsage-model.json', true);
  const files = {};
  for (const name of new Set(model.slots)) files[name] = await get(name);
  return createBgsageEngine(createBgsageWasm, model, files, await get('bearoff_1sided.db'));
})();
onmessage = async ({ data }) => {
  const engine = await ready;
  const { moves } = engine.checker({ ...data, ply: 2 });           // every play, best first
  const best = engine.play({ ...data, ply: 3 }, moves[0].board);   // the best one, a ply deeper
  postMessage({ moves, best, cube: engine.cube({ board: data.board, ply: 2 }) });
};
```

and on the page `new Worker('worker.js').postMessage({ board, die1: 3, die2: 1 })`. In Node, take
`createBgsageEngine` from `require('./bgsage-engine.js')` and the factory from
`require('./build/bgsage-wasm.js')`.

Boards are bgsage's 26 numbers from the side on roll. Requests use the field names of
`BgsageMobileRequest` (`board`, `die1`, `die2`, `ply`, `cube_value`, `cube_owner`, `away1`, `away2`,
`is_crawford`, `jacoby`, `beaver`, `budget_ms`); a field left out is 0, except `ply` (1),
`cube_value` (1) and `budget_ms` (30000). Answers are the C boundary's JSON. An invalid request,
or one over its budget, throws with `bgsage_mobile_last_error()`'s text.

A full 3-ply list can take seconds. Ranking every play at 2-ply and then calling `play()` at 3-ply
on the few closest to the best gives each of those its exact 3-ply value, in tens of milliseconds.

## Test

```
python wasm/test_parity.py                 # installed bgsage as the reference
python wasm/test_parity.py --build build   # or a build of this tree, as for mobile/test_parity.py
```

It runs `mobile/test_parity.py`'s positions (with more dice) through the WebAssembly build in Node
and compares them with the Python analyzer: checker play at 1 and 2 ply, cube actions and single
plays at 1 to 3 ply, rejected requests, and the bearoff table built in memory against the file
(identical here: WebAssembly has no fast math). With Emscripten 6.0.12 and Node 24, against
bgsage 2.0.20260907 on x86-64: 131 cases, largest difference 1.2e-6. On a laptop, a full 2-ply list
of a middle-game position takes about 100 ms, a 3-ply play or cube action 40 to 120 ms.
