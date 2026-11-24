
from dataclasses import dataclass
import math


@dataclass
class Block:
    """
    Represents a VLSI block with fixed area and bounded dimensions.
    Width is the independent shaping variable; height = area / width.
    """

    name: str
    area: float
    min_width: float
    max_width: float
    min_height: float
    max_height: float
    width: float = None

    def __post_init__(self):
        self.area = float(self.area)
        self.min_width = float(self.min_width)
        self.max_width = float(self.max_width)
        self.min_height = float(self.min_height)
        self.max_height = float(self.max_height)

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

        if min(
            self.min_width,
            self.max_width,
            self.min_height,
            self.max_height,
        ) <= 0:
            raise ValueError("Dimension limits must be positive.")

        if self.min_width > self.max_width:
            raise ValueError("Minimum width cannot exceed maximum width.")

        if self.min_height > self.max_height:
            raise ValueError("Minimum height cannot exceed maximum height.")

        if self.effective_min_width > self.effective_max_width + 1e-9:
            raise ValueError(
                f"Block {self.name} has no feasible dimensions."
            )

        if self.width is None:
            self.width = (
                self.effective_min_width + self.effective_max_width
            ) / 2
        else:
            self.set_width(self.width)

    @property
    def effective_min_width(self):
        return max(
            self.min_width,
            self.area / self.max_height
        )

    @property
    def effective_max_width(self):
        return min(
            self.max_width,
            self.area / self.min_height
        )

    @property
    def effective_min_height(self):
        return self.area / self.effective_max_width

    @property
    def effective_max_height(self):
        return self.area / self.effective_min_width

    @property
    def height(self):
        return self.area / self.width

    def set_width(self, new_width):
        """Change width while preserving area and dimension limits."""

        try:
            new_width = float(new_width)
        except (TypeError, ValueError):
            raise ValueError("Width must be numeric.")

        if not math.isfinite(new_width) or new_width <= 0:
            raise ValueError(
                "Width must be a positive finite number."
            )

        new_height = self.area / new_width

        if not (
            self.effective_min_width - 1e-9
            <= new_width
            <= self.effective_max_width + 1e-9
        ):
            raise ValueError(
                "New width is outside feasible width limits."
            )

        if not (
            self.effective_min_height - 1e-9
            <= new_height
            <= self.effective_max_height + 1e-9
        ):
            raise ValueError(
                "Resulting height is outside feasible height limits."
            )

        self.width = new_width

    def display(self):
        return (
            f"{self.name}: "
            f"Area={self.area}, "
            f"Width={self.width:.2f}, "
            f"Height={self.height:.2f}"
        )
