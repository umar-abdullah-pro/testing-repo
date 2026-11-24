def initialize_blocks_for_sds(blocks, preserve_blocks=None):
    """Initialize movable blocks at minimum feasible width.

    Blocks in preserve_blocks retain the width they had when the algorithm
    was called (normally the reference width loaded from FloorSet).
    """
    preserve_blocks = set(preserve_blocks or [])

    for name, block in blocks.items():
        if name in preserve_blocks:
            # Validate the existing reference width without changing it.
            block.set_width(block.width)
            continue

        feasible_min_width = max(block.min_width, block.area / block.max_height)
        feasible_max_width = min(block.max_width, block.area / block.min_height)

        if feasible_min_width > feasible_max_width + 1e-9:
            raise ValueError(f"Block {name} has no feasible width.")

        block.set_width(feasible_min_width)

    return blocks
