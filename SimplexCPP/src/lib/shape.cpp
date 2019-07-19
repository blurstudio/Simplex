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
#include "simplex.h"
#include "shape.h"

#include "rapidjson/document.h"

#include <vector>
#include <string>

using namespace simplex;

bool Shape::parseJSONv1(const rapidjson::Value &val, size_t index, Simplex *simp){
	if(!val.IsString()) return false;
	std::string name(val.GetString());
	simp->shapes.push_back(Shape(name, index));
	return true;
}

bool Shape::parseJSONv2(const rapidjson::Value &val, size_t index, Simplex *simp){
	if (!val.IsObject()) return false;

	CHECK_JSON_STRING(nameIt, "name", val);

	std::string name(nameIt->value.GetString());
	simp->shapes.push_back(Shape(name, index));
	return true;
}

bool Shape::parseJSONv3(const rapidjson::Value &val, size_t index, Simplex *simp){
	return parseJSONv2(val, index, simp);
}

