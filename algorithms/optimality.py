"""
Paper: Optimal Slack-Driven Block Shaping Algorithm
Authors: Yan and Chu, ISPD 2012

Implements the two optimality conditions from Section 4:

Lemma 2:
    If there exists a hard VCP, the solution is optimal.

Lemma 3:
    If there is at most one soft HCP OR at most one soft VCP,
    the solution is optimal.

Critical paths are represented using critical subgraphs.
The implementation counts paths using dynamic programming,
without explicitly enumerating every critical path.
"""

from collections import defaultdict

EPSILON = 1e-7


def _longest_path_distances(graph):
    """
    Calculate longest-path distances:
        forward[node]: SOURCE to node, including node weight.
        backward[node]: node to SINK, including node weight.
    """

    order = graph.topological_sort()

    forward = {node: float("-inf") for node in graph.weights}

    forward["SOURCE"] = 0.0

    for u in order:
        if forward[u] == float("-inf"):
            continue

        for v in graph.adj[u]:
            candidate = forward[u] + graph.weights[v]
            forward[v] = max(forward[v], candidate)

    backward = {node: float("-inf") for node in graph.weights}

    backward["SINK"] = 0.0

    for u in reversed(order):
        if u == "SINK":
            continue

        for v in graph.adj[u]:
            if backward[v] == float("-inf"):
                continue

            candidate = graph.weights[u] + backward[v]
            backward[u] = max(backward[u], candidate)

    layout_length = forward["SINK"]

    if layout_length == float("-inf"):
        raise ValueError("No SOURCE-to-SINK path exists.")

    return forward, backward, layout_length


def _build_critical_subgraph(graph, tolerance=EPSILON):
    """
    Extract all edges and nodes belonging to at least one
    longest SOURCE-to-SINK path.
    """

    forward, backward, length = _longest_path_distances(graph)

    critical_nodes = set()
    critical_edges = defaultdict(list)

    for node in graph.weights:

        if forward[node] != float("-inf") and backward[node] != float("-inf"):
            path_length = forward[node] + backward[node] - graph.weights[node]

            if abs(path_length - length) <= tolerance:
                critical_nodes.add(node)

    for u in graph.weights:

        if u not in critical_nodes:
            continue

        for v in graph.adj[u]:

            if v not in critical_nodes:
                continue

            path_length = forward[u] + backward[v]

            if abs(path_length - length) <= tolerance:
                critical_edges[u].append(v)

    return {
        "nodes": critical_nodes,
        "edges": critical_edges,
        "length": length,
        "forward": forward,
        "backward": backward,
    }


def _count_critical_paths(critical_graph, forbidden_nodes=None):
    """
    Count SOURCE-to-SINK paths in a critical subgraph.

    forbidden_nodes:
        Nodes that paths are not allowed to contain.

    Python integers support arbitrarily large path counts.
    """

    forbidden_nodes = set(forbidden_nodes or [])

    nodes = critical_graph["nodes"]
    edges = critical_graph["edges"]

    if "SOURCE" not in nodes or "SINK" not in nodes:
        return 0

    if "SOURCE" in forbidden_nodes or "SINK" in forbidden_nodes:
        return 0

    order = list(nodes)

    # Preserve topological order using the graph's original
    # forward distances as the ordering key.
    order.sort(key=lambda node: critical_graph["forward"][node])

    counts = {node: 0 for node in nodes}
    counts["SOURCE"] = 1

    for u in order:

        if u in forbidden_nodes:
            continue

        for v in edges.get(u, []):

            if v in forbidden_nodes:
                continue

            counts[v] += counts[u]

    return counts.get("SINK", 0)


def _soft_critical_path_count(critical_graph, soft_intersection_nodes):
    """
    Count critical paths containing at least one soft
    intersection block.
    """

    total_paths = _count_critical_paths(critical_graph)

    paths_without_soft_intersection = _count_critical_paths(
        critical_graph,
        forbidden_nodes=soft_intersection_nodes,
    )

    return (
        total_paths - paths_without_soft_intersection,
        total_paths,
    )


