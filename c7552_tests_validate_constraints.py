import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

from find_solutions import build_constraint_clauses, load_cnf, load_constraints_from_json

clauses = load_cnf("data/cnf.txt")
assert len(clauses) == 5053, f"Expected 5053 base clauses, got {len(clauses)}"

positives, negatives = load_constraints_from_json("data/constraints.json")
c_clauses = build_constraint_clauses(
    positives,
    negatives,
    node_index_path="data/node_index.txt" if os.path.exists("data/node_index.txt") else None,
)
assert len(c_clauses) == 875, f"Expected 875 constraint clauses, got {len(c_clauses)}"
print("Validation passed: 5053 base clauses + 875 wire constraint clauses = 5928 total clauses.")
