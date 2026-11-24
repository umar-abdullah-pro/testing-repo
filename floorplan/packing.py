from graph.dag import DAG

SOURCE = "SOURCE"
SINK = "SINK"


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

    graph.add_node(SOURCE, 0)
    graph.add_node(SINK, 0)

    for name, block in blocks.items():

        if axis == "horizontal":
            weight = block.width
        else:
            weight = block.height

        graph.add_node(name, weight)

    incoming = {name: 0 for name in blocks}
    outgoing = {name: 0 for name in blocks}

    for u, v in constraints:

        if u not in blocks or v not in blocks:
            raise ValueError(f"Unknown block in constraint: {u} -> {v}")

        if u == v:
            raise ValueError("A block cannot precede itself.")

        graph.add_edge(u, v)

        incoming[v] += 1
        outgoing[u] += 1

    for name in blocks:

        if incoming[name] == 0:
            graph.add_edge(SOURCE, name)

        if outgoing[name] == 0:
            graph.add_edge(name, SINK)

    graph.topological_sort()

    return graph


def calculate_coordinates(graph):
    """
    Calculate earliest possible coordinates.

    For every edge u -> v:

        coordinate[v] >= coordinate[u] + weight[u]
    """

    coordinates = {node: float("-inf") for node in graph.weights}

    coordinates[SOURCE] = 0.0

    order = graph.topological_sort()

    for u in order:

        for v in graph.adj[u]:

            candidate = coordinates[u] + graph.weights[u]

            coordinates[v] = max(coordinates[v], candidate)

    return coordinates


def calculate_latest_coordinates(graph, boundary):
    """
    Calculate latest feasible coordinates from the right/top boundary.

    boundary = outline width for horizontal graph.
    boundary = layout height for vertical graph.
    """

    if boundary < 0:
        raise ValueError("Boundary cannot be negative.")

    order = graph.topological_sort()

    latest = {node: float("inf") for node in graph.weights}

    latest[SINK] = boundary

    for u in reversed(order):

        if u == SINK:
            continue

        if graph.adj[u]:

            latest[u] = min(latest[v] - graph.weights[u] for v in graph.adj[u])

    return latest


def calculate_layout(
    blocks, horizontal_constraints, vertical_constraints, outline_width
):
    """
    Calculate:
    - Earliest block positions (LL and BL)
    - Latest block positions (RL and TL)
    - Horizontal and vertical slack
    - Layout dimensions
    - Critical paths
    - Fixed-outline feasibility
    """

    if outline_width <= 0:
        raise ValueError("Outline width must be positive.")

    # Build constraint graphs.
    h_graph = build_constraint_graph(blocks, horizontal_constraints, "horizontal")

    v_graph = build_constraint_graph(blocks, vertical_constraints, "vertical")

    # Calculate earliest positions.
    x_coordinates = calculate_coordinates(h_graph)
    y_coordinates = calculate_coordinates(v_graph)

    # Calculate layout dimensions.
    layout_width = x_coordinates[SINK]
    layout_height = y_coordinates[SINK]

    # Calculate latest positions.
    rl_coordinates = calculate_latest_coordinates(h_graph, outline_width)

    tl_coordinates = calculate_latest_coordinates(v_graph, layout_height)

    # Calculate horizontal slack.
    # LL = earliest left position.
    # RL = latest left position.
    horizontal_slack = {}

    for name in blocks:

        horizontal_slack[name] = max(0.0, rl_coordinates[name] - x_coordinates[name])

    # Calculate vertical slack.
    # BL = earliest bottom position.
    # TL = latest bottom position.
    vertical_slack = {}

    for name in blocks:

        vertical_slack[name] = max(0.0, tl_coordinates[name] - y_coordinates[name])

    # Find critical paths.
    hcp_weight, hcp_path = h_graph.longest_path(SOURCE)
    vcp_weight, vcp_path = v_graph.longest_path(SOURCE)

    # Collect block placements.
    placements = {}

    for name, block in blocks.items():

        placements[name] = {
            "x": x_coordinates[name],
            "y": y_coordinates[name],
            "width": block.width,
            "height": block.height,
        }

    return {
        "width": layout_width,
        "height": layout_height,
        "outline_width": outline_width,
        "feasible": layout_width <= outline_width + 1e-9,
        "placements": placements,
        "horizontal_critical_path": hcp_path,
        "vertical_critical_path": vcp_path,
        "horizontal_path_weight": hcp_weight,
        "vertical_path_weight": vcp_weight,
        "horizontal_slack": horizontal_slack,
        "vertical_slack": vertical_slack,
        # Boundary coordinates are also returned for debugging.
        "LL": x_coordinates,
        "RL": rl_coordinates,
        "BL": y_coordinates,
        "TL": tl_coordinates,
    }
