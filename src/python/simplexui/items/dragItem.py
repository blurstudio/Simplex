# Copyright 2016, Blur Studio
#
# This file is part of Simplex.
#
# Simplex is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Simplex is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with Simplex.  If not, see <http://www.gnu.org/licenses/>.

from __future__ import annotations


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
