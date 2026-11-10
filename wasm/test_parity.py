"""Compare the WebAssembly build with the Python analyzer.

Build with wasm/build.sh first. Needs Node, and the Python reference: bgsage
installed, or --build pointing at a build of this tree (as for
mobile/test_parity.py). The positions are mobile/test_parity.py's, with more
dice; 3-ply is checked one play at a time (a full 3-ply list is slow here).
"""
from __future__ import annotations
import argparse
import json
import random
import subprocess
import sys
import tempfile
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build", type=Path, help="build of this tree with the Python extension (default: installed bgsage)")
    parser.add_argument("--wasm", type=Path, default=Path(__file__).resolve().parent / "build")
    args = parser.parse_args()
    here = Path(__file__).resolve().parent
    if args.build:
        sys.path[:0] = [str(args.build.resolve()), str(here.parent / "python")]
    import bgbot_cpp as cpp
    from bgsage import BgBotAnalyzer, STARTING_BOARD
    from bgsage.weights import default_weights, bearoff_db_path
    weights = default_weights()
    boards = [list(STARTING_BOARD)]
    rng = random.Random(471)
    board = boards[0]
    for turn in range(32):
        candidates = list(cpp.possible_moves(board, rng.randint(1, 6), rng.randint(1, 6)))
        board = list(cpp.flip_board(rng.choice(candidates) if candidates else board))
        if turn % 4 == 3: boards.append(board)
    bearoff = [0] * 26
    bearoff[1:5] = [4, 3, 4, 4]
    bearoff[22:25] = [-4, -5, -6]
    boards.append(bearoff)
    rolls = [(3, 1), (6, 6), (5, 2), (4, 4), (6, 1), (2, 1)]

    cases, checks = [], []
    def case(check, **c):
        cases.append(c); checks.append(check)
    for ply in (1, 2, 3):
        reference = BgBotAnalyzer(eval_level=f"{ply}ply", parallel_threads=2)
        for index, board in enumerate(boards):
            match = index % 3 == 1
            settings = dict(cube_value=2 if index % 2 else 1, cube_owner=("centered", "player", "opponent")[index % 3],
                away1=3 if match else 0, away2=5 if match else 0, is_crawford=False,
                jacoby=not match and index % 2 == 0, beaver=not match and index % 2 == 0)
            if index == 1: settings.update(cube_value=1, away1=1, away2=3, is_crawford=True)
            if index == 4: settings.update(away1=5, away2=1)
            die1, die2 = rolls[index % len(rolls)]
            request = dict(board=board, die1=die1, die2=die2, ply=ply, cube_value=settings["cube_value"], cube_owner=index % 3,
                away1=settings["away1"], away2=settings["away2"], is_crawford=int(settings["is_crawford"]),
                jacoby=int(settings["jacoby"]), beaver=int(settings["beaver"]), budget_ms=120000)
            expected = reference._analyzer.checker_play_analytics(board, die1, die2, **settings)
            if ply < 3:
                case(("checker", expected), op="checker", request=request)
            case(("cube", reference._analyzer.cube_action_analytics(board, **settings)), op="cube", request=request)
            for m in expected[:2]:
                case(("play", m), op="play", request=request, play=list(m["board"]))
            if index == 0 and ply == 1:
                case(("rejected",), op="play", request=request, play=board)
    start = dict(board=list(STARTING_BOARD), die1=3, die2=1, ply=4)
    case(("rejected",), op="checker", request=start)
    case(("rejected",), op="checker", request=dict(start, ply=1, board=[0, 500] + list(STARTING_BOARD)[2:]))
    # an empty bearoff path builds the table in memory: the same answers as the file
    for ply in (1, 2):
        for die1, die2 in ((3, 1), (6, 6), (2, 1)):
            request = dict(board=bearoff, die1=die1, die2=die2, ply=ply, jacoby=1, beaver=1)
            for op in ("checker", "cube"):
                case(("answered",), op=op, request=request)
                case(("same", len(cases) - 1), op=op, request=request, engine="generated")

    spec = dict(build=str(args.wasm.resolve()), bearoff=str(bearoff_db_path()), cases=cases,
        model=dict(strategy=weights.strategy_type, slots=[str(p) for p in weights.weight_paths_list], hidden=list(weights.hidden_sizes_list)))
    with tempfile.TemporaryDirectory() as tmp:
        spec_path = Path(tmp) / "cases.json"
        spec_path.write_text(json.dumps(spec))
        run = subprocess.run(["node", str(here / "run_cases.js"), str(spec_path)], capture_output=True, text=True, check=True)
    out = json.loads(run.stdout)
    results = out["results"]

    max_error = 0.0
    def close(got, want, keys, tolerance=1e-5):
        nonlocal max_error
        errors = [abs(got[k] - want[k]) for k in keys] + [abs(a - b) for a, b in zip(got["probs"], want["probs"])]
        max_error = max(max_error, *errors)
        assert max(errors) < tolerance, errors
    for n, (check, r) in enumerate(zip(checks, results)):
        kind = check[0]
        if kind == "rejected":
            assert not r["ok"], (n, r)
            continue
        assert r["ok"], (n, cases[n]["request"]["ply"], r["error"])
        got = r["value"]
        if kind == "checker":
            moves = {tuple(m["board"]): m for m in got["moves"]}
            assert set(moves) == {tuple(m["board"]) for m in check[1]}, n
            for m in check[1]:
                close(moves[tuple(m["board"])], m, ("equity", "cubeless_equity", "equity_diff"))
                assert moves[tuple(m["board"])]["eval_level"] == m["eval_level"]
        elif kind == "cube":
            for key in ("should_double", "should_take", "is_beaver", "eval_level"):
                assert got[key] == check[1][key], (n, key)
            close(got, check[1], ("equity_nd", "equity_dt", "equity_dp", "optimal_equity", "cubeless_equity"))
        elif kind == "play":
            assert len(got["moves"]) == 1 and got["moves"][0]["board"] == check[1]["board"], n
            close(got["moves"][0], check[1], ("equity", "cubeless_equity"))
            assert got["moves"][0]["eval_level"] == check[1]["eval_level"]
        elif kind == "answered":
            pass
        elif kind == "same":
            assert got == results[check[1]]["value"], n
    timings = {}
    for c, r in zip(cases, results):
        if r["ok"] and "engine" not in c:
            timings.setdefault(f'{c["op"]} {c["request"]["ply"]}-ply', []).append(r["ms"])
    print(json.dumps({"cases": len(cases), "max_absolute_error": max_error,
        "median_and_max_ms": {k: [round(sorted(v)[len(v) // 2], 1), round(max(v), 1)] for k, v in timings.items()},
        "initialization_ms": {k: round(v) for k, v in out["initialization_ms"].items()},
        "reference": str(cpp.__file__)}, indent=2))


if __name__ == "__main__": main()
