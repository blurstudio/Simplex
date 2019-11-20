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
#include "trispace.h"
#include "floater.h"
#include "simplex.h"
#include "slider.h"
#include "utils.h"

#include "math.h"
#include "Eigen/Dense"

#include <algorithm>      // for all_of, sort
#include <numeric>        // for accumulate
#include <utility>
#include <unordered_map>
#include <vector>

using namespace simplex;

// Check if the stateList of one floater is equal to another
bool stateEq(
		std::vector<std::pair<Slider*, double>> lhs,
		std::vector<std::pair<Slider*, double>> rhs
){
	for (size_t i=0; i<lhs.size(); ++i){
		// pointers compare equal if they point to the same object
		if (lhs[i].first != rhs[i].first) return false;
	}
	return true;
}

std::vector<TriSpace> TriSpace::buildSpaces(std::vector<Floater> &floaters){
	// group floaters by subspace dimension span
	std::vector<std::vector<Floater*>> dimmed;
	for (auto fit = floaters.begin(); fit!=floaters.end(); ++fit){
		//for (auto &floater : floaters){
		auto &floater = *fit;
		size_t sls = floater.stateList.size();
		if (sls >= dimmed.size()) dimmed.resize(sls+1);
		dimmed[sls].push_back(&floater);
	}

	// Go through each dimension group and separate them by shared
	// sliders and directions
	std::vector<TriSpace> spaces;
	for ( auto dit = dimmed.begin(); dit != dimmed.end(); ++dit){
		//for (auto &dim : dimmed){
		auto &dim = *dit;
		std::vector<Floater*> bucket;
		std::vector<bool> used(dim.size());
		for (size_t i=0; i<dim.size(); ++i){
			if (used[i]) continue;
			used[i] = true;
			bucket.clear();
			bucket.push_back(dim[i]);

			for (size_t j=i+1; j<dim.size(); ++j){
				if (used[j]) continue;
				if (stateEq(dim[i]->stateList, dim[j]->stateList)){
					used[j] = true;
					bucket.push_back(dim[j]);
				}
			}
			spaces.push_back(TriSpace(bucket));
		}
	}
	return spaces;
}

TriSpace::TriSpace(std::vector<Floater*> floaters):floaters(floaters){
	triangulate();
}

void TriSpace::triangulate(){
	std::unordered_map<
		std::vector<int>,
		std::vector<std::vector<double>>,
		vectorHash<int>
	> d;

	for ( auto fit = floaters.begin(); fit != floaters.end(); ++fit){
		//for (auto f : floaters){
		auto &f = *fit;
		std::vector<double> userPoint;
		for (auto sit = f->stateList.begin(); sit != f->stateList.end(); ++sit){
			//for (auto sp : stateList){
			auto &sp = *sit;
			userPoint.push_back(sp.second);
		}
		userPoints.push_back(userPoint);
		std::vector<std::vector<int>> rawSimps = pointToAdjSimp(userPoint);
		for ( auto rit = rawSimps.begin(); rit != rawSimps.end(); ++rit){
			//for (auto &rawSimp : rawSimps){
			auto &rawSimp = *rit;
			d[rawSimp].push_back(userPoint);
		}
	}

	for (auto pit = d.begin(); pit != d.end(); ++pit){
		//for (auto p : d){
		auto p = *pit;
		overrideSimplices.push_back(p.first);
		std::vector<std::vector<int>> singleSimp;
		singleSimp.push_back(p.first);
		auto ext = splitSimps(p.second, singleSimp);
		for (auto uit = ext.begin(); uit != ext.end(); ++uit){
			//for (auto &userSimplex : ext){
			auto &userSimplex = *uit;
			std::vector<int> newSimp;
			for (size_t cIdx=0; cIdx<userSimplex.size(); ++cIdx){
				auto findIt = std::find(userPoints.begin(), userPoints.end(), userSimplex[cIdx]);
				if (findIt == userPoints.end()){ // not found
					newSimp.push_back(p.first[cIdx]);
				}
				else{
					size_t idx = findIt - userPoints.begin();
					newSimp.push_back(int(p.first.size() + idx));
				}
			}
			simplexMap[p.first].push_back(newSimp);
		}
	}
}

