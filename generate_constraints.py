import json, math, re, sys

d, c, outjson = sys.argv[1], sys.argv[2], sys.argv[3]
names, kinds = [], {}
for line in open(f"{d}/node_index.txt"):
    m = re.match(r"\s*(INPUT|OUTPUT|WIRE)\((.+?)\)", line)
    if m:
        names.append(m.group(2)); kinds[m.group(2)] = m.group(1)
idx = {n: i + 1 for i, n in enumerate(names)}
ins = [n for n in names if kinds[n] == "INPUT"]
wires = [n for n in names if kinds[n] == "WIRE"]
gates = {}
for line in open(f"{d}/syn_flat_{c}.bench"):
    m = re.match(r"\s*(\S+)\s*=\s*(\w+)\((.*)\)", line)
    if m:
        gates[m.group(1)] = (m.group(2).lower(), [x.strip() for x in m.group(3).split(",")])
for line in open(f"{d}/syn_flat_{c}.v"):
    m = re.match(r"\s*assign\s+(\S+)\s*=\s*(\S+?)\s*;", line)
    if m and m.group(1) not in gates:
        gates[m.group(1)] = ("buf", [m.group(2)])

order, seen = [], set()
sys.setrecursionlimit(100000)
def visit(n):
    if n in seen or n not in gates: return
    seen.add(n)
    for a in gates[n][1]: visit(a)
    order.append(n)
for n in names: visit(n)

X = None
def t_and(v):
    if any(x is False for x in v): return False
    return True if all(x is True for x in v) else X
def t_or(v):
    if any(x is True for x in v): return True
    return False if all(x is False for x in v) else X
def t_not(x): return X if x is X else (not x)
T = {"and": t_and, "or": t_or, "nand": lambda v: t_not(t_and(v)),
     "nor": lambda v: t_not(t_or(v)), "not": lambda v: t_not(v[0]), "buf": lambda v: v[0]}

def tsim(fixed):
    val = {n: fixed.get(n, X) for n in ins}
    for n in order:
        g, a = gates[n]; val[n] = T[g]([val[x] for x in a])
    return val

target = math.ceil(len(wires) / 2)
fixed = {}
def ndet(val): return sum(1 for w in wires if val[w] is not X)
cur = ndet(tsim(fixed))
while cur < target:
    best = None
    for n in ins:
        if n in fixed: continue
        for b in (False, True):
            f2 = dict(fixed); f2[n] = b
            k = ndet(tsim(f2))
            if best is None or k > best[0]: best = (k, n, b)
    cur, n, b = best; fixed[n] = b
    print(f"  fix {n}={int(b)} -> {cur} wires determined")

val = tsim(fixed)
det = [w for w in wires if val[w] is not X]
chosen = sorted(det, key=lambda w: idx[w])[:target]
cons = [{"signal": w, "var": idx[w], "value": int(val[w]),
         "clause": [idx[w] if val[w] else -idx[w]]} for w in chosen]
json.dump({"circuit": c, "n_wires": len(wires), "target": target,
           "fixed_inputs_used_to_pick": {k: int(v) for k, v in fixed.items()},
           "free_inputs": len(ins) - len(fixed), "constraints": cons},
          open(outjson, "w"), indent=1)
print(f"{c}: wires={len(wires)} constrained={len(cons)} ({len(cons)/len(wires):.1%}); "
      f"inputs fixed for selection={len(fixed)}, free inputs={len(ins)-len(fixed)}; "
      f"ones={sum(x['value'] for x in cons)} zeros={len(cons)-sum(x['value'] for x in cons)}")