def analyze_critical_paths(
    blocks,
    horizontal_graph,
    vertical_graph,
    hard_blocks=None,
    tolerance=EPSILON,
):
    """
    Analyse HCPs, VCPs and their intersection blocks.

    Returns:
        horizontal critical subgraph
        vertical critical subgraph
        intersection blocks
        hard/soft intersection blocks
        number of soft HCPs
        number of soft VCPs
        whether a hard VCP exists
    """

    hard_blocks = set(hard_blocks or [])

    unknown = hard_blocks - set(blocks)

    if unknown:
        raise ValueError(f"Unknown hard blocks: {sorted(unknown)}")

    h_critical = _build_critical_subgraph(
        horizontal_graph,
        tolerance,
    )

    v_critical = _build_critical_subgraph(
        vertical_graph,
        tolerance,
    )

    # A block is an intersection block if it lies on at least
    # one HCP and at least one VCP.
    intersection_blocks = h_critical["nodes"] & v_critical["nodes"] & set(blocks)

    soft_intersection_blocks = intersection_blocks - hard_blocks

    hard_intersection_blocks = intersection_blocks & hard_blocks

    # Count soft horizontal and vertical critical paths.
    soft_hcp_count, total_hcp_count = _soft_critical_path_count(
        h_critical,
        soft_intersection_blocks,
    )

    soft_vcp_count, total_vcp_count = _soft_critical_path_count(
        v_critical,
        soft_intersection_blocks,
    )

    # A hard VCP is a vertical critical path that contains
    # no soft intersection block.
    hard_vcp_count = _count_critical_paths(
        v_critical,
        forbidden_nodes=soft_intersection_blocks,
    )

    return {
        "horizontal_critical_length": h_critical["length"],
        "vertical_critical_length": v_critical["length"],
        "horizontal_critical_nodes": (h_critical["nodes"] - {"SOURCE", "SINK"}),
        "vertical_critical_nodes": (v_critical["nodes"] - {"SOURCE", "SINK"}),
        "intersection_blocks": intersection_blocks,
        "hard_intersection_blocks": hard_intersection_blocks,
        "soft_intersection_blocks": soft_intersection_blocks,
        "total_hcp_count": total_hcp_count,
        "total_vcp_count": total_vcp_count,
        "soft_hcp_count": soft_hcp_count,
        "soft_vcp_count": soft_vcp_count,
        "hard_vcp_count": hard_vcp_count,
        "hard_vcp_exists": hard_vcp_count > 0,
        "horizontal_critical_graph": h_critical,
        "vertical_critical_graph": v_critical,
    }


def check_optimality_lemmas(
    blocks,
    horizontal_graph,
    vertical_graph,
    hard_blocks=None,
    tolerance=EPSILON,
):
    """
    Check the optimality conditions from paper Section 4.

    Lemma 2:
        At least one hard VCP exists.

    Lemma 3:
        At most one soft HCP OR at most one soft VCP exists.

    Returns a diagnostic dictionary.
    """

    analysis = analyze_critical_paths(
        blocks=blocks,
        horizontal_graph=horizontal_graph,
        vertical_graph=vertical_graph,
        hard_blocks=hard_blocks,
        tolerance=tolerance,
    )

    lemma_2 = analysis["hard_vcp_exists"]

    lemma_3 = analysis["soft_hcp_count"] <= 1 or analysis["soft_vcp_count"] <= 1

    optimal = lemma_2 or lemma_3

    if lemma_2:
        reason = "Lemma 2 satisfied: a hard VCP exists."

    elif lemma_3:
        reason = (
            "Lemma 3 satisfied: at most one soft HCP " "or at most one soft VCP exists."
        )

    else:
        reason = (
            "Neither Lemma 2 nor Lemma 3 is satisfied. "
            "Geometric Programming improvement is required."
        )

    return {
        "optimal": optimal,
        "lemma_2_satisfied": lemma_2,
        "lemma_3_satisfied": lemma_3,
        "reason": reason,
        **analysis,
    }


def print_optimality_report(result):
    """Print a readable optimality diagnostic report."""

    print("\n========== SDS OPTIMALITY REPORT ==========")

    print(
        "Horizontal critical length:",
        f"{result['horizontal_critical_length']:.6f}",
    )

    print(
        "Vertical critical length:",
        f"{result['vertical_critical_length']:.6f}",
    )

    print(
        "Total HCPs:",
        result["total_hcp_count"],
    )

    print(
        "Total VCPs:",
        result["total_vcp_count"],
    )

    print(
        "Soft HCPs:",
        result["soft_hcp_count"],
    )

    print(
        "Soft VCPs:",
        result["soft_vcp_count"],
    )

    print(
        "Hard VCPs:",
        result["hard_vcp_count"],
    )

    print(
        "Intersection blocks:",
        sorted(result["intersection_blocks"]),
    )

    print(
        "Hard intersection blocks:",
        sorted(result["hard_intersection_blocks"]),
    )

    print(
        "Soft intersection blocks:",
        sorted(result["soft_intersection_blocks"]),
    )

    print(
        "Lemma 2:",
        "SATISFIED" if result["lemma_2_satisfied"] else "NOT SATISFIED",
    )

    print(
        "Lemma 3:",
        "SATISFIED" if result["lemma_3_satisfied"] else "NOT SATISFIED",
    )

    print(
        "Optimality established:",
        result["optimal"],
    )

    print("Reason:", result["reason"])

    print("===========================================\n")
