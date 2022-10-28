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
#include <string>

namespace simplex {

class ShapeBase {
	protected:
		void *shapeRef; // pointer to whatever the user wants
		std::string name;
		size_t index;
	public:
		explicit ShapeBase(const std::string &name, size_t index): name(name), index(index), shapeRef(nullptr) {}
		explicit ShapeBase(const std::string &name): name(name), index(0u), shapeRef(nullptr) {}
		const std::string* getName() const {return &name;}
		const size_t getIndex() const { return index; }
		void setUserData(void *data) {shapeRef = data;}
		void* getUserData(){return shapeRef;}
};

}
