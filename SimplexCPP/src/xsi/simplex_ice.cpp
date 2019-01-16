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

#include "simplex_ice.h"

using namespace XSI; 
using namespace simplex;




// Defines port, group and map identifiers used for registering the ICENode
enum IDs{
	ID_IN_Revision = 0,
	ID_IN_Definition = 1,
	ID_IN_Sliders = 2,
	ID_G_100 = 100,
	ID_OUT_Weights = 200,
	ID_TYPE_CNS = 400,
	ID_STRUCT_CNS,
	ID_CTXT_CNS,
	ID_UNDEF = ULONG_MAX
};

CStatus RegisterSimplexNode( PluginRegistrar& in_reg );

class Simplex_XSI {
public:
	simplex::Simplex mysimplex;
	std::string storedDefinition;

	void updateDef(const std::string check){
		// The *EXPECTED* result of this string comparison is equality
		// so adding extra tests to rule out equality early is a bad thing
		if (this->storedDefinition != check) {
			this->mysimplex.clear();
			this->mysimplex.parseJSON(check);
			this->mysimplex.build();
		}			
	}
	
	const std::vector<double> computeProgShapeValues(const std::vector<double> &invec) {
		return this->mysimplex.solve(invec);
	}
};



SICALLBACK XSILoadPlugin( PluginRegistrar& in_reg ){
	in_reg.PutAuthor(L"tyler");
	in_reg.PutName(L"SimplexNode Plugin");
	in_reg.PutVersion(1,1);

	RegisterSimplexNode( in_reg );

	//RegistrationInsertionPoint - do not remove this line

	return CStatus::OK;
}

SICALLBACK XSIUnloadPlugin( const PluginRegistrar& in_reg ){
	CString strPluginName;
	strPluginName = in_reg.GetName();
	Application().LogMessage(strPluginName + L" has been unloaded.",siVerboseMsg);
	return CStatus::OK;
}

CStatus RegisterSimplexNode( PluginRegistrar& in_reg ){
	ICENodeDef nodeDef;
	nodeDef = Application().GetFactory().CreateICENodeDef(L"SimplexNode",L"SimplexNode");

	CStatus st;
	st = nodeDef.PutColor(154,188,102);
	st.AssertSucceeded( ) ;

	st = nodeDef.PutThreadingModel(XSI::siICENodeSingleThreading);
	st.AssertSucceeded( ) ;

	// Add input ports and groups.
	st = nodeDef.AddPortGroup(ID_G_100);
	st.AssertSucceeded( ) ;

    // The revision number, for counting updates
	st = nodeDef.AddInputPort(ID_IN_Revision,
		ID_G_100,
		siICENodeDataLong,
		siICENodeStructureSingle,
		siICENodeContextSingleton,
		L"Revision",
		L"Revision",
		0,
		CValue(),
		CValue(),
		ID_UNDEF,
		ID_UNDEF,
		ID_CTXT_CNS);
	st.AssertSucceeded();

    // String definition
	st = nodeDef.AddInputPort(ID_IN_Definition,
        ID_G_100,
        siICENodeDataString,
        siICENodeStructureSingle,
        siICENodeContextSingleton,
        L"Definition",
        L"Definition",
        L"Default String",
        CValue(),
        CValue(),
        ID_UNDEF,
        ID_UNDEF,
        ID_CTXT_CNS);
	st.AssertSucceeded();

    // input slider vector
	st = nodeDef.AddInputPort(ID_IN_Sliders,
        ID_G_100,
        siICENodeDataFloat,
        siICENodeStructureArray,
        siICENodeContextSingleton,
        L"Sliders",
        L"Sliders",
        0,
        CValue(),
        CValue(),
        ID_UNDEF,
        ID_UNDEF,
        ID_CTXT_CNS);
	st.AssertSucceeded();



	// Add output ports.
	st = nodeDef.AddOutputPort(ID_OUT_Weights,
        siICENodeDataFloat,
        siICENodeStructureArray,
        siICENodeContextSingleton,
        L"Weights",
        L"Weights",
        ID_UNDEF,
        ID_UNDEF,
        ID_CTXT_CNS);
	st.AssertSucceeded( ) ;

	PluginItem nodeItem = in_reg.RegisterICENode(nodeDef);
	nodeItem.PutCategories(L"Custom ICENode");

	return CStatus::OK;
}


SICALLBACK SimplexNode_Evaluate( ICENodeContext& in_ctxt ){
	// The current output port being evaluated...
	ULONG out_portID = in_ctxt.GetEvaluatedOutputPortID( );
  
	switch( out_portID ){		
		case ID_OUT_Weights :
		{
			Simplex_XSI* simp = (Simplex_XSI*)(CValue::siPtrType)in_ctxt.GetUserData();

			CDataArrayLong RevisionData(in_ctxt, ID_IN_Revision);

			// Note: Specific CIndexSet for Definition is required in single-threading mode		
			CDataArrayString DefinitionData(in_ctxt, ID_IN_Definition);
			if (DefinitionData.GetCount() == 0)
                return CStatus::OK;
			//CIndexSet DefinitionIndexSet( in_ctxt, ID_IN_Definition );
			std::string definition(DefinitionData[0].GetAsciiString());
			simp->mysimplex.clear();
			simp->updateDef(definition);
			bool exact = false;
			simp->mysimplex.setExactSolve(exact);

			// Note: Specific CIndexSet for Sliders is required in single-threading mode
			CDataArray2DFloat SlidersData(in_ctxt, ID_IN_Sliders);
			//CIndexSet SlidersIndexSet( in_ctxt, ID_IN_Sliders );

			if (SlidersData.GetCount() == 0)
                return CStatus::OK;
			CDataArray2DFloat::Accessor SlidersSubArray = SlidersData[0];
			ULONG ct = SlidersSubArray.GetCount();

			if (ct == 0)
                return CStatus::OK;
			std::vector<double> inVec(ct, 0.0f);
			for (ULONG i = 0; i < ct; i++){
				inVec[i] = SlidersSubArray[i];
			}

			inVec.resize(simp->mysimplex.sliderLen());
			std::vector<double> outVec;
			outVec = simp->computeProgShapeValues(inVec);
						
			// Get the output port array ...			
			CDataArray2DFloat outData(in_ctxt);
			CDataArray2DFloat::Accessor outAcc = outData.Resize(0, outVec.size());
			for (ULONG i = 0; i<outVec.size(); i++){
				outAcc[i] = outVec[i];
			}		
		}
		break;
	}
	
	return CStatus::OK;
}

SICALLBACK SimplexNode_Init( CRef& in_ctxt ){
	Context ctxt = in_ctxt;

	Simplex_XSI* simp = new Simplex_XSI();
	ctxt.PutUserData((CValue::siPtrType)simp);
	
	return CStatus::OK;
}


SICALLBACK SimplexNode_Term( CRef& in_ctxt ){
	Context ctxt = in_ctxt;
	CValue userData = ctxt.GetUserData();
	if (userData.IsEmpty()) {
		return CStatus::OK;
	}

	Simplex_XSI* simp = (Simplex_XSI*)(CValue::siPtrType)ctxt.GetUserData();
	if (simp) {
		delete simp;
	}
	ctxt.PutUserData(CValue());
	
	return CStatus::OK;
}

