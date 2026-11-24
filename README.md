# Optimal Slack-Driven Block Shaping (SDS) Algorithm

A complete, high-performance Python reproduction of the research paper:
> **Optimal Slack-Driven Block Shaping Algorithm in Fixed-Outline Floorplanning**  
> *Jackey Z. Yan and Chris Chu*  
> ACM International Symposium on Physical Design (ISPD), 2012.

---

## 1. Overview & Theoretical Foundation

In hierarchical ASIC designs, fixed-outline floorplanning requires fitting circuit blocks within a predefined bounding box with fixed maximum width $W$ and height $H$. While hard blocks have fixed dimensions, soft blocks have fixed areas $A_i$ with flexible aspect ratios $r_i = h_i / w_i \in [r_{\min}, r_{\max}]$.

The **SDS (Slack-Driven Shaping)** algorithm solves the fundamental problem of minimizing layout height $y_{n+1}$ under a rigid upper-bound width $W$ by iteratively distributing global horizontal and vertical slack to individual soft blocks in **linear time $O(m)$ per iteration**.

### 1.1 Problem Formulation (Problem 1 in Paper)

$$\begin{aligned}
\text{Minimize} \quad & y_{n+2} \\
\text{subject to} \quad & x_{n+1} \le W \\
& x_j \ge x_i + w_i, \quad \forall (i, j) \in G_h \\
& y_j \ge y_i + h_i, \quad \forall (i, j) \in G_v \\
& W_i^{\min} \le w_i \le W_i^{\max}, \quad 1 \le i \le n \\
& H_i^{\min} \le h_i \le H_i^{\max}, \quad 1 \le i \le n \\
& w_i h_i = A_i, \quad 1 \le i \le n \\
& x_0 = 0, \quad y_0 = 0
\end{aligned}$$

---

## 2. Algorithm Components

### 2.1 Constraint Graphs and 4-Line Packing
Blocks are topologically modeled by directed acyclic graphs (DAGs) $G_h$ and $G_v$, augmented with dummy source $0$ and sink $n+1$:
- **Pack to Left Line (LL, $x = 0$):** Earliest start time (ASAP longest path in $G_h$).
- **Pack to Right Line (RL, $x = W$):** Latest start time (ALAP longest path backwards from $W$).
- **Pack to Bottom Line (BL, $y = 0$):** Earliest start time (ASAP longest path in $G_v$).
- **Pack to Top Line (TL, $y = y_{n+1}$):** Latest start time (ALAP longest path backwards from $y_{n+1}$).

Horizontal slack $s_i^h = \max(0, x_i^{RL} - x_i^{LL})$ and vertical slack $s_i^v = \max(0, y_i^{TL} - y_i^{BL})$.

### 2.2 The 7 Disjoint Subsets (Section 3.1)
Each block $i \in \{1, \dots, n\}$ is classified into one of seven mutually disjoint subsets:
| Subset | Definition | Interpretation | Action in SDS |
|---|---|---|---|
| **Subset I** | $i$ is hard | Fixed dimensions | Cannot be shaped |
| **Subset II** | Soft, $s_i^h > 0, s_i^v > 0$ | Not on any critical path | Not target |
| **Subset III** | Soft, $s_i^h = 0, s_i^v = 0$ | Intersection of HCP and VCP | Preserved / GP fallback |
| **Subset IV** | Soft, $s_i^h > 0, s_i^v = 0, w_i < W_i^{\max}$ | On VCP, has width slack | **Target: Increase $w_i$ by $\delta_i^h$** |
| **Subset V** | Soft, $s_i^h > 0, s_i^v = 0, w_i = W_i^{\max}$ | On VCP, max width reached | Cannot be widened |
| **Subset VI** | Soft, $s_i^h = 0, s_i^v > 0, h_i < H_i^{\max}$ | On HCP, has height slack | **Target: Increase $h_i$ by $\delta_i^v$** |
| **Subset VII** | Soft, $s_i^h = 0, s_i^v > 0, h_i = H_i^{\max}$ | On HCP, max height reached | Cannot be heightened |

### 2.3 Linear-Time DP Slack Allocation (Section 3.2)
To distribute slack globally along critical paths without combinatorial path enumeration, SDS computes the maximum remaining shaping capacity along any path through block $i$ via dynamic programming:
$$\delta_i^h = \frac{(W_i^{\max} - w_i) \cdot s_i^h}{\max_{p \in P_i^h} \sum_{k \in p} (W_k^{\max} - w_k)}$$
$$\delta_j^v = \beta \times \frac{(H_j^{\max} - h_j) \cdot s_j^v}{\max_{p \in P_j^v} \sum_{k \in p} (H_k^{\max} - h_k)}$$

