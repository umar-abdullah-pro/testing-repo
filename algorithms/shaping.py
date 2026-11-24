import math


def apply_shaping(blocks, horizontal_increments, vertical_increments):
    """
    Apply calculated shaping increments to blocks.

    Horizontal shaping:
        Increase block width while preserving area.

    Vertical shaping:
        Increase block height while preserving area.
    """

    # Apply horizontal shaping first.
    for name, delta in horizontal_increments.items():

        if name not in blocks:
            raise ValueError(f"Unknown block: {name}")

        if not math.isfinite(delta) or delta < 0:
            raise ValueError("Shaping increment must be finite and non-negative.")

        block = blocks[name]

        new_width = min(block.width + delta, block.max_width)

        block.set_width(new_width)

    # Apply vertical shaping.
    for name, delta in vertical_increments.items():

        if name not in blocks:
            raise ValueError(f"Unknown block: {name}")

        if not math.isfinite(delta) or delta < 0:
            raise ValueError("Shaping increment must be finite and non-negative.")

        block = blocks[name]

        new_height = min(block.height + delta, block.max_height)

        new_width = block.area / new_height

        if new_width < block.min_width - 1e-9:
            raise ValueError(
                f"Vertical shaping violates min_width for {name}: "
                f"{new_width} < {block.min_width}"
            )

        if new_width > block.max_width + 1e-9:
            raise ValueError(
                f"Vertical shaping violates max_width for {name}: "
                f"{new_width} > {block.max_width}"
            )

        block.set_width(new_width)

    return blocks
