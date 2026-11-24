
"""Controlled end-to-end test: naturally activate SDS Subset VI."""

from floorplan.blocks import Block
from floorplan.packing import calculate_layout, build_constraint_graph
from algorithms.classification import classify_blocks
from algorithms.slack_distribution import calculate_shaping_increments
from algorithms.shaping import apply_shaping


def main():
    # A is horizontally critical but vertically non-critical.
    # B determines the layout height.
    blocks = {
        "A": Block(
            name="A",
            area=20.0,
            min_width=2.0,
            max_width=8.0,
            min_height=2.0,
            max_height=10.0,
            width=5.0,
        ),
        "B": Block(
            name="B",
            area=20.0,
            min_width=1.0,
            max_width=5.0,
            min_height=2.0,
            max_height=10.0,
            width=2.0,
        ),
    }

    horizontal_constraints = []
    vertical_constraints = []
    outline_width = 5.0

    # Step 1: Calculate original layout and slacks.
    before = calculate_layout(
        blocks,
        horizontal_constraints,
        vertical_constraints,
        outline_width,
    )

    # Step 2: Classify blocks into SDS subsets.
    subsets = classify_blocks(
        blocks,
        before["horizontal_slack"],
        before["vertical_slack"],
    )

    print("=" * 68)
    print("CONTROLLED SUBSET VI ACTIVATION TEST")
    print("=" * 68)

    print(
        f"Before layout: width={before['width']:.6f}, "
        f"height={before['height']:.6f}"
    )

    print("Horizontal slack:", before["horizontal_slack"])
    print("Vertical slack  :", before["vertical_slack"])

    print("\nSubset classification:")
    for subset, names in subsets.items():
        print(f"  Subset {subset}: {names}")

    # Step 3: Get naturally classified Subset VI targets.
    vertical_targets = subsets["VI"]

    if not vertical_targets:
        raise AssertionError(
            "No block was classified into Subset VI."
        )

    # Step 4: Calculate vertical shaping increments.
    v_graph = build_constraint_graph(
        blocks,
        vertical_constraints,
        "vertical",
    )

    vertical_increments = calculate_shaping_increments(
        blocks=blocks,
        graph=v_graph,
        slack=before["vertical_slack"],
        target_blocks=vertical_targets,
        axis="vertical",
        beta=0.90,
    )

    print("\nVertical targets:", vertical_targets)
    print("Vertical increments:", vertical_increments)

    # Save original dimensions and areas.
    old_areas = {
        name: block.area
        for name, block in blocks.items()
    }

    old_heights = {
        name: block.height
        for name, block in blocks.items()
    }

    # Step 5: Apply vertical shaping.
    apply_shaping(
        blocks,
        horizontal_increments={},
        vertical_increments=vertical_increments,
    )

    # Step 6: Recalculate layout.
    after = calculate_layout(
        blocks,
        horizontal_constraints,
        vertical_constraints,
        outline_width,
    )

    print("\nActual vertical dimension changes:")

    for name in vertical_targets:
        print(
            f"{name}: "
            f"height {old_heights[name]:.6f} -> "
            f"{blocks[name].height:.6f}, "
            f"width={blocks[name].width:.6f}"
        )

    print(
        f"\nAfter layout: width={after['width']:.6f}, "
        f"height={after['height']:.6f}"
    )

    print(
        f"Width change: "
        f"{after['width'] - before['width']:.6f}"
    )

    # Step 7: Verify the results.
    for name in vertical_targets:
        assert vertical_increments[name] > 0.0
        assert abs(blocks[name].area - old_areas[name]) < 1e-8
        assert blocks[name].height > old_heights[name]

    assert after["feasible"]
    assert after["width"] < before["width"]

    print("\nPASS: Subset VI classification verified.")
    print("PASS: Positive vertical increment verified.")
    print("PASS: Block area preservation verified.")
    print("PASS: Layout width reduction verified.")


if __name__ == "__main__":
    main()
