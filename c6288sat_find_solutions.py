import time
from typing import Dict, Iterable, List, Optional, Sequence, Tuple, Type

from pysat.formula import CNF
from pysat.solvers import (
    Cadical103,
    Cadical153,
    Cadical195,
    Glucose3,
    Glucose4,
    Glucose42,
    Gluecard3,
    Gluecard4,
    Lingeling,
    Minisat22,
    Solver,
)

SOLVER_MAP: Dict[str, Type[Solver]] = {
    "Minisat22": Minisat22,
    "Cadical103": Cadical103,
    "Cadical153": Cadical153,
    "Cadical195": Cadical195,
    "Gluecard3": Gluecard3,
    "Gluecard4": Gluecard4,
    "Glucose3": Glucose3,
    "Glucose4": Glucose4,
    "Glucose42": Glucose42,
    "Lingeling": Lingeling,
}


def load_cnf(cnf_path: str = "cnf.txt") -> List[List[int]]:
    """Load CNF clauses from a DIMACS-style text file."""
    cnf = CNF()
    with open(cnf_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith(("c", "p")):
                continue
            lits = [int(tok) for tok in line.split() if int(tok) != 0]
            if lits:
                cnf.append(lits)
    return [list(c) for c in cnf.clauses]


def load_node_groups(node_index_path: str = "node_index.txt") -> Dict[str, List[int]]:
    """Parse 1-based CNF variable indices grouped by INPUT, OUTPUT, and WIRE."""
    groups: Dict[str, List[int]] = {"INPUT": [], "OUTPUT": [], "WIRE": []}
    with open(node_index_path, "r", encoding="utf-8") as f:
        idx = 0
        for line in f:
            s = line.strip()
            if "(" in s and s.endswith(")"):
                idx += 1
                kind = s.split("(", 1)[0].strip()
                if kind in groups:
                    groups[kind].append(idx)
    return groups


def build_constraint_clauses(
    positives: Sequence[int],
    negatives: Sequence[int],
    node_index_path: Optional[str] = "node_index.txt",
) -> List[List[int]]:
    """Validate wire constraints and build unit clauses ([+v] and [-v])."""
    constrained = list(positives) + list(negatives)
    assert len(constrained) == len(set(constrained)) == 1624, "Expected 1624 unique constraints"
    assert all(65 <= v <= 3312 for v in constrained), "Constraint outside wire variable range"
    assert not (set(positives) & set(negatives)), "Conflicting 0 and 1 constraints on same wire"

    if node_index_path:
        kinds: List[str] = []
        with open(node_index_path, "r", encoding="utf-8") as f:
            for line in f:
                if "(" in line:
                    kinds.append(line.split("(")[0].strip())
        assert all(kinds[v - 1] == "WIRE" for v in constrained), "node_index WIRE check failed"

    return [[pos] for pos in positives] + [[-neg] for neg in negatives]


def find_first_n_solutions(
    solver_cls: Type[Solver],
    clauses: Sequence[Sequence[int]],
    n: Optional[int] = 100,
    target_vars: Optional[Sequence[int]] = None,
    timeout_s: Optional[float] = None,
) -> Tuple[List[Tuple[int, ...]], float, str]:
    """
    Find up to `n` unique solutions using `solver_cls`.
    If `n` is None, enumerates until UNSAT or `timeout_s` expires.
    Returns: (solutions, elapsed_seconds, status) where status is one of:
    'completed_unsat', 'completed_max_n', 'timeout'.
    """
    solutions: List[Tuple[int, ...]] = []
    seen = set()
    status = "completed_unsat"
    start = time.perf_counter()

    with solver_cls(bootstrap_with=clauses) as solver:
        while True:
            if n is not None and len(solutions) >= n:
                status = "completed_max_n"
                break
            if timeout_s is not None and (time.perf_counter() - start) >= timeout_s:
                status = "timeout"
                break

            if not solver.solve():
                status = "completed_unsat"
                break

            model = solver.get_model()
            if model is None:
                status = "completed_unsat"
                break

            if target_vars:
                model_set = set(model)
                proj = tuple(1 if v in model_set else 0 for v in target_vars)
                if proj not in seen:
                    seen.add(proj)
                    solutions.append(proj)
                blocking = [-v if bit == 1 else v for v, bit in zip(target_vars, proj)]
            else:
                proj = tuple(1 if lit > 0 else 0 for lit in sorted(model, key=abs))
                if proj not in seen:
                    seen.add(proj)
                    solutions.append(proj)
                blocking = [-lit for lit in model]

            solver.add_clause(blocking)

    elapsed = time.perf_counter() - start
    return solutions, elapsed, status


def benchmark_solvers(
    clauses: Sequence[Sequence[int]],
    solver_names: Iterable[str],
    n: Optional[int] = 100,
    target_vars: Optional[Sequence[int]] = None,
    timeout_s: Optional[float] = 30.0,
    sample_limit: int = 3,
) -> Tuple[List[dict], Dict[str, dict]]:
    """
    Run multiple PySAT solvers and return:
    1) summary rows for SAT.xlsx
    2) detailed per-solver records for JSON logging
    """
    rows: List[dict] = []
    raw_details: Dict[str, dict] = {}

    for name in solver_names:
        solver_cls = SOLVER_MAP.get(name)
        if solver_cls is None:
            rows.append({
                "SAT Solver": name,
                "# of Unique Solutions": "Unsupported solver",
                "Time (s)": None,
            })
            raw_details[name] = {
                "status": "unsupported",
                "unique_solutions": 0,
                "elapsed_s": None,
                "sample_solutions": [],
            }
            continue

        try:
            sols, elapsed, status = find_first_n_solutions(
                solver_cls=solver_cls,
                clauses=clauses,
                n=n,
                target_vars=target_vars,
                timeout_s=timeout_s,
            )
            count_label = f"{len(sols)} (timeout)" if status == "timeout" else len(sols)
            rows.append({
                "SAT Solver": name,
                "# of Unique Solutions": count_label,
                "Time (s)": round(elapsed, 6),
            })
            raw_details[name] = {
                "status": status,
                "unique_solutions": len(sols),
                "elapsed_s": round(elapsed, 6),
                "sample_solutions": [list(s) for s in sols[:sample_limit]],
            }
        except Exception as exc:
            rows.append({
                "SAT Solver": name,
                "# of Unique Solutions": f"Error: {exc}",
                "Time (s)": None,
            })
            raw_details[name] = {
                "status": "error",
                "error": str(exc),
                "unique_solutions": 0,
                "elapsed_s": None,
                "sample_solutions": [],
            }

    return rows, raw_details