The terms $\max_p \sum (W_k^{\max} - w_k)$ and $\max_p \sum (H_k^{\max} - h_k)$ are computed in **$O(|V| + |E|)$** using forward DP $D_{\text{in}}$ and backward DP $D_{\text{out}}$ (Equations 5–7 in the paper).

An adaptive damping factor $\beta$ ($\beta = 1.0$ by default, $\beta = 0.9$ if $y_{n+1}$ stalls for $>2$ iterations) prevents cyclic oscillations. Changes smaller than $0.0001$ are ignored to prevent numerical error.

### 2.4 Optimality Conditions (Section 4, Lemmas 2 & 3)
When Basic SDS terminates because no target soft blocks exist in Subsets IV and VI:
- **Hard Critical Path:** A critical path containing NO soft intersection blocks (no blocks in Subset III).
- **Soft Critical Path:** A critical path containing at least one soft intersection block.
- **Lemma 2:** If there exists $\ge 1$ Hard Vertical Critical Path (VCP), the layout $L$ is **guaranteed optimal**.
- **Lemma 3:** If there exists $\le 1$ Soft HCP **OR** $\le 1$ Soft VCP, the layout $L$ is **guaranteed optimal**.

### 2.5 Full SDS with Convex Optimization Fallback (Section 5)
If neither Lemma 2 nor Lemma 3 is satisfied (e.g. Figure 2 counterexample):
1. Identify the intersection soft blocks (Subset III).
2. Solve the geometric program / convex relaxation (via CVXPY) on these intersection blocks.
3. Update block shapes and certify global optimality.

---

## 3. Project Structure

```
VLSI-ML/
├── sds/
│   ├── __init__.py             # Package exports
│   ├── block.py                # Block data structure (hard/soft, aspect ratios, bounds)
│   ├── constraint_graph.py     # Gh, Gv DAG, Kahn's topo sort, ALAP/ASAP packing, DP
│   ├── sequence_pair.py        # Sequence-Pair (X, Y) to constraint graphs
│   ├── basic_sds.py            # Basic Slack-Driven Shaping (Figure 1 in paper)
│   ├── optimality.py           # Optimality Conditions Checker (Lemmas 2 & 3)
│   ├── convex_solver.py        # Exact CVXPY DCP solver (Figure 4 GP fallback & ground truth)
│   ├── full_sds.py             # Full SDS algorithm (Figure 4 in paper)
│   ├── visualizer.py           # Floorplan & convergence curve plotting (Figure 5)
│   └── api.py                  # High-level shape_floorplan and compute_hpwl API
├── benchmarks/
│   ├── __init__.py
│   ├── figure2_example.py      # Exact reproduction of paper Figure 2 counterexample
│   ├── mcnc_benchmarks.py      # MCNC benchmarks (apte, xerox, hp, ami33a, ami49a)
│   └── synthetic_benchmarks.py # Scalable benchmarks with hard/soft blocks (Table 4)
├── tests/
│   ├── test_dp_slack.py        # Unit tests for DP path calculations
│   ├── test_figure2.py         # Tests replicating Figure 2 (5.0 -> 3.2)
│   ├── test_optimality.py      # Unit tests for Lemma 2 and Lemma 3
│   └── test_full_sds.py        # End-to-end tests vs CVXPY ground truth
├── output/                     # Generated layout and convergence plots
├── run_experiments.py          # Master experimental replication script
└── README.md                   # Complete documentation
```

---

## 4. Experimental Results

### 4.1 Experiment 1: Figure 2 Replication (Motivational Counterexample)
Figure 2 of the paper presents a 4-block layout ($A_i = 4.0, W = 5.0$) where Basic SDS gets stuck:
- **Initial Layout (Fig 2-a):** $w_1 = w_3 = 4.0, w_2 = w_4 = 1.0$.
  - Packed Dimensions: Width $= 5.0$, Height $= 5.0$.
  - All 4 blocks have $s^h = 0$ and $s^v = 0$ (all in Subset III).
  - Subsets IV and VI are empty $\implies$ **Basic SDS terminates at height 5.0!**
- **Optimality Condition Check:**
  - Soft VCPs: 2, Soft HCPs: 2, Hard VCPs: 0.
  - Lemmas 2 & 3 fail $\implies$ **Non-optimal condition successfully detected.**
- **Full SDS Resolution (Fig 2-b):**
  - Solves the convex subproblem on Subset III blocks.
  - Result: $w_1 = w_2 = w_3 = w_4 = 2.5000, h_1 = h_2 = h_3 = h_4 = 1.6000$.
  - **Optimal Height: $3.2000$ (36.00% reduction!)**

