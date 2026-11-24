SOURCE = "SOURCE"
SINK = "SINK"


def calculate_slack(graph, weights, source, sink, total_length):
    """
    Calculate slack for a simple graph represented by adjacency dictionaries.

    This compatibility helper supports existing scripts that pass:
    graph={node: [successors...]}, weights={node: weight}, source, sink.
    """
    if total_length < 0:
        raise ValueError("Total length cannot be negative.")

    if source not in graph or sink not in graph:
        raise ValueError("Source and sink must exist in the graph.")

    indegree = {node: 0 for node in graph}
    adj = {node: list(neighbors) for node, neighbors in graph.items()}

    for u, neighbors in adj.items():
        if u not in weights:
            raise ValueError(f"Missing weight for node: {u}")

        for v in neighbors:
            if v not in graph:
                raise ValueError(f"Unknown graph node: {v}")
            if v not in weights:
                raise ValueError(f"Missing weight for node: {v}")
            indegree[v] += 1

    from collections import deque
    queue = deque(node for node in graph if indegree[node] == 0)
    order = []

    while queue:
        u = queue.popleft()
        order.append(u)

        for v in adj[u]:
            indegree[v] -= 1
            if indegree[v] == 0:
                queue.append(v)

    if len(order) != len(graph):
        raise ValueError("Cycle detected in slack graph.")

    forward = {node: float("-inf") for node in graph}
    forward[source] = 0.0

    for u in order:
        if forward[u] == float("-inf"):
            continue

        for v in adj[u]:
            candidate = forward[u] + weights[u]
            forward[v] = max(forward[v], candidate)

    backward = {node: float("-inf") for node in graph}
    backward[sink] = 0.0

    for u in reversed(order):
        if u == sink:
            continue

        for v in adj[u]:
            if backward[v] == float("-inf"):
                continue

            candidate = weights[v] + backward[v]
            backward[u] = max(backward[u], candidate)

    slack = {}

    for node in graph:
        if node in (source, sink):
            continue

        if forward[node] == float("-inf") or backward[node] == float("-inf"):
            continue

        slack[node] = max(
            0.0,
            total_length - forward[node] - weights[node] - backward[node],
        )

    return slack


def calculate_graph_slack(graph, total_length):
    """
    Calculate slack for every block in a weighted constraint DAG.

    Forward distance includes the current node's weight.
    Backward distance excludes the current node's weight.
    """

    order = graph.topological_sort()

    # Forward longest-path distances from SOURCE.
    forward = {node: float("-inf") for node in graph.weights}

    forward[SOURCE] = 0.0

    for u in order:
        if forward[u] == float("-inf"):
            continue

        for v in graph.adj[u]:
            candidate = forward[u] + graph.weights[u]
            forward[v] = max(forward[v], candidate)

    # Backward longest-path distances from each node's END to SINK.
    backward = {node: float("-inf") for node in graph.weights}

    backward[SINK] = 0.0

    for u in reversed(order):
        if u == SINK:
            continue

        for v in graph.adj[u]:
            if backward[v] == float("-inf"):
                continue

            candidate = graph.weights[v] + backward[v]
            backward[u] = max(backward[u], candidate)

    # Calculate slack.
    slack = {}

    for node in graph.weights:

        if node in (SOURCE, SINK):
            continue

        if forward[node] == float("-inf"):
            slack[node] = None
            continue

        if backward[node] == float("-inf"):
            slack[node] = None
            continue

        slack[node] = (
            total_length - forward[node] - graph.weights[node] - backward[node]
        )

    return slack
