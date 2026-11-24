
from floorplan.blocks import Block
from algorithms.complete_sds import run_complete_sds


# ==================================================
# 1. CREATE BLOCKS
# ==================================================

blocks = {
    "A": Block(
        name="A",
        area=20,
        min_width=4,
        max_width=10,
        min_height=2,
        max_height=5,
        width=5,
    ),

    "B": Block(
        name="B",
        area=24,
        min_width=4,
        max_width=8,
        min_height=3,
        max_height=6,
        width=6,
    ),

    "C": Block(
        name="C",
        area=12,
        min_width=3,
        max_width=6,
        min_height=2,
        max_height=4,
        width=3,
    ),
}


# ==================================================
# 2. DEFINE CONSTRAINT GRAPHS
# ==================================================

horizontal_constraints = [
    ("A", "B"),
    ("A", "C"),
]

vertical_constraints = [
    ("B", "C"),
]


# ==================================================
# 3. FIXED OUTLINE WIDTH
# ==================================================

outline_width = 12


# ==================================================
# 4. RUN COMPLETE SDS
# ==================================================

blocks, result, history, diagnostics = run_complete_sds(
    blocks=blocks,
    hcg_edges=horizontal_constraints,
    vcg_edges=vertical_constraints,
    outline_width=outline_width,
    max_iterations=50,
    beta=1.0,
    placement_constraints=None,
    max_gp_iterations=5,
    verbose=False,
)


# ==================================================
# 5. DISPLAY FINAL LAYOUT RESULTS
# ==================================================

print("\n========== FINAL COMPLETE SDS RESULTS ==========")

print(f"Layout Width: {result['width']:.4f}")
print(f"Layout Height: {result['height']:.4f}")
print(f"Outline Width: {result['outline_width']:.4f}")
print(f"Width Feasible: {result['feasible']}")


# ==================================================
# 6. DISPLAY FINAL BLOCK DIMENSIONS
# ==================================================

print("\n========== FINAL BLOCK DIMENSIONS ==========")

for block in blocks.values():
    print(block.display())


# ==================================================
# 7. DISPLAY FINAL BLOCK POSITIONS
# ==================================================

print("\n========== FINAL BLOCK POSITIONS ==========")

for name, position in result["placements"].items():
    print(
        f"{name}: "
        f"x={position['x']:.4f}, "
        f"y={position['y']:.4f}, "
        f"width={position['width']:.4f}, "
        f"height={position['height']:.4f}"
    )


# ==================================================
# 8. DISPLAY FINAL CRITICAL PATHS
# ==================================================

print("\n========== FINAL CRITICAL PATHS ==========")

print(
    "HCP:",
    result.get("horizontal_critical_path", "Not available")
)

print(
    "VCP:",
    result.get("vertical_critical_path", "Not available")
)


# ==================================================
# 9. DISPLAY ITERATION HISTORY
# ==================================================

print("\n========== ITERATION HISTORY ==========")

for index, item in enumerate(history, start=1):

    if item.get("phase") == "GP":
        print(
            f"GP Iteration {item['iteration']}: "
            f"Width={item['width']:.4f}, "
            f"Height={item['height']:.4f}"
        )

    else:
        print(
            f"Iteration {item.get('iteration', index)}: "
            f"Width={item['width']:.4f}, "
            f"Height={item['height']:.4f}, "
            f"Subset IV={item.get('horizontal_targets', 'N/A')}, "
            f"Subset VI={item.get('vertical_targets', 'N/A')}"
        )


# ==================================================
# 10. DISPLAY OPTIMALITY DIAGNOSTICS
# ==================================================

print("\n========== OPTIMALITY DIAGNOSTICS ==========")

print("Optimality satisfied:", diagnostics["optimal"])

print(
    "GP attempts:",
    diagnostics["gp_attempts"]
)

print(
    "GP successfully applied:",
    diagnostics["gp_applied"]
)

print(
    "Termination reason:",
    diagnostics["termination_reason"]
)


if diagnostics["optimality_checks"]:

    last_check = diagnostics["optimality_checks"][-1]

    print("\nLemma 2 satisfied:",
        last_check["lemma_2_satisfied"])

    print("Lemma 3 satisfied:",
        last_check["lemma_3_satisfied"])

    print("Hard VCP exists:",
        last_check["hard_vcp_exists"])

    print("Soft HCP count:",
        last_check["soft_hcp_count"])

    print("Soft VCP count:",
        last_check["soft_vcp_count"])


# ==================================================
# 11. FINAL SUMMARY
# ==================================================

print("\n========== PROJECT SUMMARY ==========")

print(f"Final Width: {result['width']:.4f}")
print(f"Final Height: {result['height']:.4f}")
print(f"Width Feasible: {result['feasible']}")
print(f"Optimality Condition: {diagnostics['optimal']}")
print(f"GP Applied: {diagnostics['gp_applied']}")

if result["feasible"]:
    print("\nSUCCESS: Layout satisfies the outline width constraint.")
else:
    print("\nWARNING: Layout violates the outline width constraint.")
