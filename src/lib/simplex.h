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

#include "shape.h"
#include "progression.h"
#include "slider.h"
#include "combo.h"
#include "floater.h"
#include "trispace.h"
#include "traversal.h"

#include "rapidjson/document.h"

#include <vector>
#include <string>

namespace simplex {

class Simplex {
	private:
		bool exactSolve;
	public:
		std::vector<Shape> shapes;
		std::vector<Progression> progs;
		std::vector<Slider> sliders;
		std::vector<Combo> combos;
		std::vector<Floater> floaters;
		std::vector<TriSpace> spaces;
		std::vector<Traversal> traversals;

		bool built;
		bool loaded;
		bool hasParseError;

		std::string parseError;
		size_t parseErrorOffset;
		const size_t sliderLen() const { return sliders.size(); }

		Simplex():exactSolve(true), built(false), loaded(false), hasParseError(false) {};
		explicit Simplex(const std::string &json);
		explicit Simplex(const char* json);

		void clearValues();
		void clear();
		bool parseJSON(const std::string &json);
		bool parseJSONversion(const rapidjson::Document &d, unsigned version);
		void build();

		void setExactSolve(bool exact);
		bool getExactSolve() { return exactSolve; }

		std::vector<double> solve(const std::vector<double> &vec);
};

} // end namespace simplex
