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
#include "shapeController.h"
#include "rapidjson/document.h"

#include <utility>
#include <vector>
#include <string>

namespace simplex {

class Progression;
class Slider;
class Simplex;

typedef std::pair<Slider*, double> ComboPair;
typedef std::vector<ComboPair> ComboPairs;

ComboSolve getSolveType(const rapidjson::Value &val);
bool getSolvePairs(const rapidjson::Value &val, Simplex *simp, ComboPairs &state, bool &isFloater);

bool solveState(const std::vector<double> &vals, const std::vector<double> &tars, ComboSolve solveType, bool exact, double &value);
bool solveState(const ComboPairs &stateList, ComboSolve solveType, bool exact, double &value);

class Combo : public ShapeController {
	private:
		bool isFloater;
		bool exact;
		ComboSolve solveType;
	protected:
		std::vector<bool> inverted;
		std::vector<double> rectified;
		std::vector<double> clamped;
	public:
		ComboPairs stateList;
		bool sliderType() const override { return false; }
		void setExact(bool e){exact = e;}
		Combo(const std::string &name, Progression* prog, size_t index,
			const ComboPairs &stateList, bool isFloater, ComboSolve solveType);
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