void TriSpace::storeValue(
		const std::vector<double> &values,
		const std::vector<double> &posValues,
		const std::vector<double> &clamped,
		const std::vector<bool> &inverses
){
	std::vector<bool> subInverse;
	std::vector<double> vec;
	// All floats in a trispace share the same span
	// so I only need to check one of them
	for (auto pit = floaters[0]->stateList.begin(); pit != floaters[0]->stateList.end(); ++pit){
		//for (auto &p : floaters[0]->stateList) {
		auto &p = *pit;
		size_t idx = p.first->getIndex();
		subInverse.push_back(inverses[idx]);
		double cval = clamped[idx];
		if (isZero(cval)) return;
		vec.push_back(cval);
	}
	if (floaters[0]->inverted != subInverse) return;

	std::vector<int> majorSimp = pointToSimp(vec);
	size_t c = simplexMap.count(majorSimp);
	if (c == 0) return;

	std::vector<std::vector<int>> &simps = simplexMap[majorSimp];


	for (auto sit = simps.begin(); sit != simps.end(); ++sit){
		//for (auto &simp : simps){
		auto &simp = *sit;
		std::vector<std::vector<double>> expanded;
		std::vector<int> floaterCorners;
		// TODO: Didn't fill "expanded" properly
		userSimplexToCorners(simp, majorSimp, expanded, floaterCorners);

		std::vector<double> b = barycentric(expanded, vec);
		if (std::all_of(b.begin(), b.end(), isPositive)){
			for (size_t i = 0; i < b.size(); ++i) {
				int fcIdx = floaterCorners[i];
				if (fcIdx != -1) {
					floaters[fcIdx]->value = b[i];
				}
			}
			break;
		}
	}
}

std::vector<std::vector<int>> TriSpace::pointToAdjSimp(
		const std::vector<double> &pt,
		double eps
) {
	//Search for simplices that are near the point
	//This allows for splitting the simplex, or snapping a
	//point to a nearby progression

	// Point, OrderedValues, CurrentSimplex, Output

	std::vector<std::vector<int> > out;
	std::vector<int> rn, simp;
	rn.resize(pt.size());
	for (int i=0; i<pt.size(); ++i){
		rn[i] = i;
	}
	simp.push_back(0);
	TriSpace::rec(pt, rn, simp, out, eps);
	return out;
}

void TriSpace::rec(
		const std::vector<double> &point,
		const std::vector<int> &oVals,
		const std::vector<int> &simp,
		std::vector<std::vector<int> > &out,
		double eps
) const {
	if (point.empty()){
		out.push_back(simp);
		return;
	}

	double maxabs = fabs(point[0]);
	for (size_t i=0; i<point.size(); ++i){
		double aa = fabs(point[i]);
		if (aa > maxabs){
			maxabs = aa;
		}
	}

	std::vector<size_t> mxs;
	for (size_t i=0; i<point.size(); ++i){
		if (maxabs - fabs(point[i]) < eps){
			mxs.push_back(i);
		}
	}

	std::vector<double> subpoint;
	std::vector<int> subvals, nSimp;
	bool mvZero = isZero(maxabs);

	for (size_t i=0; i<mxs.size(); ++i){
		std::vector<int> searchDirection;
		// zero is both positive and negative
		// so I need to do both directions
		size_t mx = mxs[i];
		if (mvZero){
			searchDirection.push_back(-1); 
			searchDirection.push_back(1); 
		}
		else {
			int p = (isPositive(point[mx])) ? 1 : -1;
			searchDirection.push_back(p);
		}

		//for (int direction : searchDirection){
		for (auto dit = searchDirection.begin(); dit != searchDirection.end(); ++dit) {
			int direction = *dit;
			int newval = (oVals[mx] + 1) * direction;

			// Copy
			nSimp = simp;
			subpoint = point;
			subvals = oVals;

			nSimp.insert(nSimp.end(), newval);
			subpoint.erase(subpoint.begin()+mx);
			subvals.erase(subvals.begin()+mx);
			TriSpace::rec(subpoint, subvals, nSimp, out, eps);
		}
	}
}

std::vector<std::vector<double> > TriSpace::simplexToCorners(
		const std::vector<int> &simplex
) const {
	std::vector<double> currVec(simplex.size() - 1, 0.0);
	std::vector<std::vector<double> > out;
	for (size_t i = 0; i<simplex.size(); ++i) {
		int s = simplex[i];
		if (s == 0) {
			out.push_back(currVec);
			continue;
		}
		int idx = (s > 0) ? s : -s;
		double val = (s > 0) ? 1.0 : -1.0;

		if (idx >= simplex.size()) {
			idx = idx - int(simplex.size());
			out.push_back(this->userPoints[idx]);
		}
		else {
			currVec[idx - 1] = val;
			out.push_back(currVec);
		}
	}
	return out;
}

