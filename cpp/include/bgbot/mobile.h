// SPDX-License-Identifier: MPL-2.0
// Copyright (C) 2026 Mark Higgins
#pragma once

// Portable, exception-safe C boundary for native clients. No Python, platform
// framework, network, or host-application dependency. Calls on a handle must be
// serialized by its owner. Returned JSON is owned by the caller; free it below.
#ifdef __cplusplus
extern "C" {
#endif

typedef struct BgsageMobileEngine BgsageMobileEngine;
typedef struct {
    int board[26];
    int die1, die2, ply; // ply 1-2 (BGSAGE_MOBILE_MAX_PLY at build time)
    int cube_value, cube_owner; // 0 centered, 1 player, 2 opponent
    int away1, away2, is_crawford, jacoby, beaver;
    int budget_ms; // checked between candidates; never creates engine threads;
                   // 1-1000 (BGSAGE_MOBILE_MAX_BUDGET_MS at build time)
} BgsageMobileRequest;

// An empty bearoff_path builds the one-sided bearoff database in memory
// instead of loading it: no asset to ship, a start seconds slower. (A
// fast-math build rounds a few of its entries one step from the file's.)
BgsageMobileEngine* bgsage_mobile_create(const char* strategy_type,
    const char* const* paths, const int* hidden_sizes, int count,
    const char* bearoff_path);
void bgsage_mobile_destroy(BgsageMobileEngine* engine);
// operation: 0 checker; 1 cube. Null means invalid, over budget, or failure;
// native caller falls back to the cloud. Does not produce a partial result.
char* bgsage_mobile_analyze(BgsageMobileEngine* engine, int operation,
    const BgsageMobileRequest* request);
// Operation 0 for one play of the roll: play is the board after it, as in
// operation 0's "board". The same JSON and numbers as that play's entry there,
// so a caller can rank every play at a low ply and look deeper at a few.
// Null as above, or when play is not a legal play of the roll.
char* bgsage_mobile_analyze_play(BgsageMobileEngine* engine,
    const BgsageMobileRequest* request, const int* play);
void bgsage_mobile_free(char* text);
const char* bgsage_mobile_last_error(void);

#ifdef __cplusplus
}
#endif
