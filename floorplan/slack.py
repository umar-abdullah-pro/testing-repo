SOURCE = "SOURCE"
SINK = "SINK"


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
