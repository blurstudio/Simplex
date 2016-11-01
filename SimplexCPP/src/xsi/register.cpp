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

#include "simplex_xsi.h"

///////////////////////////////////////////////////////////////
// XSI LOAD / UNLOAD PLUGIN
///////////////////////////////////////////////////////////////
XSIPLUGINCALLBACK XSI::CStatus XSILoadPlugin( XSI::PluginRegistrar& in_reg )
{
   in_reg.PutAuthor(L"Tyler Fox");
   in_reg.PutName(L"Simplex Solver");
   in_reg.PutEmail(L"beta@blur.com");
   in_reg.PutURL(L"http://www.blur.com");
   in_reg.PutVersion(1,0);

   // register all of the solvers
   in_reg.RegisterOperator(L"simplex2CPP");
   return XSI::CStatus::OK;
}

XSIPLUGINCALLBACK XSI::CStatus XSIUnloadPlugin( const XSI::PluginRegistrar& in_reg )
{
   XSI::CString strPluginName;
   strPluginName = in_reg.GetName();
   XSI::Application().LogMessage(strPluginName + L" has been unloaded.", XSI::siVerboseMsg);
   return XSI::CStatus::OK;
}

