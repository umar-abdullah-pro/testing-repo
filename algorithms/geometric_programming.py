"""
Geometric Programming step for the SDS algorithm.

Based on:
Yan and Chu, "Optimal Slack-Driven Block Shaping Algorithm
in Fixed-Outline Floorplanning", ISPD 2012, Section 5.

Only soft blocks that are intersection blocks (belonging to
both a horizontal and a vertical critical path) are allowed
to change shape.

All other block dimensions remain fixed.

Optimization:
    Minimize layout height

Subject to:
    - Layout width <= outline width
    - HCG non-overlap constraints
    - VCG non-overlap constraints
    - Block dimension bounds
    - Area preservation

Uses CVXPY Disciplined Geometric Programming (DGP).

Note:
This implementation solves the reduced GP subproblem. It is
not a literal implementation of the paper's one-iteration
deepest-descent GP step.
"""

import math

EPSILON = 1e-6
AREA_TOLERANCE = 1e-4


# ============================================================
# 1. BASIC VALIDATION
# ============================================================


def _validate_positive(value, label):
    """Convert a value to a positive finite float."""

    try:
        value = float(value)
    except (TypeError, ValueError):
        raise ValueError(f"{label} must be numeric.")

    if not math.isfinite(value) or value <= 0:
        raise ValueError(f"{label} must be positive and finite. Got {value}")

    return value


def _get_effective_bounds(block):
    """Return feasible width and height bounds of a block."""

    min_width = _validate_positive(block.effective_min_width, "Minimum width")

    max_width = _validate_positive(block.effective_max_width, "Maximum width")

    min_height = _validate_positive(block.effective_min_height, "Minimum height")

    max_height = _validate_positive(block.effective_max_height, "Maximum height")

    if min_width > max_width + EPSILON:
        raise ValueError(f"Infeasible width bounds for block {block.name}.")

    if min_height > max_height + EPSILON:
        raise ValueError(f"Infeasible height bounds for block {block.name}.")

    return min_width, max_width, min_height, max_height


def _validate_graph(graph, blocks, graph_name):
    """Validate the graph structure against the block dictionary."""

    if not hasattr(graph, "weights") or not hasattr(graph, "adj"):
        raise TypeError(f"{graph_name} must be a weighted DAG.")

    if "SOURCE" not in graph.weights:
        raise ValueError(f"{graph_name} does not contain SOURCE.")

    if "SINK" not in graph.weights:
        raise ValueError(f"{graph_name} does not contain SINK.")

    for name in blocks:
        if name not in graph.weights:
            raise ValueError(f"Block {name} is missing from {graph_name}.")

    # This also detects cycles.
    graph.topological_sort()


# ============================================================
# 2. LONGEST PATH CALCULATION
# ============================================================


def _longest_path_value(graph, node_weights):
    """
    Calculate the longest SOURCE-to-SINK path using supplied
    node weights.

    The repository DAG uses node weights, not edge weights.

    Parameters
    ----------
    graph:
        DAG containing SOURCE, SINK and block nodes.

    node_weights:
        Dictionary mapping every graph node to its weight.

    Returns
    -------
    float:
        Longest SOURCE-to-SINK path weight.
    """

    order = graph.topological_sort()

    distance = {node: float("-inf") for node in graph.weights}

    distance["SOURCE"] = 0.0

    for u in order:

        if distance[u] == float("-inf"):
            continue

        for v in graph.adj[u]:

            candidate = distance[u] + node_weights[u]

            if candidate > distance[v]:
                distance[v] = candidate

    result = distance["SINK"]

    if not math.isfinite(result):
        raise ValueError("SINK is not reachable from SOURCE.")

    return float(result)


def _current_node_weights(blocks, graph):
    """Build current node weights for a horizontal or vertical graph."""

    weights = {}

    for node in graph.weights:

        if node in ("SOURCE", "SINK"):
            weights[node] = 0.0

        elif node in blocks:
            # The caller selects the appropriate dimension later.
            weights[node] = None

        else:
            raise ValueError(f"Unexpected graph node: {node}")

    return weights


def _calculate_current_dimensions(blocks, horizontal_graph, vertical_graph):
    """Calculate current layout width and height."""

    horizontal_weights = _current_node_weights(blocks, horizontal_graph)

    vertical_weights = _current_node_weights(blocks, vertical_graph)

    for name, block in blocks.items():
        horizontal_weights[name] = float(block.width)
        vertical_weights[name] = float(block.height)

    old_width = _longest_path_value(horizontal_graph, horizontal_weights)

    old_height = _longest_path_value(vertical_graph, vertical_weights)

    return old_width, old_height


