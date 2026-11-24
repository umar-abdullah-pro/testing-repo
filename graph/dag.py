from collections import deque
import math


class DAG:
    """
    Directed Acyclic Graph with weighted nodes.
    Each node has a numerical weight.
    Edges represent precedence constraints.
    """

    def __init__(self):
        self.weights = {}
        self.adj = {}

    def add_node(self, node, weight):
        """Add a node and its weight."""

        if node in self.weights:
            raise ValueError(f"Node {node} already exists.")

        if not isinstance(weight, (int, float)):
            raise TypeError("Node weight must be a number.")

        if not math.isfinite(weight) or weight < 0:
            raise ValueError("Node weight must be finite and non-negative.")

        self.weights[node] = float(weight)
        self.adj[node] = []

    def add_edge(self, u, v):
        """Add a directed edge u -> v."""

        if u not in self.adj or v not in self.adj:
            raise ValueError("Both nodes must exist before adding an edge.")

        # Avoid adding the same edge twice.
        if v not in self.adj[u]:
            self.adj[u].append(v)

    def topological_sort(self):
        """
        Return nodes in topological order using Kahn's algorithm.

        Raises ValueError if the graph contains a cycle.
        """

        # Step 1: Calculate incoming edge count for each node.
        indegree = {node: 0 for node in self.weights}

        for u in self.adj:
            for v in self.adj[u]:
                indegree[v] += 1

        # Step 2: Start with nodes having no incoming edges.
        queue = deque(node for node in self.weights if indegree[node] == 0)

        order = []

        # Step 3: Process nodes and update indegrees.
        while queue:
            u = queue.popleft()
            order.append(u)

            for v in self.adj[u]:
                indegree[v] -= 1

                if indegree[v] == 0:
                    queue.append(v)

        # If some nodes remain, a cycle exists.
        if len(order) != len(self.weights):
            raise ValueError("Cycle detected! Graph is not a DAG.")

        return order

    def longest_path(self, start=None):
        """
        Calculate the longest path using node weights.

        If start is None:
            Find the longest path anywhere in the graph.

        Otherwise:
            Find the longest path starting at the given node.

        Returns:
            (maximum_weight, path)
        """

        if not self.weights:
            return 0.0, []

        if start is not None and start not in self.weights:
            raise ValueError(f"Unknown starting node: {start}")

        order = self.topological_sort()

        # Distance stores the best path weight ending at each node.
        if start is None:
            # A path may begin at any node.
            distance = self.weights.copy()
        else:
            # A path must begin at the selected node.
            distance = {node: -math.inf for node in self.weights}
            distance[start] = self.weights[start]

        parent = {node: None for node in self.weights}

        # Dynamic programming over topological order.
        for u in order:

            if distance[u] == -math.inf:
                continue

            for v in self.adj[u]:

                candidate = distance[u] + self.weights[v]

                if candidate > distance[v]:
                    distance[v] = candidate
                    parent[v] = u

        # Find the endpoint with maximum path weight.
        end = max(distance, key=distance.get)
        maximum_weight = distance[end]

        # Reconstruct the path by following parent pointers.
        path = []
        current = end

        while current is not None:
            path.append(current)
            current = parent[current]

        path.reverse()

        return maximum_weight, path
