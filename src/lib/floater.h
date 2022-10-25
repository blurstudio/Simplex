/*
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
*/

#pragma once

#include "enums.h"
#include "combo.h"

#include <utility>
#include <vector>
#include <string>

namespace simplex {

class Slider;
class Floater : public Combo {
	public:
		friend class TriSpace; // lets the trispace set the value for this guy
		Floater(const std::string &name, Progression* prog, size_t index,
			const std::vector<std::pair<Slider*, double>> &stateList, bool isFloater) :
			Combo(name, prog, index, stateList, isFloater, ComboSolve::None) {
		}
};


}

