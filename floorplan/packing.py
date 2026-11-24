
import math

from graph.dag import DAG

SOURCE = "SOURCE"
SINK = "SINK"

EPSILON = 1e-9


def build_constraint_graph(blocks, constraints, axis):
    """
    Build a weighted constraint graph.

    Horizontal graph: node weight = block width.
    Vertical graph: node weight = block height.

    SOURCE and SINK are added automatically.
    """

    if axis not in ("horizontal", "vertical"):
        raise ValueError("Axis must be horizontal or vertical.")

    if not blocks:
        raise ValueError("At least one block is required.")

    graph = DAG()

    graph.add_node(SOURCE, 0.0)
    graph.add_node(SINK, 0.0)

    for name, block in blocks.items():

        if axis == "horizontal":
            weight = float(block.width)
        else:
            weight = float(block.height)

        if not math.isfinite(weight) or weight <= 0:
            raise ValueError(
                f"Invalid {axis} dimension for block {name}: {weight}"
            )

        graph.add_node(name, weight)

    incoming = {name: 0 for name in blocks}
    outgoing = {name: 0 for name in blocks}

    seen_edges = set()

    for u, v in constraints:

        if u not in blocks or v not in blocks:
            raise ValueError(
                f"Unknown block in constraint: {u} -> {v}"
            )

        if u == v:
            raise ValueError("A block cannot precede itself.")

        if (u, v) in seen_edges:
            continue

        seen_edges.add((u, v))

        graph.add_edge(u, v)

        incoming[v] += 1
        outgoing[u] += 1

    # Connect all source blocks and sink blocks.
    for name in blocks:

        if incoming[name] == 0:
            graph.add_edge(SOURCE, name)

        if outgoing[name] == 0:
            graph.add_edge(name, SINK)

    # This also detects cycles in the constraint graph.
    graph.topological_sort()

    return graph


def calculate_coordinates(graph):
    """
    Calculate earliest possible coordinates.

    For every edge u -> v:

        coordinate[v] >= coordinate[u] + weight[u]
    """

    coordinates = {
        node: float("-inf")
        for node in graph.weights
    }

    coordinates[SOURCE] = 0.0

    order = graph.topological_sort()

    for u in order:

        if not math.isfinite(coordinates[u]):
            raise ValueError(
                f"Node {u} is not reachable from SOURCE."
            )

        for v in graph.adj[u]:

            candidate = (
                coordinates[u] + graph.weights[u]
            )

            coordinates[v] = max(
                coordinates[v],
                candidate
            )

    if not math.isfinite(coordinates[SINK]):
        raise ValueError("SINK is not reachable from SOURCE.")

    return coordinates


def calculate_latest_coordinates(graph, boundary):
    """
    Calculate latest feasible coordinates from the right/top boundary.

    Horizontal boundary = outline width.
    Vertical boundary = layout height.

    For every edge u -> v:

        latest[u] <= latest[v] - weight[u]
    """

    boundary = float(boundary)

    if not math.isfinite(boundary) or boundary < 0:
        raise ValueError("Boundary must be finite and non-negative.")

    order = graph.topological_sort()

    latest = {
        node: float("inf")
        for node in graph.weights
    }

    latest[SINK] = boundary

    for u in reversed(order):

        if u == SINK:
            continue

        if graph.adj[u]:

            latest[u] = min(
                latest[v] - graph.weights[u]
                for v in graph.adj[u]
            )

    for node, coordinate in latest.items():

        if not math.isfinite(coordinate):
            raise ValueError(
                f"Latest coordinate could not be calculated for {node}."
            )

    return latest


def calculate_layout(
    blocks,
    horizontal_constraints,
    vertical_constraints,
    outline_width
):
    """
    Calculate:

    - Earliest block positions (LL and BL)
    - Latest block positions (RL and TL)
    - Horizontal and vertical slack
    - Raw slack (including negative values)
    - Layout dimensions
    - Critical paths
    - Fixed-outline feasibility

    Note:
    This function calculates relative packing coordinates.
    It does not enforce absolute preplaced coordinates.
    """

    if not blocks:
        raise ValueError("At least one block is required.")

    outline_width = float(outline_width)

    if not math.isfinite(outline_width) or outline_width <= 0:
        raise ValueError("Outline width must be positive and finite.")

    # --------------------------------------------------
    # 1. Build constraint graphs
    # --------------------------------------------------

    h_graph = build_constraint_graph(
        blocks,
        horizontal_constraints,
        "horizontal"
    )

    v_graph = build_constraint_graph(
        blocks,
        vertical_constraints,
        "vertical"
    )

    # --------------------------------------------------
    # 2. Calculate earliest coordinates
    # --------------------------------------------------

    x_coordinates = calculate_coordinates(h_graph)
    y_coordinates = calculate_coordinates(v_graph)

    # --------------------------------------------------
    # 3. Calculate layout dimensions
    # --------------------------------------------------

    layout_width = x_coordinates[SINK]
    layout_height = y_coordinates[SINK]

    # --------------------------------------------------
    # 4. Calculate latest coordinates
    # --------------------------------------------------

    rl_coordinates = calculate_latest_coordinates(
        h_graph,
        outline_width
    )

    tl_coordinates = calculate_latest_coordinates(
        v_graph,
        layout_height
    )

    # --------------------------------------------------
    # 5. Calculate horizontal slack
    # --------------------------------------------------

    horizontal_slack = {}
    horizontal_slack_raw = {}

    for name in blocks:

        raw_slack = (
            rl_coordinates[name] - x_coordinates[name]
        )

        horizontal_slack_raw[name] = raw_slack

        # Preserve compatibility with existing SDS code.
        horizontal_slack[name] = max(0.0, raw_slack)

    # --------------------------------------------------
    # 6. Calculate vertical slack
    # --------------------------------------------------

    vertical_slack = {}
    vertical_slack_raw = {}

    for name in blocks:

        raw_slack = (
            tl_coordinates[name] - y_coordinates[name]
        )

        vertical_slack_raw[name] = raw_slack

        # Preserve compatibility with existing SDS code.
        vertical_slack[name] = max(0.0, raw_slack)

    # --------------------------------------------------
    # 7. Find critical paths
    # --------------------------------------------------

    hcp_weight, hcp_path = h_graph.longest_path(SOURCE)

    vcp_weight, vcp_path = v_graph.longest_path(SOURCE)

    # --------------------------------------------------
    # 8. Collect block placements
    # --------------------------------------------------

    placements = {}

    for name, block in blocks.items():

        placements[name] = {
            "x": x_coordinates[name],
            "y": y_coordinates[name],
            "width": block.width,
            "height": block.height,
        }

    # --------------------------------------------------
    # 9. Check feasibility
    # --------------------------------------------------

    feasible = (
        layout_width <= outline_width + EPSILON
    )

    # --------------------------------------------------
    # 10. Return results
    # --------------------------------------------------

    return {
        "width": layout_width,
        "height": layout_height,
        "outline_width": outline_width,
        "feasible": feasible,

        "placements": placements,

        "horizontal_critical_path": hcp_path,
        "vertical_critical_path": vcp_path,

        "horizontal_path_weight": hcp_weight,
        "vertical_path_weight": vcp_weight,

        "horizontal_slack": horizontal_slack,
        "vertical_slack": vertical_slack,

        "horizontal_slack_raw": horizontal_slack_raw,
        "vertical_slack_raw": vertical_slack_raw,

        "LL": x_coordinates,
        "RL": rl_coordinates,
        "BL": y_coordinates,
        "TL": tl_coordinates,
    }
