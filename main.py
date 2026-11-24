from floorplan.blocks import Block
from algorithms.original_sds import run_original_sds

# 1. Create blocks
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


# 2. Define constraint graphs
horizontal_constraints = [("A", "B"), ("A", "C")]

vertical_constraints = [("B", "C")]


# 3. Define fixed outline width
outline_width = 12


# 4. Run iterative Original SDS
blocks, result, history = run_original_sds(
    blocks=blocks,
    hcg_edges=horizontal_constraints,
    vcg_edges=vertical_constraints,
    outline_width=outline_width,
    max_iterations=50,
    beta=1.0,
)


# 5. Display final layout results
print("\n========== FINAL SDS RESULTS ==========")

print(f"Layout Width: {result['width']:.2f}")
print(f"Layout Height: {result['height']:.2f}")
print(f"Outline Width: {result['outline_width']:.2f}")
print(f"Width Feasible: {result['feasible']}")


# 6. Display final block dimensions
print("\nFINAL BLOCK DIMENSIONS")

for block in blocks.values():
    print(block.display())


# 7. Display final block positions
print("\nFINAL BLOCK POSITIONS")

for name, position in result["placements"].items():
    print(
        f"{name}: "
        f"x={position['x']:.2f}, "
        f"y={position['y']:.2f}, "
        f"width={position['width']:.2f}, "
        f"height={position['height']:.2f}"
    )


# 8. Display critical paths
print("\nFINAL CRITICAL PATHS")

print("HCP:", result["horizontal_critical_path"])
print("VCP:", result["vertical_critical_path"])


# 9. Display iteration history
print("\n========== ITERATION HISTORY ==========")

for item in history:
    print(
        f"Iteration {item['iteration']}: "
        f"Width={item['width']:.4f}, "
        f"Height={item['height']:.4f}, "
        f"Subset IV={item['horizontal_targets']}, "
        f"Subset VI={item['vertical_targets']}"
    )
