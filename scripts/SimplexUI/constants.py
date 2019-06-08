'''
Copyright 2016, Blur Studio

This file is part of Simplex.

Simplex is free software: you can redistribute it and/or modify
it under the terms of the GNU Lesser General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

Simplex is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU Lesser General Public License for more details.

You should have received a copy of the GNU Lesser General Public License
along with Simplex.  If not, see <http://www.gnu.org/licenses/>.
'''

from .Qt.QtCore import Qt

PRECISION = 4
COLUMNCOUNT = 3

THING_ROLE = Qt.UserRole + 1
VALUE_ROLE = Qt.UserRole + 2
WEIGHT_ROLE = Qt.UserRole + 3
TYPE_ROLE = Qt.UserRole + 4
PARENT_ROLE = Qt.UserRole + 5

THING_NAME_COL = 0
SLIDER_VALUE_COL = 1
SHAPE_WEIGHT_COL = 2

S_SHAPE_TYPE = 10
S_SLIDER_TYPE = 9
S_GROUP_TYPE = 8
S_SYSTEM_TYPE = 7

C_SHAPE_TYPE = 6
C_SHAPE_PAR_TYPE = 5
C_SLIDER_TYPE = 4
C_SLIDER_PAR_TYPE = 3
C_COMBO_TYPE = 2
C_GROUP_TYPE = 1
C_SYSTEM_TYPE = 0

