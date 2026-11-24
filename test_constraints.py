from floorplan.blocks import Block
from floorplan.constraints import (
    parse_placement_constraints,
    get_shaping_targets,
    get_mib_groups,
    get_cluster_groups,
    check_fixed_constraints,
    check_mib_constraints,
)

names = ["B0", "B1", "B2", "B3"]

rows = [
    [1, 0, 0, 0, 0],
    [0, 0, 1, 0, 10],
    [0, 0, 1, 1, 0],
    [0, 1, 0, 1, 4],
]

constraints = parse_placement_constraints(names, rows)

blocks = {
    name: Block(name, 100, 5, 20, 5, 20, width=10)
    for name in names
}

reference_dimensions = {
    name: (block.width, block.height)
    for name, block in blocks.items()
}

print("Shaping targets:", get_shaping_targets(names, constraints))
print("MIB groups:", get_mib_groups(constraints))
print("Cluster groups:", get_cluster_groups(constraints))
print("Fixed violations:", check_fixed_constraints(
    blocks, reference_dimensions, constraints
))
print("MIB violations:", check_mib_constraints(blocks, constraints))
print("Constraint parsing test completed.")