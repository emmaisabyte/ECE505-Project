import argparse
import json
import os
from typing import List, Optional

import pandas as pd

from find_solutions import (
    SOLVER_MAP,
    benchmark_solvers,
    build_constraint_clauses,
    load_cnf,
    load_constraints_from_json,
    load_node_groups,
)

DEFAULT_SOLVERS = list(SOLVER_MAP.keys())


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run PySAT solver benchmark on constrained c7552 CNF.")
    parser.add_argument("--cnf", default="data/cnf.txt", help="Path to DIMACS CNF file")
    parser.add_argument("--node-index", default="data/node_index.txt", help="Path to node_index.txt")
    parser.add_argument("--constraints", default="data/constraints.json", help="Path to constraints.json")
    parser.add_argument(
        "--max-solutions",
        type=int,
        default=100,
        help="Cap unique solutions per solver (use -1 for unlimited until UNSAT or timeout)",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=30.0,
        help="Per-solver timeout in seconds (use -1 for no timeout)",
    )
    parser.add_argument(
        "--project",
        choices=["all", "inputs", "outputs"],
        default="all",
        help="Project uniqueness onto all variables, primary INPUTs, or primary OUTPUTs",
    )
    parser.add_argument("--excel-out", default="SAT.xlsx", help="Output Excel workbook path")
    parser.add_argument("--json-out", default="benchmark_raw.json", help="Output JSON run log path")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    base_clauses = load_cnf(args.cnf)
    positives, negatives = load_constraints_from_json(args.constraints)
    node_index_path = args.node_index if os.path.exists(args.node_index) else None
    constraint_clauses = build_constraint_clauses(
        positives=positives,
        negatives=negatives,
        node_index_path=node_index_path,
    )
    all_clauses = base_clauses + constraint_clauses

    target_vars: Optional[List[int]] = None
    if args.project != "all":
        if not node_index_path:
            raise FileNotFoundError("node_index.txt is required when --project is 'inputs' or 'outputs'.")
        groups = load_node_groups(node_index_path)
        target_vars = groups["INPUT"] if args.project == "inputs" else groups["OUTPUT"]

    max_n: Optional[int] = None if args.max_solutions < 0 else args.max_solutions
    timeout_s: Optional[float] = None if args.timeout < 0 else args.timeout

    print(
        f"Loaded {len(base_clauses)} base clauses + {len(constraint_clauses)} constraint clauses = "
        f"{len(all_clauses)} total clauses | projection={args.project} | max_n={max_n} | timeout={timeout_s}s"
    )

    rows, raw_details = benchmark_solvers(
        clauses=all_clauses,
        solver_names=DEFAULT_SOLVERS,
        n=max_n,
        target_vars=target_vars,
        timeout_s=timeout_s,
    )

    df = pd.DataFrame(rows)
    print("\n=== Solver Benchmark Summary ===")
    print(df.to_string(index=False))

    with pd.ExcelWriter(args.excel_out, engine="openpyxl", mode="w") as writer:
        df.to_excel(writer, sheet_name="Sheet1", index=False)

    payload = {
        "config": {
            "cnf": args.cnf,
            "node_index": args.node_index,
            "constraints": args.constraints,
            "base_clauses": len(base_clauses),
            "constraint_clauses": len(constraint_clauses),
            "total_clauses": len(all_clauses),
            "projection": args.project,
            "target_var_count": len(target_vars) if target_vars else None,
            "max_solutions": max_n,
            "timeout_s": timeout_s,
        },
        "summary": rows,
        "solvers": raw_details,
    }
    with open(args.json_out, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
    print(f"\nSaved Excel to {args.excel_out} and detailed log to {args.json_out}")


if __name__ == "__main__":
    main()