std::vector<std::vector<std::vector<double> > > TriSpace::splitSimps(
		const std::vector<std::vector<double> > &pts,
		const std::vector<std::vector<int> > &simps
) const {
	std::vector<std::vector<std::vector<double> > > out, tmpList;
	for (size_t i = 0; i<simps.size(); ++i) {
		out.push_back(simplexToCorners(simps[i]));
	}

	for (size_t i = 0; i<pts.size(); ++i) {
		const std::vector<double> &p = pts[i];
		tmpList.clear();
		for (size_t j = 0; j<out.size(); ++j) {
			std::vector<double> bary = barycentric(out[j], p);
			if (std::all_of(bary.begin(), bary.end(), isPositive)) {
				for (size_t k = 0; k<bary.size(); ++k) {
					double b = bary[k];
					if (!isZero(b)) {
						std::vector<std::vector<double>> ns = out[j];
						ns[k] = p;
						tmpList.push_back(std::move(ns));
					}
				}
			}
			else {
				tmpList.push_back(out[j]);
			}
		}
		out = tmpList;
	}
	return out;
}

std::vector<double> TriSpace::barycentric(
		const std::vector<std::vector<double>> &simplex,
		const std::vector<double> &p
) const {

	std::vector<double> last = simplex.back();

	// lastVec = (p - last)
	Eigen::VectorXd lastVec(p.size());
	for (size_t i=0; i<last.size(); ++i){
		lastVec(i) = p[i] - last[i];
	}

	// M = (s - last)[:-1].transpose()
	Eigen::MatrixXd M(simplex.size()-1, simplex.size()-1);
	for (size_t i=0; i<simplex.size()-1; ++i){ // [:-1]
		for (size_t j=0; j<simplex[i].size(); ++j){
			// transpose // ji = ij
			M(j,i) = simplex[i][j] - last[j];
		}
	}

	// solve for the coordinates
	Eigen::VectorXd x = M.colPivHouseholderQr().solve(lastVec);
	double * outArray = x.data(); // x.data isn't a vector, so convert it
	std::vector<double> out(&outArray[0],&outArray[p.size()]);
	double sum = accumulate(out.begin(), out.end(), 0.0);
	out.push_back(1.0 - sum); // 1-sum = missing value
	return out;
}

std::vector<int> TriSpace::pointToSimp(const std::vector<double> &pt) {
	/*
		Each simplex can be represented as a permutation of [(+-)(i+1) for i in range(len(dim))]
		So I will encode these values by the pos/neg direction along a dimension number.
		We always start at 0, so that makes [0,-2,4,1,-3] a valid encoding

		The resultant simplex is called a "Schlafli Orthoscheme"
	*/
	std::vector<std::pair<int, double> > abspt;
	double v;
	int idx, i, n;
	for (i=0; i<pt.size(); ++i){
		v = pt[i];
		idx = i+1;
		n = !isPositive(v) ? -1 : 1;
		abspt.push_back(std::make_pair(idx*n, v*n));
	}
	std::sort(abspt.begin(), abspt.end(),
		[](const std::pair<int, double> &a, const std::pair<int, double> &b) {
			return a.second < b.second;
		}
	);

	std::vector<int> out;
	out.push_back(0);
	for (i=int(abspt.size()); i>0; --i){
		out.push_back(abspt[i-1].first);
	}
	return out;
}

void TriSpace::userSimplexToCorners(
		const std::vector<int> &simplex,
		const std::vector<int> &original,
		std::vector<std::vector<double>> &out,
		std::vector<int> &floaterCorners // TODO
		) const{ 

	std::vector<double> currVec (simplex.size()-1, 0.0);
	for (size_t i=0; i<simplex.size(); ++i){
		int s = simplex[i];
		int os = original[i];
		if (s == 0){
			out.push_back(currVec);
			floaterCorners.push_back(-1);
			continue;
		}
		// get the user idx
		int idx = (s > 0)? s : -s;

		// get the original idx
		int oidx = (os > 0)? os : -os;
		double val = (os > 0)? 1.0 : -1.0;

		if (oidx != 0){	
			// keep track of where we *would* be normally
			// unless we're replacing the first item
			currVec[oidx-1] = val;
		}

		// if the user idx is too high
		if (idx >= simplex.size()){
			// grab a user point
			idx = idx - int(simplex.size());
			out.push_back(this->userPoints[idx]);
			floaterCorners.push_back(idx);
		}
		else {
			// get the currVec		
			out.push_back(currVec);
			floaterCorners.push_back(-1);
		}
	}
}