# ============================================================
# 3. MAIN GEOMETRIC PROGRAMMING FUNCTION
# ============================================================


def optimize_intersection_blocks(
    blocks,
    horizontal_graph,
    vertical_graph,
    outline_width,
    intersection_blocks,
    hard_blocks=None,
    solver=None,
    verbose=False,
):
    """
    Optimize soft intersection blocks using CVXPY DGP.

    Parameters
    ----------
    blocks:
        Dictionary {block_name: Block}.

    horizontal_graph:
        Weighted horizontal constraint graph (HCG).

    vertical_graph:
        Weighted vertical constraint graph (VCG).

    outline_width:
        Fixed upper bound on layout width.

    intersection_blocks:
        Blocks lying on at least one HCP and one VCP.

    hard_blocks:
        Blocks that must never be reshaped.

    solver:
        Optional CVXPY solver, e.g. "CLARABEL".

    verbose:
        Whether to print solver output.

    Returns
    -------
    Dictionary containing:
        status
        improved
        old_width
        old_height
        optimized_width
        optimized_height
        optimized_dimensions
        optimized_layout_height
        objective_value

    This function does not mutate the original blocks.
    """

    # --------------------------------------------------------
    # A. Import CVXPY only when optimization is requested
    # --------------------------------------------------------

    try:
        import cvxpy as cp
    except ImportError as exc:
        raise ImportError(
            "CVXPY is required for geometric programming. "
            "Install it using: python -m pip install cvxpy"
        ) from exc

    # --------------------------------------------------------
    # B. Validate inputs
    # --------------------------------------------------------

    if not isinstance(blocks, dict) or not blocks:
        raise ValueError("blocks must be a non-empty dictionary.")

    outline_width = _validate_positive(outline_width, "Outline width")

    hard_blocks = set(hard_blocks or [])
    intersection_blocks = set(intersection_blocks or [])

    unknown_intersections = intersection_blocks - set(blocks)

    if unknown_intersections:
        raise ValueError(
            "Unknown intersection blocks: " f"{sorted(unknown_intersections)}"
        )

    unknown_hard = hard_blocks - set(blocks)

    if unknown_hard:
        raise ValueError(f"Unknown hard blocks: {sorted(unknown_hard)}")

    # Only soft intersection blocks are variables.
    variable_blocks = intersection_blocks - hard_blocks

    _validate_graph(horizontal_graph, blocks, "Horizontal graph")

    _validate_graph(vertical_graph, blocks, "Vertical graph")

    # --------------------------------------------------------
    # C. Calculate current layout dimensions
    # --------------------------------------------------------

    old_width, old_height = _calculate_current_dimensions(
        blocks, horizontal_graph, vertical_graph
    )

    if old_width > outline_width + EPSILON:
        raise ValueError(
            "Input layout is already wider than the outline. "
            f"Current width={old_width:.8f}, "
            f"outline width={outline_width:.8f}."
        )

    # Validate all block dimensions before building the GP.
    for name, block in blocks.items():

        _validate_positive(block.width, f"Width of {name}")

        _validate_positive(block.height, f"Height of {name}")

        _validate_positive(block.area, f"Area of {name}")

        _get_effective_bounds(block)

    # --------------------------------------------------------
    # D. Handle the no-variable case
    # --------------------------------------------------------

    if not variable_blocks:
        return {
            "status": "NO_VARIABLE_BLOCKS",
            "improved": False,
            "old_width": old_width,
            "old_height": old_height,
            "optimized_width": old_width,
            "optimized_height": old_height,
            "optimized_dimensions": {},
            "optimized_layout_height": old_height,
            "objective_value": old_height,
        }

    # --------------------------------------------------------
    # E. Create GP variables
    # --------------------------------------------------------

    widths = {}
    heights = {}

    for name, block in blocks.items():

        if name in variable_blocks:

            widths[name] = cp.Variable(pos=True, name=f"width_{name}")

            heights[name] = cp.Variable(pos=True, name=f"height_{name}")

        else:
            # Non-intersection and hard blocks remain unchanged.
            widths[name] = float(block.width)
            heights[name] = float(block.height)

    # Coordinates are positive GP variables.
    x = {name: cp.Variable(pos=True, name=f"x_{name}") for name in blocks}

    y = {name: cp.Variable(pos=True, name=f"y_{name}") for name in blocks}

    layout_height = cp.Variable(pos=True, name="layout_height")

    constraints = []

    # --------------------------------------------------------
    # F. Area and dimension constraints
    # --------------------------------------------------------

    for name in variable_blocks:

        block = blocks[name]

        area = _validate_positive(block.area, f"Area of {name}")

        min_w, max_w, min_h, max_h = _get_effective_bounds(block)

        constraints.extend(
            [
                widths[name] >= min_w,
                widths[name] <= max_w,
                heights[name] >= min_h,
                heights[name] <= max_h,
                # Preserve block area.
                widths[name] * heights[name] == area,
            ]
        )

    # --------------------------------------------------------
    # G. Horizontal graph constraints
    # --------------------------------------------------------

    for u in horizontal_graph.weights:

        for v in horizontal_graph.adj[u]:

            if u == "SOURCE":
                # SOURCE coordinate is zero.
                # x[v] is already constrained positive.
                continue

            elif v == "SINK":
                # The right edge of every sink predecessor
                # must remain inside the fixed outline.
                constraints.append(x[u] + widths[u] <= outline_width)

            else:
                # Horizontal non-overlap:
                # x[u] + width[u] <= x[v]
                constraints.append(x[u] + widths[u] <= x[v])

    # --------------------------------------------------------
    # H. Vertical graph constraints
    # --------------------------------------------------------

    for u in vertical_graph.weights:

        for v in vertical_graph.adj[u]:

            if u == "SOURCE":
                # SOURCE coordinate is zero.
                # y[v] is already constrained positive.
                continue

            elif v == "SINK":
                # The top edge must remain below layout height.
                constraints.append(y[u] + heights[u] <= layout_height)

            else:
                # Vertical non-overlap:
                # y[u] + height[u] <= y[v]
                constraints.append(y[u] + heights[u] <= y[v])

    # --------------------------------------------------------
    # I. Build and validate the GP problem
    # --------------------------------------------------------

    problem = cp.Problem(cp.Minimize(layout_height), constraints)

    if not problem.is_dgp():
        raise ValueError(
            "The generated optimization problem is not "
            "Disciplined Geometric Programming compliant. "
            "Check dimensions, bounds and graph constraints."
        )

    # --------------------------------------------------------
    # J. Solve
    # --------------------------------------------------------

    solve_options = {
        "gp": True,
        "verbose": bool(verbose),
    }

    if solver is not None:
        solve_options["solver"] = solver

    try:
        problem.solve(**solve_options)

    except cp.error.SolverError as exc:
        raise RuntimeError(
            "CVXPY could not solve the geometric program. "
            "Check installed solvers using "
            "cp.installed_solvers()."
        ) from exc

    if problem.status not in (
        cp.OPTIMAL,
        cp.OPTIMAL_INACCURATE,
    ):
        return {
            "status": problem.status,
            "improved": False,
            "old_width": old_width,
            "old_height": old_height,
            "optimized_width": old_width,
            "optimized_height": old_height,
            "optimized_dimensions": {},
            "optimized_layout_height": old_height,
            "objective_value": None,
        }

    # --------------------------------------------------------
    # K. Extract and validate optimized dimensions
    # --------------------------------------------------------

    optimized_dimensions = {}

    for name in variable_blocks:

        if widths[name].value is None or heights[name].value is None:
            raise RuntimeError(f"Solver did not return dimensions for {name}.")

        new_width = float(widths[name].value)
        new_height = float(heights[name].value)

        if (
            not math.isfinite(new_width)
            or not math.isfinite(new_height)
            or new_width <= 0
            or new_height <= 0
        ):
            raise RuntimeError(f"Invalid optimized dimensions for {name}.")

        block = blocks[name]

        min_w, max_w, min_h, max_h = _get_effective_bounds(block)

        if not (min_w - EPSILON <= new_width <= max_w + EPSILON):
            raise RuntimeError(f"Optimized width violates bounds for {name}.")

        if not (min_h - EPSILON <= new_height <= max_h + EPSILON):
            raise RuntimeError(f"Optimized height violates bounds for {name}.")

        area_error = abs(new_width * new_height - block.area)

        if area_error > (AREA_TOLERANCE * max(1.0, block.area)):
            raise RuntimeError(
                f"Area preservation failed for {name}. " f"Error={area_error}"
            )

        optimized_dimensions[name] = {
            "width": new_width,
            "height": new_height,
        }

    # --------------------------------------------------------
    # L. Calculate actual optimized layout dimensions
    # --------------------------------------------------------

    optimized_h_weights = {node: 0.0 for node in horizontal_graph.weights}

    optimized_v_weights = {node: 0.0 for node in vertical_graph.weights}

    for name, block in blocks.items():

        if name in optimized_dimensions:
            optimized_h_weights[name] = optimized_dimensions[name]["width"]

            optimized_v_weights[name] = optimized_dimensions[name]["height"]

        else:
            optimized_h_weights[name] = float(block.width)
            optimized_v_weights[name] = float(block.height)

    optimized_width = _longest_path_value(horizontal_graph, optimized_h_weights)

    optimized_height = _longest_path_value(vertical_graph, optimized_v_weights)

    # The GP objective and graph-derived height should agree.
    solver_height = float(layout_height.value)

    if abs(optimized_height - solver_height) > 1e-3 * max(1.0, optimized_height):
        raise RuntimeError(
            "Solver objective and graph-derived layout height "
            "do not agree. "
            f"Solver={solver_height}, "
            f"Graph={optimized_height}."
        )

    if optimized_width > outline_width + 1e-4:
        raise RuntimeError(
            "Optimized layout violates the fixed outline. "
            f"Width={optimized_width}, "
            f"Outline={outline_width}."
        )

    # --------------------------------------------------------
    # M. Return result without mutating original blocks
    # --------------------------------------------------------

    return {
        "status": problem.status,
        "improved": (optimized_height < old_height - EPSILON),
        "old_width": old_width,
        "old_height": old_height,
        "optimized_width": optimized_width,
        "optimized_height": optimized_height,
        "optimized_dimensions": optimized_dimensions,
        "optimized_layout_height": optimized_height,
        "objective_value": float(problem.value),
    }


