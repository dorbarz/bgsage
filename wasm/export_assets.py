"""Copy what the WebAssembly engine loads into one folder for a web page.

Writes the production model's weights files, bgsage-model.json naming them
for bgsage-engine.js (strategy, one file and hidden size per slot), and the
bearoff database unless --no-bearoff (the engine then builds it in memory).
Needs the Python reference: bgsage installed, or --build as for test_parity.py.
"""
from __future__ import annotations
import argparse
import json
import shutil
import sys
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("out", type=Path)
    parser.add_argument("--build", type=Path, help="build of this tree with the Python extension (default: installed bgsage)")
    parser.add_argument("--no-bearoff", action="store_true")
    args = parser.parse_args()
    if args.build:
        sys.path[:0] = [str(args.build.resolve()), str(Path(__file__).resolve().parents[1] / "python")]
    from bgsage.weights import default_weights, bearoff_db_path
    weights = default_weights()
    args.out.mkdir(parents=True, exist_ok=True)
    slots = [Path(p) for p in weights.weight_paths_list]
    for p in {p.name: p for p in slots}.values():
        shutil.copyfile(p, args.out / p.name)
    if not args.no_bearoff:
        shutil.copyfile(bearoff_db_path(), args.out / "bearoff_1sided.db")
    model = dict(strategy=weights.strategy_type, slots=[p.name for p in slots], hidden=list(weights.hidden_sizes_list))
    (args.out / "bgsage-model.json").write_text(json.dumps(model, indent=1) + "\n")
    total = sum(f.stat().st_size for f in args.out.iterdir())
    print(f"{len({p.name for p in slots})} weights files, {total / 1e6:.1f} MB in {args.out}")


if __name__ == "__main__": main()
