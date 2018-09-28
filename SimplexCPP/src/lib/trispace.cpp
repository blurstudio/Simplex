/*
class TriSpace {
	private:
		// Correlates the auto-generated simplex with the user-created simplices
		// resulting from the splitting procedure
		std::vector<std::pair<std::vector<int>, std::vector<std::vector<int>>>> simplexMap;
	
		std::vector<Floater *> floaters;
		static std::vector<double> barycentric(const std::vector<std::vector<double>> &simplex, const std::vector<double> &p);
		static std::vector<std::vector<double>> simplexToCorners(const std::vector<int> &simplex);
		static std::vector<int> pointToSimp(const std::vector<double> &pt);
		static std::vector<std::vector<int>> pointToAdjSimp(const std::vector<double> &pt, double eps);
		void triangulate(); // convenience function for separating the data access from the actual math
		// Code to split a list of simplices by a list of points, only used in triangulate()
		std::vector<std::vector<std::vector<double>>> splitSimps(const std::vector<std::vector<double>> &pts, const std::vector<std::vector<int>> &simps) const;

		// break down the given simplex encoding to a list of corner points for the barycentric solver and
		// a correlation of the point index to the floater index (or size_t_MAX if invalid)
		void userSimplexToCorners(
				const std::vector<int> &simplex,
				const std::vector<int> &original,
				std::vector<std::vector<double>> out,
				std::vector<size_t> floaterCorners
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
*/



#include "simplex.h"

using namespace simplex;

// Check if the stateList of one floater is equal to another
bool stateEq(std::vector<std::pair<Slider*, double>> lhs, std::vector<std::pair<Slider*, double>> rhs){
	for (size_t i=0;, i<lhs.size(); ++i){
		// pointers compare equal if they point to the same object
		if (lhs[i].first != rhs[i].first) return false;
	}
	return true;
}

std::vector<TriSpace> TriSpace::buildSpaces(std::vector<Floater> &floaters){
	// group floaters by subspace dimension span
	std::vector<std::vector<*Floater>> dimmed;
	for (auto &floater : floaters){
		size_t sls = floater.stateList.size();
		if (sls > dimmed.size()) dimmed.resize(sls);
		dimmed[sls].push_back(&floater);
	}

	// Go through each dimension group and separate them by shared
	// sliders and directions
	std::vector<TriSpace> spaces;
	for (auto &dim : dimmed){
		std::vector<*Floater> bucket;
		std::vector<bool> used(dim.size());
		for (size_t i=0; i<dim.size(); ++i){
			if (used[i]) continue;
			used[i] = true;
			bucket.clear();
			bucket.push_back(dim[i]);

			for (size_t j=i+1; j<dim.size(); ++j){
				if (used[j]) continue;
				if (stateEq(dim[i], dim[j])){
					dim[j] = true;
					bucket.push_back(dim[j]);
				}
			}
			spaces.push_back(TriSpace(bucket));
		}
	}
	return spaces;
}