# ============================================================
# 4. COMPATIBILITY FUNCTION
# ============================================================


def solve_geometric_program(
    blocks,
    horizontal_graph,
    vertical_graph,
    outline_width,
    intersection_blocks,
    hard_blocks=None,
    solver=None,
    verbose=False,
):
    """
    Compatibility wrapper.

    Both names can now be used:
        optimize_intersection_blocks(...)
        solve_geometric_program(...)
    """

    return optimize_intersection_blocks(
        blocks=blocks,
        horizontal_graph=horizontal_graph,
        vertical_graph=vertical_graph,
        outline_width=outline_width,
        intersection_blocks=intersection_blocks,
        hard_blocks=hard_blocks,
        solver=solver,
        verbose=verbose,
    )


# ============================================================
# 5. APPLY GP DIMENSIONS
# ============================================================


def apply_gp_dimensions(blocks, gp_result):
    """
    Apply validated GP dimensions to original Block objects.

    All dimensions are validated before any block is modified.
    This avoids partial updates if one dimension is invalid.
    """

    if gp_result is None:
        raise ValueError("GP result cannot be None.")

    status = gp_result.get("status")

    if status not in (
        "optimal",
        "optimal_inaccurate",
        "OPTIMAL",
        "OPTIMAL_INACCURATE",
    ):
        raise ValueError(
            "Cannot apply dimensions from an unsuccessful " f"GP solve. Status={status}"
        )

    dimensions = gp_result.get("optimized_dimensions", {})

    # --------------------------------------------------------
    # First pass: validate every proposed update
    # --------------------------------------------------------

    validated_updates = {}

    for name, values in dimensions.items():

        if name not in blocks:
            raise KeyError(f"Unknown block in GP result: {name}")

        if "width" not in values or "height" not in values:
            raise ValueError(f"Missing width or height for block {name}.")

        new_width = _validate_positive(values["width"], f"Optimized width of {name}")

        expected_height = _validate_positive(
            values["height"], f"Optimized height of {name}"
        )

        block = blocks[name]

        min_w, max_w, min_h, max_h = _get_effective_bounds(block)

        if not (min_w - EPSILON <= new_width <= max_w + EPSILON):
            raise ValueError(f"Width violates bounds for {name}.")

        actual_height = block.area / new_width

        if not (min_h - EPSILON <= actual_height <= max_h + EPSILON):
            raise ValueError(f"Height violates bounds for {name}.")

        if abs(actual_height - expected_height) > (
            AREA_TOLERANCE * max(1.0, expected_height)
        ):
            raise ValueError(f"Area/height validation failed for {name}.")

        validated_updates[name] = new_width

    # --------------------------------------------------------
    # Second pass: apply all validated widths
    # --------------------------------------------------------

    for name, new_width in validated_updates.items():
        blocks[name].set_width(new_width)

    return blocks
