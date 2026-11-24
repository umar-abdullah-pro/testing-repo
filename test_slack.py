from floorplan.slack import calculate_slack

# Three blocks
blocks = {
    "A": {"width": 5, "height": 4},
    "B": {"width": 6, "height": 4},
    "C": {"width": 3, "height": 4},
}

# Horizontal constraint graph
# A is left of B and C
h_graph = {"SOURCE": ["A"], "A": ["B", "C"], "B": ["SINK"], "C": ["SINK"], "SINK": []}

h_weights = {"SOURCE": 0, "A": 5, "B": 6, "C": 3, "SINK": 0}

# Vertical constraint graph
# B is below C
v_graph = {"SOURCE": ["B"], "B": ["C"], "C": ["SINK"], "SINK": []}

v_weights = {"SOURCE": 0, "B": 4, "C": 4, "SINK": 0}

# Calculate horizontal slack
horizontal_slack = calculate_slack(h_graph, h_weights, "SOURCE", "SINK", 11)

# Calculate vertical slack
vertical_slack = calculate_slack(v_graph, v_weights, "SOURCE", "SINK", 8)

print("HORIZONTAL SLACK")
for block, value in horizontal_slack.items():
    print(block, ":", value)

print("\nVERTICAL SLACK")
for block, value in vertical_slack.items():
    print(block, ":", value)
