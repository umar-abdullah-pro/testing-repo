def initialize_blocks_for_sds(blocks):
    """
    Initialize every block at its minimum allowed width.
    """

    for name, block in blocks.items():
        block.set_width(block.min_width)

    return blocks