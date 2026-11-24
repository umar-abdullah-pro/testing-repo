
from floorplan.packing import calculate_layout, build_constraint_graph
from floorplan.constraints import get_shaping_targets, get_mib_groups
from algorithms.classification import classify_blocks
from algorithms.slack_distribution import calculate_shaping_increments
from algorithms.shaping import apply_shaping
from algorithms.initialization import initialize_blocks_for_sds


def get_protected_blocks(placement_constraints):
    """
    Return blocks that must not be reshaped:
    fixed blocks, preplaced blocks, and MIB group members.
    """
    protected = set()

    if placement_constraints is None:
        return protected

    for name, info in placement_constraints.items():
        if info.get("fixed", False) or info.get("preplaced", False):
            protected.add(name)

    mib_groups = get_mib_groups(placement_constraints)

    for group in mib_groups.values():
        protected.update(group)

    return protected


def filter_targets(targets, blocks, placement_constraints):
    """
    Remove blocks that are not eligible for shaping.
    """
    if placement_constraints is None:
        return list(targets)

    allowed = set(
        get_shaping_targets(list(blocks.keys()), placement_constraints)
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


def run_improved_sds(
    blocks,
    hcg_edges,
    vcg_edges,
    outline_width,
    max_iterations=200,
    initial_beta=1.0,
    reduced_beta=0.7,
    tolerance=1e-6,
    stagnation_threshold=0.05,
    stagnation_window=3,
    placement_constraints=None,
):
    """
    Improved Slack-Driven Shaping algorithm.

    Horizontal shaping uses Subset IV.
    Vertical shaping uses Subset VI.

    Beta scales vertical shaping increments.
    """

    if not 0.0 <= initial_beta <= 1.0:
        raise ValueError("initial_beta must be between 0 and 1.")

    if not 0.0 <= reduced_beta <= 1.0:
        raise ValueError("reduced_beta must be between 0 and 1.")

    if max_iterations < 1:
        raise ValueError("max_iterations must be at least 1.")

    if stagnation_window < 1:
        raise ValueError("stagnation_window must be at least 1.")

    protected_blocks = get_protected_blocks(placement_constraints)

    initialize_blocks_for_sds(
        blocks,
        preserve_blocks=protected_blocks,
    )

    beta = initial_beta
    previous_height = None
    stagnation_count = 0
    beta_adjusted = False
    beta_update_pending = False

    history = []

    for iteration in range(1, max_iterations + 1):

        result = calculate_layout(
            blocks,
            hcg_edges,
            vcg_edges,
            outline_width,
        )

        h_slack = result["horizontal_slack"]
        v_slack = result["vertical_slack"]
        height = result["height"]

        # Classify blocks according to SDS subset rules.
        subsets = classify_blocks(
            blocks,
            h_slack,
            v_slack,
            hard_blocks=protected_blocks,
            tolerance=tolerance,
        )

        # Select eligible shaping targets.
        h_targets = filter_targets(
            subsets["IV"],
            blocks,
            placement_constraints,
        )

        v_targets = filter_targets(
            subsets["VI"],
            blocks,
            placement_constraints,
        )

        # Calculate height improvement and stagnation.
        improvement = None

        if previous_height is not None:
            improvement = previous_height - height

            if 0.0 <= improvement < stagnation_threshold:
                stagnation_count += 1
            else:
                stagnation_count = 0

            if (
                stagnation_count >= stagnation_window
                and not beta_adjusted
            ):
                beta_update_pending = True

        previous_height = height

        # Apply adaptive beta only when vertical targets exist.
        if (
            beta_update_pending
            and v_targets
            and not beta_adjusted
        ):
            beta = reduced_beta
            beta_adjusted = True
            beta_update_pending = False

            print(
                f"Adaptive beta update at iteration {iteration}: "
                f"beta = {beta:.2f}"
            )

        # Build constraint graphs.
        h_graph = build_constraint_graph(
            blocks,
            hcg_edges,
            "horizontal",
        )

        v_graph = build_constraint_graph(
            blocks,
            vcg_edges,
            "vertical",
        )

        # Calculate horizontal shaping increments.
        h_inc = calculate_shaping_increments(
            blocks,
            h_graph,
            h_slack,
            h_targets,
            axis="horizontal",
        )

        # Calculate vertical shaping increments.
        v_inc = calculate_shaping_increments(
            blocks,
            v_graph,
            v_slack,
            v_targets,
            axis="vertical",
            beta=beta,
        )

        total_h = sum(h_inc.values())
        total_v = sum(v_inc.values())

        max_increment = max(
            [0.0] + list(h_inc.values()) + list(v_inc.values())
        )

        # Record iteration information.
        history.append(
            {
                "iteration": iteration,
                "width": result["width"],
                "height": height,
                "beta": beta,
                "improvement": improvement,
                "stagnation_count": stagnation_count,
                "beta_update_pending": beta_update_pending,
                "horizontal_targets": h_targets.copy(),
                "vertical_targets": v_targets.copy(),
                "horizontal_increment": total_h,
                "vertical_increment": total_v,
                "subset_I": len(subsets["I"]),
                "subset_II": len(subsets["II"]),
                "subset_III": len(subsets["III"]),
                "subset_IV": len(subsets["IV"]),
                "subset_V": len(subsets["V"]),
                "subset_VI": len(subsets["VI"]),
                "subset_VII": len(subsets["VII"]),
            }
        )

        print(
            f"Iteration {iteration}: "
            f"Width={result['width']:.4f}, "
            f"Height={height:.4f}, "
            f"Beta={beta:.2f}"
        )

        print(
            f"Subsets: "
            f"I={len(subsets['I'])}, "
            f"II={len(subsets['II'])}, "
            f"III={len(subsets['III'])}, "
            f"IV={len(subsets['IV'])}, "
            f"V={len(subsets['V'])}, "
            f"VI={len(subsets['VI'])}, "
            f"VII={len(subsets['VII'])}"
        )

        print(
            f"Targets: H={len(h_targets)}, V={len(v_targets)} | "
            f"Increments: H={total_h:.6f}, V={total_v:.6f}"
        )

        # Stop if no eligible targets exist.
        if not h_targets and not v_targets:
            print("No eligible shaping targets. Stopping.")
            break

        # Stop if shaping increments are negligible.
        if max_increment < 0.01:
            print("Shaping increments are too small. Stopping.")
            break

        # Apply calculated shaping increments.
        apply_shaping(
            blocks,
            h_inc,
            v_inc,
        )

    final_result = calculate_layout(
        blocks,
        hcg_edges,
        vcg_edges,
        outline_width,
    )

    return blocks, final_result, history
