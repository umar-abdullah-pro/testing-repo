from dataclasses import dataclass
import math


@dataclass
class Block:
    """
    Represents a VLSI block with:
    - Fixed area
    - Minimum and maximum width
    - Minimum and maximum height
    - A currently selected width
    """

    name: str
    area: float

    min_width: float
    max_width: float

    min_height: float
    max_height: float

    width: float = None

    def __post_init__(self):
        """Validate the block and choose an initial width."""

        values = [
            self.area,
            self.min_width,
            self.max_width,
            self.min_height,
            self.max_height,
        ]

        if not all(math.isfinite(v) for v in values):
            raise ValueError("Block dimensions must be finite numbers.")

        if self.area <= 0:
            raise ValueError("Block area must be positive.")

        if min(self.min_width, self.max_width, self.min_height, self.max_height) <= 0:
            raise ValueError("Dimension limits must be positive.")

        if self.min_width > self.max_width:
            raise ValueError("Minimum width cannot exceed maximum width.")

        if self.min_height > self.max_height:
            raise ValueError("Minimum height cannot exceed maximum height.")

        # Fixed area and height limits also restrict possible widths.
        feasible_min = max(self.min_width, self.area / self.max_height)

        feasible_max = min(self.max_width, self.area / self.min_height)

        if feasible_min > feasible_max + 1e-9:
            raise ValueError(f"Block {self.name} has no feasible dimensions.")

        if self.width is None:
            # Pick the midpoint of the feasible width range.
            self.width = (feasible_min + feasible_max) / 2
        else:
            self.set_width(self.width)

    @property
    def height(self):
        """Calculate height from the fixed area."""

        return self.area / self.width

    def set_width(self, new_width):
        """Change width while preserving area and dimension limits."""

        if not math.isfinite(new_width) or new_width <= 0:
            raise ValueError("Width must be a positive finite number.")

        new_height = self.area / new_width

        if not (self.min_width - 1e-9 <= new_width <= self.max_width + 1e-9):
            raise ValueError("New width is outside allowed limits.")

        if not (self.min_height - 1e-9 <= new_height <= self.max_height + 1e-9):
            raise ValueError("Resulting height is outside allowed limits.")

        self.width = float(new_width)

    def display(self):
        """Return a readable description of the block."""

        return (
            f"{self.name}: "
            f"Area={self.area}, "
            f"Width={self.width:.2f}, "
            f"Height={self.height:.2f}"
        )
