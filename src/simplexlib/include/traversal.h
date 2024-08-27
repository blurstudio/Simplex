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

#include "combo.h"
#include "shapeController.h"
#include "rapidjson/document.h"

#include <vector>
#include <string>

namespace simplex {

class Progression;
class Simplex;
class Slider;


class Traversal : public ShapeController {
	private:
		ComboPairs progStartState;
		ComboPairs progDeltaState;
		ComboPairs multState;
		ComboSolve solveType;
		bool exact;
	public:
		/*
		Traversal(const std::string &name, Progression* prog, size_t index,
				ShapeController* progressCtrl, ShapeController* multiplierCtrl, bool valueFlip, bool multiplierFlip):
			ShapeController(name, prog, index), progressCtrl(progressCtrl), multiplierCtrl(multiplierCtrl),
			valueFlip(valueFlip), multiplierFlip(multiplierFlip) {}
		*/

		Traversal(const std::string &name, Progression* prog, size_t index, ShapeController* progressCtrl, ShapeController* multiplierCtrl, bool valueFlip, bool multiplierFlip);
		Traversal(const std::string &name, Progression* prog, size_t index, const ComboPairs &startState, const ComboPairs &endState, ComboSolve solveType);

		void storeValue(
			const std::vector<double> &values,
			const std::vector<double> &posValues,
			const std::vector<double> &clamped,
			const std::vector<bool> &inverses);
		static bool parseJSONv1(const rapidjson::Value &val, size_t index, Simplex *simp);
		static bool parseJSONv2(const rapidjson::Value &val, size_t index, Simplex *simp);
		static bool parseJSONv3(const rapidjson::Value &val, size_t index, Simplex *simp);
};


}

