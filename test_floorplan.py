from graph.dag import DAG
from floorplan.blocks import Block
from floorplan.packing import build_constraint_graph, calculate_layout
from floorplan.slack import calculate_slack


def test_dag_cycle_detection():
    graph = DAG()
    graph.add_node("A", 1)
    graph.add_node("B", 1)
    graph.add_edge("A", "B")
    graph.add_edge("B", "A")

    try:
        graph.topological_sort()
    except ValueError as error:
        assert "Cycle" in str(error)
    else:
        raise AssertionError("Cycle should be rejected.")


def test_slack_dict_adapter():
    graph = {
        "SOURCE": ["A"],
        "A": ["B", "C"],
        "B": ["SINK"],
        "C": ["SINK"],
        "SINK": [],
    }
    weights = {
        "SOURCE": 0,
        "A": 5,
        "B": 6,
        "C": 3,
        "SINK": 0,
    }

    horizontal = calculate_slack(
        graph, weights, "SOURCE", "SINK", 11
    )

    assert horizontal["A"] == 0.0
    assert horizontal["B"] == 0.0
    assert horizontal["C"] == 3.0


def test_fixed_area_layout():
    blocks = {
        "A": Block("A", 20, 4, 10, 2, 5, width=5),
        "B": Block("B", 24, 4, 8, 3, 6, width=6),
    }

    result = calculate_layout(
        blocks,
        [("A", "B")],
        [],
        outline_width=12,
    )

    assert abs(blocks["A"].area - blocks["A"].width * blocks["A"].height) < 1e-9
    assert abs(blocks["B"].area - blocks["B"].width * blocks["B"].height) < 1e-9
    assert result["feasible"]
    assert set(result["placements"]) == set(blocks)


if __name__ == "__main__":
    test_dag_cycle_detection()
    test_slack_dict_adapter()
    test_fixed_area_layout()
    print("test_floorplan.py passed.")
