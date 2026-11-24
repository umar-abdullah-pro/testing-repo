from pathlib import Path

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

# Must match the feature order used during model training.
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
    """Convert constraint metadata to a numeric value safely."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


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
    """Remove blocks that are not eligible for shaping."""
    if placement_constraints is None:
        return list(targets)

    allowed = set(
        get_shaping_targets(
            list(blocks.keys()),
            placement_constraints,
        )
    )

    mib_groups = get_mib_groups(placement_constraints)

    mib_blocks = {name for group in mib_groups.values() for name in group}

    return [name for name in targets if name in allowed and name not in mib_blocks]


def _get_constraint_info(name, placement_constraints):
    if placement_constraints is None:
        return {}

    return placement_constraints.get(name, {})


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
    Build feature rows in exactly the same order as training.
    Returns a dictionary: block_name -> feature row.
    """

    mib_groups = get_mib_groups(placement_constraints or {})

    mib_blocks = {name for group in mib_groups.values() for name in group}

    subset_by_block = {}

    for subset_name, names in subsets.items():
        for name in names:
            subset_by_block[name] = subset_name

    feature_rows = {}

    for name, block in blocks.items():

        info = _get_constraint_info(
            name,
            placement_constraints,
        )

        h_slack = max(
            0.0,
            float(horizontal_slack.get(name, 0.0)),
        )

        v_slack = max(
            0.0,
            float(vertical_slack.get(name, 0.0)),
        )

        width_room = max(
            0.0,
            float(block.effective_max_width) - float(block.width),
        )

        height_room = max(
            0.0,
            float(block.effective_max_height) - float(block.height),
        )

        h_capacity = max(
            0.0,
            float(horizontal_capacity.get(name, 0.0)),
        )

        v_capacity = max(
            0.0,
            float(vertical_capacity.get(name, 0.0)),
        )

        row = [
            float(block.area),
            float(block.width),
            float(block.height),
            float(block.height) / max(float(block.width), 1e-12),
            float(block.min_width),
            float(block.max_width),
            float(block.min_height),
            float(block.max_height),
            width_room,
            height_room,
            h_slack,
            v_slack,
            h_slack / max(width_room, 1e-12),
            v_slack / max(height_room, 1e-12),
            h_capacity,
            v_capacity,
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


def _predict_horizontal_targets(
    model,
    candidate_targets,
    feature_rows,
):
    """
    Predict HORIZONTAL or NONE for eligible Subset IV blocks.
    Only HORIZONTAL predictions are returned as shaping targets.
    """

    if not candidate_targets:
        return [], {}

    X = [feature_rows[name] for name in candidate_targets]

    predictions = model.predict(X)

    prediction_map = {
        name: str(prediction)
        for name, prediction in zip(candidate_targets, predictions)
    }

    selected = [
        name for name in candidate_targets if prediction_map[name] == "HORIZONTAL"
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
    Improved Slack-Driven Shaping algorithm.

    Rule-based mode:
        Horizontal shaping uses eligible Subset IV blocks.

    ML-assisted mode:
        Random Forest predicts HORIZONTAL or NONE for eligible
        Subset IV blocks.

    Vertical shaping:
        Uses the original Subset VI SDS rule in both modes.

    The function returns:
        blocks, final_layout_result, history
    """

    if not 0.0 <= initial_beta <= 1.0:
        raise ValueError("initial_beta must be between 0 and 1.")

    if not 0.0 <= reduced_beta <= 1.0:
        raise ValueError("reduced_beta must be between 0 and 1.")

    if max_iterations < 1:
        raise ValueError("max_iterations must be at least 1.")

    if stagnation_window < 1:
        raise ValueError("stagnation_window must be at least 1.")

    # Load model only when ML mode is requested.
    ml_model = None

    if use_ml:

        if ml_model_path is None:
            project_root = Path(__file__).resolve().parents[1]

            ml_model_path = project_root / "FloorSet" / "sds_baseline_model.joblib"

        ml_model_path = Path(ml_model_path)

        if not ml_model_path.exists():
            raise FileNotFoundError(f"ML model not found: {ml_model_path}")

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

        # First select only eligible rule-based targets.
        eligible_h_targets = filter_targets(
            subsets["IV"],
            blocks,
            placement_constraints,
        )

        v_targets = filter_targets(
            subsets["VI"],
            blocks,
            placement_constraints,
        )

        # Build graphs for path-capacity calculations.
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

        # Calculate path capacities.
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

        # Select horizontal targets using ML or original rules.
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

            h_targets, prediction_map = _predict_horizontal_targets(
                ml_model,
                eligible_h_targets,
                feature_rows,
            )

        else:
            h_targets = eligible_h_targets

        # Calculate height improvement and stagnation.
        improvement = None

        if previous_height is not None:

            improvement = previous_height - height

            if 0.0 <= improvement < stagnation_threshold:
                stagnation_count += 1
            else:
                stagnation_count = 0

            if stagnation_count >= stagnation_window and not beta_adjusted:
                beta_update_pending = True

        previous_height = height

        # Apply adaptive beta only when vertical targets exist.
        if beta_update_pending and v_targets and not beta_adjusted:
            beta = reduced_beta
            beta_adjusted = True
            beta_update_pending = False

            print(
                f"Adaptive beta update at iteration {iteration}: " f"beta = {beta:.2f}"
            )

        # Calculate horizontal shaping increments.
        h_inc = calculate_shaping_increments(
            blocks,
            h_graph,
            h_slack,
            h_targets,
            axis="horizontal",
        )

        # Vertical shaping remains rule-based.
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

        max_increment = max([0.0] + list(h_inc.values()) + list(v_inc.values()))

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
                "eligible_horizontal_targets": eligible_h_targets.copy(),
                "vertical_targets": v_targets.copy(),
                "ml_predictions": prediction_map.copy(),
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
            f"Targets: "
            f"H={len(h_targets)} "
            f"(eligible={len(eligible_h_targets)}), "
            f"V={len(v_targets)} | "
            f"Increments: H={total_h:.6f}, V={total_v:.6f}"
        )

        if use_ml:
            print(
                f"ML selected {len(h_targets)} out of "
                f"{len(eligible_h_targets)} eligible horizontal targets."
            )

        # Stop if no eligible targets exist.
        if not h_targets and not v_targets:
            print("No eligible shaping targets. Stopping.")
            break

        # Stop if shaping increments are negligible.
        if max_increment < 0.0001:
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
