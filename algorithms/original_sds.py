
from floorplan.packing import calculate_layout, build_constraint_graph
from floorplan.constraints import get_shaping_targets, get_mib_groups
from algorithms.classification import classify_blocks
from algorithms.slack_distribution import calculate_shaping_increments
from algorithms.shaping import apply_shaping
from algorithms.initialization import initialize_blocks_for_sds


def filter_targets(targets, blocks, placement_constraints):
    if placement_constraints is None:
        return list(targets)

    allowed = set(
        get_shaping_targets(
            list(blocks.keys()),
            placement_constraints
        )
    )

    mib_groups = get_mib_groups(placement_constraints)

    mib_blocks = {
        name
        for group in mib_groups.values()
        for name in group
    }

    return [
        name for name in targets
        if name in allowed and name not in mib_blocks
    ]


def print_diagnostics(
    iteration,
    blocks,
    horizontal_slack,
    vertical_slack,
    subsets,
):
    print("\n" + "=" * 75)
    print(f"DETAILED SDS DIAGNOSTICS - ITERATION {iteration}")
    print("=" * 75)

    print("\nBLOCK DIMENSIONS AND SLACK")

    for name, block in blocks.items():
        sh = horizontal_slack.get(name, 0.0)
        sv = vertical_slack.get(name, 0.0)

        effective_max_width = getattr(
            block, "effective_max_width", block.max_width
        )
        effective_max_height = getattr(
            block, "effective_max_height", block.max_height
        )

        print(
            f"{name}: "
            f"W={block.width:.5f}, "
            f"H={block.height:.5f}, "
            f"SH={sh:.8f}, "
            f"SV={sv:.8f}, "
            f"MaxW={effective_max_width:.5f}, "
            f"MaxH={effective_max_height:.5f}"
        )

    print("\nSEVEN-SUBSET CLASSIFICATION")

    for subset_name, members in subsets.items():
        print(f"Subset {subset_name}: {list(members)}")


def print_increment_diagnostics(
    horizontal_increments,
    vertical_increments,
):
    print("\nHORIZONTAL SHAPING INCREMENTS")

    if horizontal_increments:
        for name, delta in horizontal_increments.items():
            print(f"{name}: +{delta:.8f} width")
    else:
        print("No horizontal increments.")

    print("\nVERTICAL SHAPING INCREMENTS")

    if vertical_increments:
        for name, delta in vertical_increments.items():
            print(f"{name}: +{delta:.8f} height")
    else:
        print("No vertical increments.")


