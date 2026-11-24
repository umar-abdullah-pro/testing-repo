from floorplan.blocks import Block
from graph.dag import DAG
from algorithms.slack_distribution import calculate_shaping_increments
from algorithms.shaping import apply_shaping


def test_vertical_sds():

    # 1. Create a test block.
    block = Block(
        name="A",
        area=20.0,
        min_width=2.0,
        max_width=10.0,
        min_height=2.0,
        max_height=8.0,
        width=5.0,
    )

    blocks = {"A": block}

    # 2. Create a simple vertical constraint graph.
    graph = DAG()

    graph.add_node("SOURCE", 0.0)
    graph.add_node("A", block.height)
    graph.add_node("SINK", 0.0)

    graph.add_edge("SOURCE", "A")
    graph.add_edge("A", "SINK")

    # 3. Calculate initial longest path.
    initial_height, initial_path = graph.longest_path(start="SOURCE")

    print("\nINITIAL STATE")
    print("Block width :", block.width)
    print("Block height:", block.height)
    print("Longest path:", initial_height)
    print("Path        :", initial_path)

    # 4. Give the block vertical slack.
    vertical_slack = {"A": 1.0}

    # A is the vertical shaping target.
    vertical_targets = ["A"]

    # 5. Calculate vertical shaping increment.
    increments = calculate_shaping_increments(
        blocks=blocks,
        graph=graph,
        slack=vertical_slack,
        target_blocks=vertical_targets,
        axis="vertical",
        beta=1.0,
    )

    print("\nVERTICAL SHAPING INCREMENTS")
    print(increments)

    # 6. Apply vertical shaping.
    apply_shaping(
        blocks=blocks,
        horizontal_increments={},
        vertical_increments=increments,
    )

    # 7. Update graph node weight after shaping.
    graph.weights["A"] = block.height

    # 8. Calculate updated longest path.
    final_height, final_path = graph.longest_path(start="SOURCE")

    print("\nFINAL STATE")
    print("Block width :", block.width)
    print("Block height:", block.height)
    print("Block area  :", block.width * block.height)
    print("Longest path:", final_height)
    print("Path        :", final_path)

    # 9. Verify results.
    assert increments["A"] > 0.0
    assert abs(block.height - 5.0) < 1e-8
    assert abs(block.width - 4.0) < 1e-8
    assert abs(block.area - block.width * block.height) < 1e-8
    assert final_height > initial_height

    print("\nPASS: Vertical SDS increment and DAG update work correctly.")


if __name__ == "__main__":
    test_vertical_sds()
