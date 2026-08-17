class Draggable:
    """A mixin to make an item middle-click draggable"""

    # This is in a separate file from the DragFilter so that no Qt imports
    # are required for the core Simplex items
    dragStep: float = 0.05
    maxValue: float = 1.0
    minValue: float = 0.0

    def valueTick(self, ticks: int, mul: float):
        """Change the value of the current object by some number of ticks
        with some given multiplier. This is the interface for the MMB drag

        Parameters
        ----------
        ticks : int
            The number of dragStep ticks to apply
        mul : float
            An overall multiplier
        """
        val = self.value + (self.dragStep * ticks * mul)
        val = 0.0 if abs(val) < 1e-5 else val
        val = max(min(val, self.maxValue), self.minValue)
        self.value = val
