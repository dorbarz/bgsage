#!/usr/bin/env bash
# SPDX-License-Identifier: MPL-2.0
# Copyright (C) 2026 Mark Higgins
#
# Builds the C boundary in cpp/include/bgbot/mobile.h to WebAssembly with
# Emscripten (an activated emsdk on PATH): wasm/build/bgsage-wasm.js and
# bgsage-wasm.wasm. Single-threaded, no Python, no network.
set -euo pipefail
cd "$(dirname "$0")/.."
out=wasm/build
mkdir -p "$out"
sources=()
for f in board moves strategy pubeval game encoding neural_net multipy cube cube_eval match_equity bearoff mobile; do
    sources+=("cpp/src/$f.cpp")
done
# A worker has no cloud to fall back to, so 3-ply and long budgets are allowed.
em++ -O3 -fno-math-errno -msimd128 -mavx2 -mfma -fwasm-exceptions -std=c++17 -Icpp/include \
    -DBGSAGE_MOBILE_MAX_PLY=3 -DBGSAGE_MOBILE_MAX_BUDGET_MS=120000 \
    "${sources[@]}" -o "$out/bgsage-wasm.js" \
    -sMODULARIZE=1 -sEXPORT_NAME=createBgsageWasm -sENVIRONMENT=web,worker,node \
    -sALLOW_MEMORY_GROWTH=1 -sSTACK_SIZE=2MB -sFORCE_FILESYSTEM=1 \
    -sEXPORTED_FUNCTIONS=_bgsage_mobile_create,_bgsage_mobile_destroy,_bgsage_mobile_analyze,_bgsage_mobile_analyze_play,_bgsage_mobile_free,_bgsage_mobile_last_error,_malloc,_free \
    -sEXPORTED_RUNTIME_METHODS=FS,UTF8ToString,stringToUTF8,lengthBytesUTF8,HEAP32
ls -l "$out"
