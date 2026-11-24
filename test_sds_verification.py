
from floorplan.blocks import Block
from graph.dag import DAG

from algorithms.slack_distribution import (
    calculate_path_capacity,
    calculate_shaping_increments,
)

from algorithms.shaping import apply_shaping


def test_area_preservation():
    block = Block("A", 20, 2, 10, 2, 10, 5)

    block.set_width(4)

    assert abs(block.width * block.height - 20) < 1e-9

    print("PASS: Area preservation")


def test_dimension_limits():
    block = Block("B", 20, 2, 8, 2, 10, 5)

    block.set_width(4)

    assert (
        block.effective_min_width
        <= block.width
        <= block.effective_max_width
    )

    assert (
        block.effective_min_height
        <= block.height
        <= block.effective_max_height
    )

    print("PASS: Dimension limits")


def test_path_capacity():
    blocks = {
        "A": Block("A", 20, 2, 8, 2, 10, 4),
        "B": Block("B", 20, 2, 8, 2, 10, 4),
        "C": Block("C", 20, 2, 8, 2, 10, 4),
    }

    graph = DAG()

    graph.add_node("SOURCE", 0)

    for name, block in blocks.items():
        graph.add_node(name, block.width)

    graph.add_node("SINK", 0)

    graph.add_edge("SOURCE", "A")
    graph.add_edge("A", "B")
    graph.add_edge("B", "C")
    graph.add_edge("C", "SINK")

    capacity = calculate_path_capacity(
        graph,
        blocks,
        "horizontal",
    )

    expected = sum(
        block.effective_max_width - block.width
        for block in blocks.values()
    )

    print("Calculated capacity:", capacity["B"])
    print("Expected capacity:", expected)

    assert abs(capacity["B"] - expected) < 1e-9

    print("PASS: Path capacity calculation")


def test_horizontal_shaping():
    blocks = {
        "A": Block("A", 20, 2, 8, 2, 10, 4),
    }

    original_area = blocks["A"].area

    apply_shaping(
        blocks,
        horizontal_increments={"A": 1.0},
        vertical_increments={},
    )

    assert abs(blocks["A"].width - 5.0) < 1e-9

    assert (
        abs(blocks["A"].width * blocks["A"].height - original_area)
        < 1e-9
    )

    print("PASS: Horizontal shaping")


def test_vertical_shaping():
    blocks = {
        "A": Block("A", 20, 2, 8, 2, 10, 5),
    }

    original_area = blocks["A"].area
    original_height = blocks["A"].height

    apply_shaping(
        blocks,
        horizontal_increments={},
        vertical_increments={"A": 1.0},
    )

    assert blocks["A"].height > original_height

    assert abs(
        blocks["A"].width * blocks["A"].height - original_area
    ) < 1e-9

    print("PASS: Vertical shaping")


def test_shaping_increment_calculation():
    blocks = {
        "A": Block("A", 20, 2, 8, 2, 10, 4),
    }

    graph = DAG()

    graph.add_node("SOURCE", 0)
    graph.add_node("A", blocks["A"].width)
    graph.add_node("SINK", 0)

    graph.add_edge("SOURCE", "A")
    graph.add_edge("A", "SINK")

    increments = calculate_shaping_increments(
        blocks=blocks,
        graph=graph,
        slack={"A": 2.0},
        target_blocks=["A"],
        axis="horizontal",
        beta=1.0,
    )

    assert increments["A"] > 0
    assert increments["A"] <= (
        blocks["A"].effective_max_width - blocks["A"].width
    )

    print("PASS: Shaping increment calculation")


if __name__ == "__main__":

    print("\n========== SDS VERIFICATION TESTS ==========\n")

    test_area_preservation()
    test_dimension_limits()
    test_path_capacity()
    test_horizontal_shaping()
    test_vertical_shaping()
    test_shaping_increment_calculation()

    print("\n============================================")
    print("ALL TESTS PASSED")
    print("============================================")
