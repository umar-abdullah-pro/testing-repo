"""
FloorSet placement-constraint utilities.

Constraint columns:
[fixed, preplaced, mib_id, cluster_id, boundary_code]

Boundary bitmask:
1=left, 2=right, 4=top, 8=bottom
"""

from collections import defaultdict


def parse_placement_constraints(block_names, constraint_rows):
    """Convert FloorSet's five-column constraint rows into block-wise data."""
    if len(block_names) != len(constraint_rows):
        raise ValueError("Block count and constraint-row count do not match.")

    constraints = {}

    for name, row in zip(block_names, constraint_rows):
        if len(row) < 5:
            raise ValueError(f"Constraint row for {name} has fewer than 5 values.")

        values = [int(float(v)) for v in row[:5]]

        constraints[name] = {
            "fixed": values[0] != 0,
            "preplaced": values[1] != 0,
            "mib_id": values[2],
            "cluster_id": values[3],
            "boundary_code": values[4],
        }

    return constraints


def get_shaping_targets(block_names, constraints):
    """
    Fixed and preplaced blocks must not be independently reshaped.
    MIB groups need group-wise shaping, not independent shaping.
    """
    targets = []

    for name in block_names:
        info = constraints[name]

        if info["fixed"] or info["preplaced"]:
            continue

        targets.append(name)

    return targets


def get_mib_groups(constraints):
    """Return MIB groups as {group_id: [block_names]}."""
    groups = defaultdict(list)

    for name, info in constraints.items():
        group_id = info["mib_id"]
        if group_id > 0:
            groups[group_id].append(name)

    return dict(groups)


def get_cluster_groups(constraints):
    """Return cluster groups as {group_id: [block_names]}."""
    groups = defaultdict(list)

    for name, info in constraints.items():
        group_id = info["cluster_id"]
        if group_id > 0:
            groups[group_id].append(name)

    return dict(groups)


def check_fixed_constraints(blocks, reference_dimensions, constraints, tolerance=1e-6):
    """Check dimensions only for blocks marked as fixed."""

    violations = []

    for name, info in constraints.items():

        if not info["fixed"]:
            continue

        if name not in blocks or name not in reference_dimensions:
            violations.append(name)
            continue

        block = blocks[name]
        ref_w, ref_h = reference_dimensions[name]

        if (
            abs(block.width - ref_w) > tolerance
            or abs(block.height - ref_h) > tolerance
        ):
            violations.append(name)

    return violations


def check_preplaced_constraints(
    placements, reference_placements, constraints, tolerance=1e-6
):
    """
    Check exact position and dimensions for preplaced blocks.

    Placement format: {name: (x, y, width, height)}
    """
    violations = []

    for name, info in constraints.items():
        if not info["preplaced"]:
            continue

        if name not in placements or name not in reference_placements:
            violations.append(name)
            continue

        current = placements[name]
        reference = reference_placements[name]

        if any(
            abs(float(a) - float(b)) > tolerance for a, b in zip(current, reference)
        ):
            violations.append(name)

    return violations


def check_mib_constraints(blocks, constraints, tolerance=1e-4):
    """All blocks in one MIB group must have identical width and height."""
    violations = []
    groups = get_mib_groups(constraints)

    for group_id, names in groups.items():
        if len(names) < 2:
            continue

        first = blocks[names[0]]

        for name in names[1:]:
            block = blocks[name]

            if (
                abs(block.width - first.width) > tolerance
                or abs(block.height - first.height) > tolerance
            ):
                violations.append((group_id, names[0], name))

    return violations


def _touch_or_overlap(a, b, tolerance=1e-6):
    """True if two rectangles touch or overlap (including edge contact)."""
    ax, ay, aw, ah = a
    bx, by, bw, bh = b

    separated = (
        ax + aw < bx - tolerance
        or bx + bw < ax - tolerance
        or ay + ah < by - tolerance
        or by + bh < ay - tolerance
    )

    return not separated


def check_cluster_constraints(placements, constraints):
    """
    A cluster is valid when all its blocks form one connected component.
    Blocks are connected when their rectangles touch or overlap.
    """
    violations = []
    groups = get_cluster_groups(constraints)

    for group_id, names in groups.items():
        names = [n for n in names if n in placements]

        if len(names) < 2:
            continue

        visited = {names[0]}
        stack = [names[0]]

        while stack:
            current = stack.pop()

            for other in names:
                if other in visited:
                    continue

                if _touch_or_overlap(placements[current], placements[other]):
                    visited.add(other)
                    stack.append(other)

        if len(visited) != len(names):
            violations.append(group_id)

    return violations


def check_boundary_constraints(placements, constraints, tolerance=1e-5):
    """
    Check boundary bitmask against the overall placement bounding box.
    Placement format: {name: (x, y, width, height)}
    """
    if not placements:
        return []

    x_min = min(p[0] for p in placements.values())
    y_min = min(p[1] for p in placements.values())
    x_max = max(p[0] + p[2] for p in placements.values())
    y_max = max(p[1] + p[3] for p in placements.values())

    violations = []

    for name, info in constraints.items():
        code = info["boundary_code"]

        if code == 0:
            continue

        if name not in placements:
            violations.append(name)
            continue

        x, y, width, height = placements[name]

        checks = {
            1: abs(x - x_min) <= tolerance,
            2: abs(x + width - x_max) <= tolerance,
            4: abs(y + height - y_max) <= tolerance,
            8: abs(y - y_min) <= tolerance,
        }

        valid = all(checks[bit] for bit in (1, 2, 4, 8) if code & bit)

        if not valid:
            violations.append(name)

    return violations
