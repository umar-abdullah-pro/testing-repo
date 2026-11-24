def calculate_path_capacity(graph, blocks, axis):
    """
    Calculate maximum remaining shaping capacity on a
    SOURCE-to-SINK path passing through each block.
    """

    if axis not in ("horizontal", "vertical"):
        raise ValueError("Axis must be 'horizontal' or 'vertical'.")

    room = {}

    for name, block in blocks.items():
        if axis == "horizontal":
            room[name] = max(0.0, block.max_width - block.width)
        else:
            room[name] = max(0.0, block.max_height - block.height)

    room["SOURCE"] = 0.0
    room["SINK"] = 0.0

    order = graph.topological_sort()

    forward = {node: float("-inf") for node in graph.weights}
    forward["SOURCE"] = 0.0

    for u in order:
        if forward[u] == float("-inf"):
            continue

        for v in graph.adj[u]:
            candidate = forward[u] + room[v]
            forward[v] = max(forward[v], candidate)

    backward = {node: float("-inf") for node in graph.weights}
    backward["SINK"] = 0.0

    for u in reversed(order):
        if u == "SINK":
            continue

        for v in graph.adj[u]:
            if backward[v] == float("-inf"):
                continue

            candidate = room[v] + backward[v]
            backward[u] = max(backward[u], candidate)

    path_capacity = {}

    for name in blocks:
        if forward[name] == float("-inf") or backward[name] == float("-inf"):
            path_capacity[name] = 0.0
        else:
            path_capacity[name] = forward[name] + backward[name]

    return path_capacity


def calculate_shaping_increments(
    blocks,
    graph,
    slack,
    target_blocks,
    axis,
    beta=1.0,
):
    """
    Calculate alpha-based shaping increments.

    Horizontal:
        delta_width = alpha * horizontal_slack

    Vertical:
        delta_height = beta * alpha * vertical_slack
    """

    if axis not in ("horizontal", "vertical"):
        raise ValueError("Axis must be 'horizontal' or 'vertical'.")

    if not 0.0 <= beta <= 1.0:
        raise ValueError("Beta must be between 0 and 1.")

    path_capacity = calculate_path_capacity(graph, blocks, axis)

    increments = {}

    for name in target_blocks:
        if name not in blocks or name not in slack:
            continue

        block = blocks[name]

        if axis == "horizontal":
            remaining_room = max(0.0, block.max_width - block.width)
        else:
            remaining_room = max(0.0, block.max_height - block.height)

        denominator = path_capacity[name]

        if denominator <= 1e-12 or remaining_room <= 1e-12:
            increments[name] = 0.0
            continue

        alpha = remaining_room / denominator

        delta = alpha * max(0.0, slack[name])

        if axis == "vertical":
            delta *= beta

        delta = min(delta, remaining_room)

        increments[name] = max(0.0, delta)

    return increments