def run_original_sds(
    blocks,
    hcg_edges,
    vcg_edges,
    outline_width,
    max_iterations=200,
    beta=1.0,
    tolerance=1e-6,
    placement_constraints=None,
):
    # Preserve fixed, preplaced and MIB blocks.
    preserve_blocks = set()

    if placement_constraints is not None:
        preserve_blocks = {
            name
            for name, info in placement_constraints.items()
            if info.get("fixed", False)
            or info.get("preplaced", False)
        }

        mib_groups = get_mib_groups(placement_constraints)

        preserve_blocks.update(
            name
            for group in mib_groups.values()
            for name in group
        )

    initialize_blocks_for_sds(
        blocks,
        preserve_blocks=preserve_blocks
    )

    history = []

    print("\n" + "#" * 75)
    print("STARTING ORIGINAL SDS")
    print("#" * 75)
    print(f"Outline width: {outline_width}")
    print(f"Maximum iterations: {max_iterations}")
    print(f"Beta: {beta}")
    print(f"Tolerance: {tolerance}")

    for iteration in range(1, max_iterations + 1):

        # Step 1: Calculate current layout and slack.
        result = calculate_layout(
            blocks,
            hcg_edges,
            vcg_edges,
            outline_width
        )

        horizontal_slack = result["horizontal_slack"]
        vertical_slack = result["vertical_slack"]

        current_width = result["width"]
        current_height = result["height"]

        # Step 2: Classify blocks.
        subsets = classify_blocks(
            blocks,
            horizontal_slack,
            vertical_slack,
            tolerance=tolerance,
        )

        # Step 3: Select eligible targets.
        horizontal_targets = filter_targets(
            subsets["IV"],
            blocks,
            placement_constraints
        )

        vertical_targets = filter_targets(
            subsets["VI"],
            blocks,
            placement_constraints
        )

        print("\n" + "-" * 75)
        print(f"ITERATION {iteration}")
        print("-" * 75)

        print(
            f"Current layout: "
            f"Width={current_width:.6f}, "
            f"Height={current_height:.6f}"
        )

        print("Subset IV targets:", horizontal_targets)
        print("Subset VI targets:", vertical_targets)

        print(
            f"Target counts: "
            f"Horizontal={len(horizontal_targets)}, "
            f"Vertical={len(vertical_targets)}"
        )

        # Detailed block diagnostics on every iteration.
        print_diagnostics(
            iteration,
            blocks,
            horizontal_slack,
            vertical_slack,
            subsets,
        )

        if not horizontal_targets and not vertical_targets:
            print(
                "\nSDS STOPPED: "
                "No eligible Subset IV or Subset VI targets remain."
            )

            history.append({
                "iteration": iteration,
                "width": current_width,
                "height": current_height,
                "horizontal_targets": [],
                "vertical_targets": [],
                "horizontal_increments": {},
                "vertical_increments": {},
                "height_after": current_height,
                "height_change": 0.0,
            })

            break

        # Step 4: Build constraint graphs.
        h_graph = build_constraint_graph(
            blocks,
            hcg_edges,
            "horizontal"
        )

        v_graph = build_constraint_graph(
            blocks,
            vcg_edges,
            "vertical"
        )

        # Step 5: Calculate horizontal increments.
        h_increments = calculate_shaping_increments(
            blocks,
            h_graph,
            horizontal_slack,
            horizontal_targets,
            axis="horizontal",
        )

        # Step 6: Calculate vertical increments.
        v_increments = calculate_shaping_increments(
            blocks,
            v_graph,
            vertical_slack,
            vertical_targets,
            axis="vertical",
            beta=beta,
        )

        print_increment_diagnostics(
            h_increments,
            v_increments,
        )

        all_increments = (
            list(h_increments.values())
            + list(v_increments.values())
        )

        maximum_increment = max(
            all_increments,
            default=0.0
        )

        if maximum_increment < 0.0001:
            print(
                "\nSDS STOPPED: "
                "All shaping increments are below 0.0001."
            )

            history.append({
                "iteration": iteration,
                "width": current_width,
                "height": current_height,
                "horizontal_targets": horizontal_targets.copy(),
                "vertical_targets": vertical_targets.copy(),
                "horizontal_increments": h_increments.copy(),
                "vertical_increments": v_increments.copy(),
                "height_after": current_height,
                "height_change": 0.0,
            })

            break

        # Step 7: Save dimensions before shaping.
        dimensions_before = {
            name: (block.width, block.height)
            for name, block in blocks.items()
        }

        # Step 8: Apply shaping.
        apply_shaping(
            blocks,
            h_increments,
            v_increments
        )

        # Step 9: Print actual block dimension changes.
        print("\nACTUAL BLOCK DIMENSION CHANGES")

        for name, block in blocks.items():
            old_width, old_height = dimensions_before[name]

            if (
                abs(block.width - old_width) > 1e-12
                or abs(block.height - old_height) > 1e-12
            ):
                print(
                    f"{name}: "
                    f"W {old_width:.6f} -> {block.width:.6f}, "
                    f"H {old_height:.6f} -> {block.height:.6f}"
                )

        # Step 10: Recalculate layout after shaping.
        updated_result = calculate_layout(
            blocks,
            hcg_edges,
            vcg_edges,
            outline_width
        )

        updated_height = updated_result["height"]
        height_change = updated_height - current_height

        print("\nLAYOUT HEIGHT COMPARISON")
        print(f"Before shaping: {current_height:.8f}")
        print(f"After shaping : {updated_height:.8f}")
        print(f"Height change : {height_change:+.8f}")

        history.append({
            "iteration": iteration,
            "width": current_width,
            "height": current_height,
            "horizontal_targets": horizontal_targets.copy(),
            "vertical_targets": vertical_targets.copy(),
            "horizontal_increments": h_increments.copy(),
            "vertical_increments": v_increments.copy(),
            "height_after": updated_height,
            "height_change": height_change,
        })

    # Final layout.
    final_result = calculate_layout(
        blocks,
        hcg_edges,
        vcg_edges,
        outline_width
    )

    print("\n" + "#" * 75)
    print("FINAL ORIGINAL SDS RESULT")
    print("#" * 75)

    print(f"Final width : {final_result['width']:.6f}")
    print(f"Final height: {final_result['height']:.6f}")

    print("\nTotal iterations:", len(history))

    vertical_iterations = sum(
        1
        for item in history
        if any(
            delta > 0
            for delta in item["vertical_increments"].values()
        )
    )

    print(
        "Iterations with positive vertical shaping:",
        vertical_iterations
    )

    return blocks, final_result, history
