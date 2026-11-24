
from pathlib import Path
import math

import joblib

from floorplan.packing import calculate_layout, build_constraint_graph
from floorplan.constraints import get_shaping_targets, get_mib_groups
from algorithms.classification import classify_blocks
from algorithms.slack_distribution import (
    calculate_shaping_increments,
    calculate_path_capacity,
)
from algorithms.shaping import apply_shaping
from algorithms.initialization import initialize_blocks_for_sds


# Keep this order synchronized with train_baseline_ml.py.
NUMERIC_FEATURES = [
    "area",
    "width",
    "height",
    "aspect_ratio",
    "min_width",
    "max_width",
    "min_height",
    "max_height",
    "width_room",
    "height_room",
    "horizontal_slack",
    "vertical_slack",
    "normalized_horizontal_slack",
    "normalized_vertical_slack",
    "horizontal_path_capacity",
    "vertical_path_capacity",
    "is_fixed",
    "is_preplaced",
    "is_mib_member",
    "cluster_id",
    "boundary_code",
    "outline_width",
    "initial_layout_width",
    "initial_layout_height",
    "initial_width_feasible",
]

CATEGORICAL_FEATURES = ["subset"]


def _safe_number(value, default=0.0):
    try:
        result = float(value)
        return result if math.isfinite(result) else float(default)
    except (TypeError, ValueError):
        return float(default)


def get_protected_blocks(placement_constraints):
    """Fixed, preplaced and MIB blocks are not independently reshaped."""
    protected = set()

    if placement_constraints is None:
        return protected

    for name, info in placement_constraints.items():
        if info.get("fixed", False) or info.get("preplaced", False):
            protected.add(name)

    for group in get_mib_groups(placement_constraints).values():
        protected.update(group)

    return protected


def filter_targets(targets, blocks, placement_constraints):
    """Keep only blocks eligible for independent shaping."""
    if placement_constraints is None:
        return list(targets)

    allowed = set(
        get_shaping_targets(
            list(blocks.keys()),
            placement_constraints,
        )
    )

    mib_blocks = {
        name
        for group in get_mib_groups(placement_constraints).values()
        for name in group
    }

    return [
        name for name in targets
        if name in allowed and name not in mib_blocks
    ]


def _build_ml_features(
    blocks,
    subsets,
    horizontal_slack,
    vertical_slack,
    horizontal_capacity,
    vertical_capacity,
    outline_width,
    layout_width,
    layout_height,
    placement_constraints,
):
    """
    Build rows in the training feature order.

    Normalized slack is divided by the current block dimension,
    matching the feature extraction used by run_all_samples.py.
    """

    constraints = placement_constraints or {}

    mib_blocks = {
        name
        for group in get_mib_groups(constraints).values()
        for name in group
    }

    subset_by_block = {}
    for subset_name, names in subsets.items():
        for name in names:
            subset_by_block[name] = subset_name

    feature_rows = {}

    for name, block in blocks.items():
        info = constraints.get(name, {})

        h_slack = max(0.0, _safe_number(horizontal_slack.get(name, 0.0)))
        v_slack = max(0.0, _safe_number(vertical_slack.get(name, 0.0)))

        width = float(block.width)
        height = float(block.height)

        width_room = max(
            0.0,
            float(block.effective_max_width) - width,
        )
        height_room = max(
            0.0,
            float(block.effective_max_height) - height,
        )

        row = [
            float(block.area),
            width,
            height,
            height / max(width, 1e-12),
            float(block.effective_min_width),
            float(block.effective_max_width),
            float(block.effective_min_height),
            float(block.effective_max_height),
            width_room,
            height_room,
            h_slack,
            v_slack,
            h_slack / max(width, 1e-12),
            v_slack / max(height, 1e-12),
            max(0.0, _safe_number(horizontal_capacity.get(name, 0.0))),
            max(0.0, _safe_number(vertical_capacity.get(name, 0.0))),
            float(bool(info.get("fixed", False))),
            float(bool(info.get("preplaced", False))),
            float(name in mib_blocks),
            _safe_number(info.get("cluster_id", 0)),
            _safe_number(info.get("boundary_code", 0)),
            float(outline_width),
            float(layout_width),
            float(layout_height),
            float(layout_width <= outline_width + 1e-9),
            subset_by_block.get(name, "UNKNOWN"),
        ]

        feature_rows[name] = row

    return feature_rows


