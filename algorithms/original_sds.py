
from floorplan.packing import calculate_layout, build_constraint_graph
from floorplan.constraints import get_shaping_targets, get_mib_groups
from algorithms.classification import classify_blocks
from algorithms.slack_distribution import calculate_shaping_increments
from algorithms.shaping import apply_shaping
from algorithms.initialization import initialize_blocks_for_sds


def filter_targets(targets, blocks, placement_constraints):
    if placement_constraints is None:
        return list(targets)

    allowed = set(get_shaping_targets(list(blocks.keys()), placement_constraints))

    # MIB members are excluded because they must retain identical shapes.
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
    # Keep fixed/preplaced blocks and all MIB members at their reference shape.
    preserve_blocks = set()
    if placement_constraints is not None:
        preserve_blocks = {
            name for name, info in placement_constraints.items()
            if info.get("fixed", False) or info.get("preplaced", False)
        }
        mib_groups = get_mib_groups(placement_constraints)
        preserve_blocks.update(
            name for group in mib_groups.values() for name in group
        )

    initialize_blocks_for_sds(blocks, preserve_blocks=preserve_blocks)
    history = []

    for iteration in range(1, max_iterations + 1):
        result = calculate_layout(
            blocks, hcg_edges, vcg_edges, outline_width
        )

        horizontal_slack = result["horizontal_slack"]
        vertical_slack = result["vertical_slack"]

        subsets = classify_blocks(
            blocks,
            horizontal_slack,
            vertical_slack,
            tolerance=tolerance,
        )

        horizontal_targets = filter_targets(
            subsets["IV"], blocks, placement_constraints
        )
        vertical_targets = filter_targets(
            subsets["VI"], blocks, placement_constraints
        )

        history.append({
            "iteration": iteration,
            "width": result["width"],
            "height": result["height"],
            "horizontal_targets": horizontal_targets.copy(),
            "vertical_targets": vertical_targets.copy(),
        })

        print(
            f"Iteration {iteration}: "
            f"Width={result['width']:.4f}, "
            f"Height={result['height']:.4f}"
        )
        print("Subset IV targets:", horizontal_targets)
        print("Subset VI targets:", vertical_targets)

        if not horizontal_targets and not vertical_targets:
            print("SDS stopped: no eligible target blocks remain.")
            break

        h_graph = build_constraint_graph(
            blocks, hcg_edges, "horizontal"
        )
        v_graph = build_constraint_graph(
            blocks, vcg_edges, "vertical"
        )

        h_increments = calculate_shaping_increments(
            blocks,
            h_graph,
            horizontal_slack,
            horizontal_targets,
            axis="horizontal",
        )

        v_increments = calculate_shaping_increments(
            blocks,
            v_graph,
            vertical_slack,
            vertical_targets,
            axis="vertical",
            beta=beta,
        )

        all_increments = (
            list(h_increments.values()) + list(v_increments.values())
        )

        if max(all_increments, default=0.0) < 0.01:
            print("SDS stopped: shaping increments are too small.")
            break

        apply_shaping(blocks, h_increments, v_increments)

    final_result = calculate_layout(
        blocks, hcg_edges, vcg_edges, outline_width
    )

    return blocks, final_result, history
