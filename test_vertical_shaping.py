from floorplan.blocks import Block
from algorithms.shaping import apply_shaping


def test_vertical_shaping():
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

    original_area = block.area
    original_width = block.width
    original_height = block.height

    print("BEFORE VERTICAL SHAPING")
    print(f"Width  : {original_width:.4f}")
    print(f"Height : {original_height:.4f}")
    print(f"Area   : {original_area:.4f}")

    # Increase height by 1 unit.
    apply_shaping(
        blocks,
        horizontal_increments={},
        vertical_increments={"A": 1.0},
    )

    print("\nAFTER VERTICAL SHAPING")
    print(f"Width  : {block.width:.4f}")
    print(f"Height : {block.height:.4f}")
    print(f"Area   : {block.width * block.height:.4f}")

    # Verify area is preserved.
    assert abs(block.width * block.height - original_area) < 1e-8

    # Verify height increased.
    assert block.height > original_height

    # Verify width decreased.
    assert block.width < original_width

    # Expected: height = 5, width = 4.
    assert abs(block.height - 5.0) < 1e-8
    assert abs(block.width - 4.0) < 1e-8

    print("\nPASS: Vertical shaping is working correctly.")


if __name__ == "__main__":
    test_vertical_shaping()
