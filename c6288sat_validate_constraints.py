import os
from find_solutions import build_constraint_clauses, load_cnf
from run_solvers import NEGATIVES, POSITIVES

clauses = load_cnf("cnf.txt")
assert len(clauses) == 8913, f"Expected 8913 base clauses, got {len(clauses)}"
c_clauses = build_constraint_clauses(
    POSITIVES,
    NEGATIVES,
    node_index_path="node_index.txt" if os.path.exists("node_index.txt") else None,
)
assert len(c_clauses) == 1624, f"Expected 1624 constraint clauses, got {len(c_clauses)}"
print("Validation passed: 8913 base clauses + 1624 wire constraint clauses.")
