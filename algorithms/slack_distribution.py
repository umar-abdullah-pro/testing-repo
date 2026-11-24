
def calculate_path_capacity(graph, blocks, axis):
    """
    Calculate maximum remaining shaping capacity on a
    SOURCE-to-SINK path passing through each block.
    """

    room = {}

    for name, block in blocks.items():
        if axis == "horizontal":
            max_dimension = getattr(
                block, "effective_max_width", block.max_width
            )
            room[name] = max(0.0, max_dimension - block.width)

        elif axis == "vertical":
            max_dimension = getattr(
                block, "effective_max_height", block.max_height
            )
            room[name] = max(0.0, max_dimension - block.height)

        else:
            raise ValueError("Axis must be 'horizontal' or 'vertical'.")

    room["SOURCE"] = 0.0
    room["SINK"] = 0.0

    order = graph.topological_sort()

    forward = {node: float("-inf") for node in graph.weights}
    forward["SOURCE"] = 0.0

    for u in order:
        for v in graph.adj[u]:
            candidate = forward[u] + room.get(v, 0.0)
            forward[v] = max(forward[v], candidate)

    backward = {node: float("-inf") for node in graph.weights}
    backward["SINK"] = 0.0

    for u in reversed(order):
        for v in graph.adj[u]:
            candidate = room.get(v, 0.0) + backward[v]
            backward[u] = max(backward[u], candidate)

    path_capacity = {}

    for name in blocks:
        # forward[name] already includes this block's room.
        # backward[name] includes only the nodes after it.
        path_capacity[name] = max(
            0.0, forward[name] + backward[name]
        )

    return path_capacity


def calculate_shaping_increments(
    blocks, graph, slack, target_blocks, axis, beta=1.0
):
    """
    Calculate alpha-based shaping increments.

    Horizontal: increase width.
    Vertical: increase height.
    """

    if not 0.0 <= beta <= 1.0:
        raise ValueError("Beta must be between 0 and 1.")

    path_capacity = calculate_path_capacity(graph, blocks, axis)
    increments = {}

    for name in target_blocks:
        if name not in blocks:
            raise ValueError(f"Unknown target block: {name}")

        block = blocks[name]

        if axis == "horizontal":
            max_dimension = getattr(
                block, "effective_max_width", block.max_width
            )
            current_dimension = block.width

        elif axis == "vertical":
            max_dimension = getattr(
                block, "effective_max_height", block.max_height
            )
            current_dimension = block.height

        else:
            raise ValueError("Axis must be 'horizontal' or 'vertical'.")

        remaining_room = max(
            0.0, max_dimension - current_dimension
        )

        denominator = path_capacity.get(name, 0.0)

        if denominator <= 1e-12:
            increments[name] = 0.0
            continue

        alpha = remaining_room / denominator
        delta = alpha * max(0.0, slack[name])

        if axis == "vertical":
            delta *= beta

        increments[name] = min(delta, remaining_room)

    return increments
