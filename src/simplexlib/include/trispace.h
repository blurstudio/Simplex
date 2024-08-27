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
#include "utils.h"
#include <vector>
#include <unordered_map>

namespace simplex {

class Floater;

class TriSpace {
	private:
		// Correlates the auto-generated simplex with the user-created simplices
		// resulting from the splitting procedure
		std::unordered_map<std::vector<int>, std::vector<std::vector<int>>, vectorHash<int>> simplexMap;
		std::vector<std::vector<double>> userPoints;
		std::vector<std::vector<int>> overrideSimplices;

		std::vector<Floater *> floaters;
		std::vector<double> barycentric(const std::vector<std::vector<double>> &simplex, const std::vector<double> &p) const;
		//static std::vector<std::vector<double>> simplexToCorners(const std::vector<int> &simplex);
		std::vector<int> pointToSimp(const std::vector<double> &pt);
		std::vector<std::vector<int>> pointToAdjSimp(const std::vector<double> &pt, double eps=0.01);
		void triangulate(); // convenience function for separating the data access from the actual math
		// Code to split a list of simplices by a list of points, only used in triangulate()
		std::vector<std::vector<std::vector<double>>> splitSimps(const std::vector<std::vector<double>> &pts, const std::vector<std::vector<int>> &simps) const;
		std::vector<std::vector<double> > simplexToCorners(const std::vector<int> &simplex) const;
		void rec(const std::vector<double> &point, const std::vector<int> &oVals, const std::vector<int> &simp, std::vector<std::vector<int> > &out, double eps) const;

		// break down the given simplex encoding to a list of corner points for the barycentric solver and
		// a correlation of the point index to the floater index (or size_t_MAX if invalid)
		void userSimplexToCorners(
				const std::vector<int> &simplex,
				const std::vector<int> &original,
				std::vector<std::vector<double>> &out,
				std::vector<int> &floaterCorners
				) const;

	public:
		// Take the non-related floaters and group them by shared span and orthant
		static std::vector<TriSpace> buildSpaces(std::vector<Floater> &floaters);
		TriSpace(std::vector<Floater*> floaters);
		void storeValue(
				const std::vector<double> &values,
				const std::vector<double> &posValues,
				const std::vector<double> &clamped,
				const std::vector<bool> &inverses);
};


}