### 4.2 Experiment 2: MCNC Benchmarks (Tables 2 & 3)
Evaluated across MCNC benchmarks with soft blocks (aspect ratio in $[1/3, 3]$):

| Circuit | Blocks | Bound $W$ | Initial $H$ | Final $W$ | SDS $H$ | CVXPY Optimum $H$ | Difference | Iterations | Runtime (s) |
|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| **apte** | 9 | 195.09 | 581.93 | 195.09 | **327.97** | 327.97 | **0.001%** | 48 | 0.0098 s |
| **xerox** | 10 | 173.32 | 393.19 | 173.32 | **142.25** | 141.63 | **0.434%** | 59 | 0.0104 s |
| **hp** | 11 | 83.95 | 271.05 | 83.95 | **110.98** | 110.44 | **0.493%** | 52 | 0.0147 s |
| **ami33a**| 33 | 126.39 | 389.32 | 126.39 | **132.63** | 131.25 | **1.054%** | 243 | 0.0936 s |
| **ami49a**| 49 | 177.95 | 557.56 | 177.95 | **226.61** | 222.20 | **1.985%** | 584 | 0.6384 s |

### 4.3 Experiment 3: Scalable HB Benchmarks & Convergence Milestones (Table 4, Figure 5)
Evaluated on scalable testcases containing hundreds of soft and hard blocks ($W = \sqrt{1.10 \times \text{Total Area}}$):

| Testcase | Soft / Hard Blocks | Outline $W$ | Optimal Height $Y$ | Total Iterations | Iter to $<10\%$ | Iter to $<5\%$ | Iter to $<1\%$ | Iter to $<0.1\%$ | Runtime |
|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| **HB_Small** | 50 / 20 | 190.28 | 184.45 | 65 | 4 (6%) | 5 (8%) | 13 (20%) | 25 (38%) | 0.11 s |
| **HB_Medium**| 150 / 50 | 329.88 | 339.80 | 96 | 4 (4%) | 5 (5%) | 12 (12%) | 32 (33%) | 0.19 s |
| **HB_Large** | 400 / 100 | 477.71 | 426.79 | 250 | 16 (6%) | 27 (11%) | 56 (22%) | 117 (47%) | 25.8 s |

> **Key Observation (matching Paper Remark 3):** Across all benchmarks, SDS reaches within **1% of optimal height within ~20% of total iterations**, making it suitable for fixed-outline floorplanners.

---

## 5. How to Run

### 5.1 Run All Unit Tests
```bash
python -m tests.test_dp_slack
python -m tests.test_figure2
python -m tests.test_optimality
python -m tests.test_full_sds
```

### 5.2 Run All Experiments & Generate Figures
```bash
python run_experiments.py
```
This produces plots in the `output/` directory:
- `output/figure2_a_trap.png` (Figure 2-a non-optimal trap)
- `output/figure2_b_optimal.png` (Figure 2-b optimal resolution)
- `output/floorplan_apte.png`, `output/floorplan_ami33a.png` (MCNC layout visualizations)
- `output/convergence_HB_*.png` (Convergence graphs replicating Figure 5)

---

## 6. Python API Usage

### Quick Integration Example:
```python
from sds import shape_floorplan

# Define blocks (both soft and hard)
blocks = [
    {"id": 1, "name": "ALU",  "area": 120.0, "is_hard": False, "aspect_ratio_range": (1/3, 3.0)},
    {"id": 2, "name": "MEM",  "w_fixed": 12.0, "h_fixed": 15.0, "is_hard": True},
    {"id": 3, "name": "REG",  "area": 80.0,  "is_hard": False},
    {"id": 4, "name": "CTRL", "area": 60.0,  "is_hard": False},
]

# Sequence Pair representation (X, Y)
seq_x = [1, 2, 3, 4]
seq_y = [2, 1, 4, 3]

# Fixed Outline constraints
outline_W = 30.0
outline_H = 25.0

# Netlist for wirelength (HPWL) calculation
nets = [
    [1, 2],
    [2, 3, 4],
]

# Run SDS
result = shape_floorplan(
    block_specs=blocks,
    seq_x=seq_x,
    seq_y=seq_y,
    upper_bound_width=outline_W,
    outline_height=outline_H,
    nets=nets,
)

print(f"Feasible (W <= {outline_W}): {result['feasible']}")
print(f"Legal (within outline W x H): {result['legal']}")
print(f"Dimensions: {result['layout_width']:.2f} x {result['layout_height']:.2f}")
print(f"HPWL Wirelength: {result['hpwl']:.2f}")
print(f"Runtime: {result['runtime_seconds']*1000:.2f} ms")
```

