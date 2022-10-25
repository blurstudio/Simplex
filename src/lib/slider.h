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

#include "shapeController.h"
#include "rapidjson/document.h"

#include <vector>
#include <string>

namespace simplex {

class Simplex;
class Progression;

class Slider : public ShapeController {
	public:
		Slider(const std::string &name, Progression* prog, size_t index) : ShapeController(name, prog, index){}
		void storeValue(
				const std::vector<double> &values,
				const std::vector<double> &posValues,
				const std::vector<double> &clamped,
				const std::vector<bool> &inverses){
			if (!enabled) return;
			this->value = values[this->index];
		}

		static bool parseJSONv1(const rapidjson::Value &val, size_t index, Simplex *simp);
		static bool parseJSONv2(const rapidjson::Value &val, size_t index, Simplex *simp);
		static bool parseJSONv3(const rapidjson::Value &val, size_t index, Simplex *simp);
};

}

