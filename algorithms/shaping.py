
import math


def _validate_increment(name, delta):
    try:
        delta = float(delta)
    except (TypeError, ValueError):
        raise ValueError(f"Invalid shaping increment for {name}: {delta}")

    if not math.isfinite(delta) or delta < 0.0:
        raise ValueError(
            f"Shaping increment for {name} must be finite and non-negative."
        )

    return delta


def _validate_block(block, name, original_area, tolerance=1e-7):
    if not math.isfinite(block.width) or not math.isfinite(block.height):
        raise ValueError(f"Non-finite dimensions after shaping block {name}.")

    if block.width <= 0 or block.height <= 0:
        raise ValueError(f"Non-positive dimensions after shaping block {name}.")

    if not (
        block.effective_min_width - tolerance
        <= block.width
        <= block.effective_max_width + tolerance
    ):
        raise ValueError(f"Width bounds violated for block {name}.")

    if not (
        block.effective_min_height - tolerance
        <= block.height
        <= block.effective_max_height + tolerance
    ):
        raise ValueError(f"Height bounds violated for block {name}.")

    if abs(block.width * block.height - original_area) > (
        tolerance * max(1.0, original_area)
    ):
        raise ValueError(f"Area preservation violated for block {name}.")


def apply_shaping(blocks, horizontal_increments, vertical_increments):
    """
    Apply area-preserving horizontal and vertical shaping.

    Horizontal shaping increases width and decreases height.
    Vertical shaping increases height and decreases width.

    Horizontal and vertical target sets should be disjoint, as in
    the SDS subset classification (IV versus VI).
    """

    horizontal_names = set(horizontal_increments)
    vertical_names = set(vertical_increments)

    overlap = horizontal_names.intersection(vertical_names)
    if overlap:
        raise ValueError(
            "A block cannot receive horizontal and vertical shaping "
            f"in the same iteration: {sorted(overlap)}"
        )

    original_areas = {
        name: float(block.area)
        for name, block in blocks.items()
    }

    # Apply horizontal shaping.
    for name, raw_delta in horizontal_increments.items():
        if name not in blocks:
            raise ValueError(f"Unknown block: {name}")

        delta = _validate_increment(name, raw_delta)
        block = blocks[name]

        new_width = min(
            block.width + delta,
            block.effective_max_width,
        )

        block.set_width(new_width)
        _validate_block(block, name, original_areas[name])

    # Apply vertical shaping.
    for name, raw_delta in vertical_increments.items():
        if name not in blocks:
            raise ValueError(f"Unknown block: {name}")

        delta = _validate_increment(name, raw_delta)
        block = blocks[name]

        new_height = min(
            block.height + delta,
            block.effective_max_height,
        )

        if new_height <= 0:
            raise ValueError(f"Invalid new height for block {name}.")

        new_width = block.area / new_height

        if not (
            block.effective_min_width - 1e-9
            <= new_width
            <= block.effective_max_width + 1e-9
        ):
            raise ValueError(
                f"Vertical shaping violates width bounds for {name}: "
                f"new width={new_width:.8f}, "
                f"allowed=[{block.effective_min_width:.8f}, "
                f"{block.effective_max_width:.8f}]"
            )

        block.set_width(new_width)
        _validate_block(block, name, original_areas[name])

    return blocks

import math


def _validate_increment(name, delta):
    try:
        delta = float(delta)
    except (TypeError, ValueError):
        raise ValueError(f"Invalid shaping increment for {name}: {delta}")

    if not math.isfinite(delta) or delta < 0.0:
        raise ValueError(
            f"Shaping increment for {name} must be finite and non-negative."
        )

    return delta


def _validate_block(block, name, original_area, tolerance=1e-7):
    if not math.isfinite(block.width) or not math.isfinite(block.height):
        raise ValueError(f"Non-finite dimensions after shaping block {name}.")

    if block.width <= 0 or block.height <= 0:
        raise ValueError(f"Non-positive dimensions after shaping block {name}.")

    if not (
        block.effective_min_width - tolerance
        <= block.width
        <= block.effective_max_width + tolerance
    ):
        raise ValueError(f"Width bounds violated for block {name}.")

    if not (
        block.effective_min_height - tolerance
        <= block.height
        <= block.effective_max_height + tolerance
    ):
        raise ValueError(f"Height bounds violated for block {name}.")

    if abs(block.width * block.height - original_area) > (
        tolerance * max(1.0, original_area)
    ):
        raise ValueError(f"Area preservation violated for block {name}.")


def apply_shaping(blocks, horizontal_increments, vertical_increments):
    """
    Apply area-preserving horizontal and vertical shaping.

    Horizontal shaping increases width and decreases height.
    Vertical shaping increases height and decreases width.

    Horizontal and vertical target sets should be disjoint, as in
    the SDS subset classification (IV versus VI).
    """

    horizontal_names = set(horizontal_increments)
    vertical_names = set(vertical_increments)

    overlap = horizontal_names.intersection(vertical_names)
    if overlap:
        raise ValueError(
            "A block cannot receive horizontal and vertical shaping "
            f"in the same iteration: {sorted(overlap)}"
        )

    original_areas = {
        name: float(block.area)
        for name, block in blocks.items()
    }

    # Apply horizontal shaping.
    for name, raw_delta in horizontal_increments.items():
        if name not in blocks:
            raise ValueError(f"Unknown block: {name}")

        delta = _validate_increment(name, raw_delta)
        block = blocks[name]

        new_width = min(
            block.width + delta,
            block.effective_max_width,
        )

        block.set_width(new_width)
        _validate_block(block, name, original_areas[name])

    # Apply vertical shaping.
    for name, raw_delta in vertical_increments.items():
        if name not in blocks:
            raise ValueError(f"Unknown block: {name}")

        delta = _validate_increment(name, raw_delta)
        block = blocks[name]

        new_height = min(
            block.height + delta,
            block.effective_max_height,
        )

        if new_height <= 0:
            raise ValueError(f"Invalid new height for block {name}.")

        new_width = block.area / new_height

        if not (
            block.effective_min_width - 1e-9
            <= new_width
            <= block.effective_max_width + 1e-9
        ):
            raise ValueError(
                f"Vertical shaping violates width bounds for {name}: "
                f"new width={new_width:.8f}, "
                f"allowed=[{block.effective_min_width:.8f}, "
                f"{block.effective_max_width:.8f}]"
            )

        block.set_width(new_width)
        _validate_block(block, name, original_areas[name])

    return blocks