def _predict_horizontal_targets(model, candidate_targets, feature_rows):
    """Predict HORIZONTAL or NONE for eligible Subset IV blocks."""
    if not candidate_targets:
        return [], {}

    rows = [feature_rows[name] for name in candidate_targets]
    predictions = model.predict(rows)

    prediction_map = {
        name: str(prediction)
        for name, prediction in zip(candidate_targets, predictions)
    }

    selected = [
        name
        for name in candidate_targets
        if prediction_map[name].strip().upper() == "HORIZONTAL"
    ]

    return selected, prediction_map


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
    use_ml=False,
    ml_model_path=None,
):
    """
    Improved SDS with optional ML selection for horizontal targets.

    ML model currently supports HORIZONTAL/NONE labels only.
    Vertical shaping remains the SDS Subset VI rule in both modes.

    Returns:
        blocks, final_layout_result, history
    """

    if not 0.0 <= initial_beta <= 1.0:
        raise ValueError("initial_beta must be between 0 and 1.")

    if not 0.0 <= reduced_beta <= 1.0:
        raise ValueError("reduced_beta must be between 0 and 1.")

    if max_iterations < 1:
        raise ValueError("max_iterations must be at least 1.")

    if tolerance <= 0 or not math.isfinite(tolerance):
        raise ValueError("tolerance must be positive and finite.")

    if stagnation_window < 1:
        raise ValueError("stagnation_window must be at least 1.")

    ml_model = None

    if use_ml:
        if ml_model_path is None:
            project_root = Path(__file__).resolve().parents[1]
            ml_model_path = (
                project_root / "FloorSet" / "sds_baseline_model.joblib"
            )

        ml_model_path = Path(ml_model_path)

        if not ml_model_path.exists():
            raise FileNotFoundError(
                f"ML model not found: {ml_model_path}"
            )

        ml_model = joblib.load(ml_model_path)
        print(f"ML model loaded: {ml_model_path}")

    protected_blocks = get_protected_blocks(placement_constraints)

    initialize_blocks_for_sds(
        blocks,
        preserve_blocks=protected_blocks,
    )

    beta = initial_beta
    previous_height = None
    stagnation_count = 0
    beta_adjusted = False
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

        subsets = classify_blocks(
            blocks,
            h_slack,
            v_slack,
            hard_blocks=protected_blocks,
            tolerance=tolerance,
        )

        eligible_h_targets = filter_targets(
            subsets["IV"],
            blocks,
            placement_constraints,
        )

        # Subset VI is the vertical target group in basic SDS.
        vertical_targets = filter_targets(
            subsets["VI"],
            blocks,
            placement_constraints,
        )

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

        h_capacity = calculate_path_capacity(
            h_graph,
            blocks,
            axis="horizontal",
        )
        v_capacity = calculate_path_capacity(
            v_graph,
            blocks,
            axis="vertical",
        )

        prediction_map = {}

        if use_ml:
            feature_rows = _build_ml_features(
                blocks=blocks,
                subsets=subsets,
                horizontal_slack=h_slack,
                vertical_slack=v_slack,
                horizontal_capacity=h_capacity,
                vertical_capacity=v_capacity,
                outline_width=outline_width,
                layout_width=result["width"],
                layout_height=result["height"],
                placement_constraints=placement_constraints,
            )

            horizontal_targets, prediction_map = _predict_horizontal_targets(
                ml_model,
                eligible_h_targets,
                feature_rows,
            )
        else:
            horizontal_targets = eligible_h_targets

        height = result["height"]
        improvement = None

        if previous_height is not None:
            improvement = previous_height - height

            if 0.0 <= improvement < stagnation_threshold:
                stagnation_count += 1
            else:
                stagnation_count = 0

        previous_height = height

        if (
            stagnation_count >= stagnation_window
            and vertical_targets
            and not beta_adjusted
        ):
            beta = reduced_beta
            beta_adjusted = True
            print(
                f"Adaptive beta update at iteration {iteration}: "
                f"beta={beta:.2f}"
            )

        h_inc = calculate_shaping_increments(
            blocks,
            h_graph,
            h_slack,
            horizontal_targets,
            axis="horizontal",
        )

        v_inc = calculate_shaping_increments(
            blocks,
            v_graph,
            v_slack,
            vertical_targets,
            axis="vertical",
            beta=beta,
        )

        total_h = sum(h_inc.values())
        total_v = sum(v_inc.values())

        max_increment = max(
            [0.0] + list(h_inc.values()) + list(v_inc.values())
        )

        iteration_record = {
            "iteration": iteration,
            "width": result["width"],
            "height": height,
            "beta": beta,
            "improvement": improvement,
            "stagnation_count": stagnation_count,
            "horizontal_targets": horizontal_targets.copy(),
            "eligible_horizontal_targets": eligible_h_targets.copy(),
            "vertical_targets": vertical_targets.copy(),
            "ml_predictions": prediction_map.copy(),
            "horizontal_increments": h_inc.copy(),
            "vertical_increments": v_inc.copy(),
            "horizontal_increment": total_h,
            "vertical_increment": total_v,
            "subset_I": len(subsets["I"]),
            "subset_II": len(subsets["II"]),
            "subset_III": len(subsets["III"]),
            "subset_IV": len(subsets["IV"]),
            "subset_V": len(subsets["V"]),
            "subset_VI": len(subsets["VI"]),
            "subset_VII": len(subsets["VII"]),
            "ml_enabled": use_ml,
        }
        history.append(iteration_record)

        print(
            f"Iteration {iteration}: "
            f"Width={result['width']:.4f}, "
            f"Height={height:.4f}, Beta={beta:.2f}"
        )

        print(
            "Subsets: "
            + ", ".join(
                f"{key}={len(value)}"
                for key, value in subsets.items()
            )
        )

        print(
            f"Targets: H={len(horizontal_targets)} "
            f"(eligible={len(eligible_h_targets)}), "
            f"V={len(vertical_targets)} | "
            f"Increments: H={total_h:.8f}, V={total_v:.8f}"
        )

        if use_ml:
            print(
                f"ML selected {len(horizontal_targets)} out of "
                f"{len(eligible_h_targets)} eligible horizontal targets."
            )

        if vertical_targets:
            positive_vertical = {
                name: delta
                for name, delta in v_inc.items()
                if delta > tolerance
            }
            print(
                f"Positive vertical increments: "
                f"{len(positive_vertical)}/{len(vertical_targets)}"
            )

        if not horizontal_targets and not vertical_targets:
            print("No eligible shaping targets. Stopping.")
            break

        # Do not stop merely because an increment is below 0.0001.
        # Continue until the user-configured numerical tolerance is reached.
        if max_increment <= tolerance:
            print(
                f"All shaping increments are <= tolerance "
                f"({tolerance:g}). Stopping."
            )
            break

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
