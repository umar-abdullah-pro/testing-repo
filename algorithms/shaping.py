
import math


def apply_shaping(blocks, horizontal_increments, vertical_increments):
    """
    Apply calculated shaping increments to blocks.

    Horizontal shaping:
        Increase width while preserving area.

    Vertical shaping:
        Increase height while preserving area.
    """

    # Apply horizontal shaping first.
    for name, delta in horizontal_increments.items():

        if name not in blocks:
            raise ValueError(f"Unknown block: {name}")

        if not math.isfinite(delta) or delta < 0:
            raise ValueError(
                "Shaping increment must be finite and non-negative."
            )

        block = blocks[name]

        new_width = min(
            block.width + delta,
            block.effective_max_width
        )

        block.set_width(new_width)

    # Apply vertical shaping.
    for name, delta in vertical_increments.items():

        if name not in blocks:
            raise ValueError(f"Unknown block: {name}")

        if not math.isfinite(delta) or delta < 0:
            raise ValueError(
                "Shaping increment must be finite and non-negative."
            )

        block = blocks[name]

        new_height = min(
            block.height + delta,
            block.effective_max_height
        )

        new_width = block.area / new_height

        if (
            new_width < block.effective_min_width - 1e-9
            or new_width > block.effective_max_width + 1e-9
        ):
            raise ValueError(
                f"Vertical shaping violates effective width bounds "
                f"for {name}: width={new_width:.8f}, "
                f"allowed=[{block.effective_min_width:.8f}, "
                f"{block.effective_max_width:.8f}]"
            )

        block.set_width(new_width)

    return blocks
