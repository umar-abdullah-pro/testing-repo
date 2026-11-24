
import math


def calculate_path_capacity(graph, blocks, axis):
    """
    Maximum remaining shaping room on a SOURCE-to-SINK path
    passing through each block.
    """

    if axis not in ("horizontal", "vertical"):
        raise ValueError("Axis must be 'horizontal' or 'vertical'.")

    room = {"SOURCE": 0.0, "SINK": 0.0}

    for name, block in blocks.items():
        if axis == "horizontal":
            maximum = block.effective_max_width
            current = block.width
        else:
            maximum = block.effective_max_height
            current = block.height

        room[name] = max(0.0, float(maximum) - float(current))

    order = graph.topological_sort()

    # Longest remaining room from SOURCE to each node.
    forward = {node: -math.inf for node in graph.weights}
    forward["SOURCE"] = 0.0

    for u in order:
        if not math.isfinite(forward[u]):
            continue

        for v in graph.adj[u]:
            candidate = forward[u] + room.get(v, 0.0)
            forward[v] = max(forward[v], candidate)

    # Longest remaining room from each node to SINK,
    # excluding the current node's own room.
    backward = {node: -math.inf for node in graph.weights}
    backward["SINK"] = 0.0

    for u in reversed(order):
        if u == "SINK":
            continue

        candidates = [
            room.get(v, 0.0) + backward[v]
            for v in graph.adj[u]
            if math.isfinite(backward[v])
        ]

        if candidates:
            backward[u] = max(candidates)

    path_capacity = {}

    for name in blocks:
        if (
            not math.isfinite(forward.get(name, -math.inf))
            or not math.isfinite(backward.get(name, -math.inf))
        ):
            path_capacity[name] = 0.0
        else:
            # forward includes this block; backward includes successors.
            path_capacity[name] = max(
                0.0, forward[name] + backward[name]
            )

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
    Calculate path-capacity-based shaping increments.

    Horizontal: increase width.
    Vertical: increase height.

    For a target block i:
        delta_i = (remaining_room_i / path_capacity_i) * slack_i

    Vertical increments are additionally multiplied by beta.
    """

    if axis not in ("horizontal", "vertical"):
        raise ValueError("Axis must be 'horizontal' or 'vertical'.")

    beta = float(beta)

    if not math.isfinite(beta) or not 0.0 <= beta <= 1.0:
        raise ValueError("Beta must be finite and between 0 and 1.")

    path_capacity = calculate_path_capacity(graph, blocks, axis)
    increments = {}

    for name in target_blocks:
        if name not in blocks:
            raise ValueError(f"Unknown target block: {name}")

        if name not in slack:
            raise KeyError(f"Slack missing for target block: {name}")

        slack_value = float(slack[name])

        if not math.isfinite(slack_value):
            raise ValueError(f"Non-finite slack for block {name}")

        if slack_value < 0:
            raise ValueError(f"Negative slack for block {name}: {slack_value}")

        block = blocks[name]

        if axis == "horizontal":
            maximum = block.effective_max_width
            current = block.width
        else:
            maximum = block.effective_max_height
            current = block.height

        remaining_room = max(0.0, float(maximum) - float(current))
        denominator = path_capacity.get(name, 0.0)

        if remaining_room <= 0.0 or denominator <= 1e-12:
            increments[name] = 0.0
            continue

        alpha = min(1.0, remaining_room / denominator)
        delta = alpha * slack_value

        if axis == "vertical":
            delta *= beta

        increments[name] = min(
            max(0.0, delta),
            remaining_room,
        )

    return increments
