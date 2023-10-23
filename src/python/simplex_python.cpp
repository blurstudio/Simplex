#include <Python.h>
#include <structmember.h>

#include "simplex.h"
#include <string>
#include <codecvt>
#include <vector>
#include <locale>

typedef struct {
    PyObject_HEAD // No Semicolon for this Macro;
    PyObject *definition;
    simplex::Simplex *sPointer;
} PySimplex;

static void
PySimplex_dealloc(PySimplex* self) {
    Py_XDECREF(self->definition);
    if (self->sPointer != NULL)
		delete self->sPointer;
    PyObject_Del(self);
}

static PyObject *
PySimplex_new(PyTypeObject *type, PyObject *args, PyObject *kwds) {

    PySimplex *self = PyObject_New(PySimplex, type);
    if (self != NULL) {
        self->definition = PyUnicode_FromString("");
        if (self->definition == NULL) {
            Py_DECREF(self);
            return NULL;
        }
        self->sPointer = new simplex::Simplex();
    }

    return (PyObject *)self;
}

static PyObject *
PySimplex_getdefinition(PySimplex* self, void* closure){
    Py_INCREF(self->definition);
    return self->definition;
}

static int
PySimplex_setdefinition(PySimplex* self, PyObject* jsValue, void* closure){
    if (jsValue == NULL || jsValue == Py_None){
        jsValue = PyUnicode_FromString("");
    }

    if (! PyUnicode_Check(jsValue)) {
        PyErr_SetString(PyExc_TypeError, "The simplex definition must be a string");
        return -1;
    }

    PyObject *tmp = self->definition;
    Py_INCREF(jsValue);
    self->definition = jsValue;
    Py_DECREF(tmp);

    // Get the unicode as a wstring, and a wstring to string converter
    std::wstring simDefw = std::wstring(PyUnicode_AsWideCharString(self->definition, NULL));
    std::wstring_convert<std::codecvt_utf8<wchar_t>> myconv;
    std::string simDef = myconv.to_bytes(simDefw);

    // set the definition in the solver
    self->sPointer->clear();
    self->sPointer->parseJSON(simDef);
    self->sPointer->build();

    return 0;
}

static PyObject *
PySimplex_getexactsolve(PySimplex* self, void* closure){
    if (self->sPointer->getExactSolve()){
        Py_RETURN_TRUE;
    }
    Py_RETURN_FALSE;
}

static int
PySimplex_setexactsolve(PySimplex* self, PyObject* exact, void* closure){
    int truthy = PyObject_IsTrue(exact);
    if (truthy == -1){
        PyErr_SetString(PyExc_TypeError, "The value passed cannot be cast to boolean");
        return -1;
    }

    self->sPointer->setExactSolve((truthy == 1));
    return 0;
}

static int
PySimplex_init(PySimplex *self, PyObject *args, PyObject *kwds) {
    PyObject *jsValue=NULL, *tmp=NULL;

    char jsValueLiteral[] = "jsValue";
    static char *kwlist[] = {jsValueLiteral, NULL};

    if (! PyArg_ParseTupleAndKeywords(args, kwds, "|O", kwlist, &jsValue))
        return -1;

    return PySimplex_setdefinition(self, jsValue, NULL);
}

static PyObject *
PySimplex_solve(PySimplex* self, PyObject* vec){
    if (! PySequence_Check(vec)){
        PyErr_SetString(PyExc_TypeError, "Input must be a list or tuple");
        return NULL;
    }

    PyObject *item;
    std::vector<double> stdVec, outVec;
    for (Py_ssize_t i=0; i<PySequence_Size(vec); ++i){
        item = PySequence_GetItem(vec, i);
        if (! PyNumber_Check(item)) {
            PyErr_SetString(PyExc_TypeError, "Input list can contain only numbers");
            return NULL;
        }
        stdVec.push_back(PyFloat_AsDouble(PyNumber_Float(item)));
        Py_DECREF(item);
    }

	self->sPointer->clearValues();
    outVec = self->sPointer->solve(stdVec);

    PyObject *out = PyList_New(outVec.size());
    for (size_t i=0; i<outVec.size(); ++i){
        PyList_SetItem(out, i, PyFloat_FromDouble(outVec[i]));
    }
    return out;
}

static PyGetSetDef PySimplex_getseters[] = {
    {(char*)"definition",
     (getter)PySimplex_getdefinition, (setter)PySimplex_setdefinition,
     (char*)"Simplex structure definition string",
     NULL},

    {(char*)"exactSolve",
     (getter)PySimplex_getexactsolve, (setter)PySimplex_setexactsolve,
     (char*)"Run the solve with the exact min() solver",
     NULL},
    {NULL}  // Sentinel
};

static PyMethodDef PySimplex_methods[] = {
    {(char*)"solve", (PyCFunction)PySimplex_solve, METH_O,
     (char*)"Supply an input list to the solver, and recieve and output list"
    },
    {NULL}  // Sentinel
};



static PyType_Slot PySimplexType_Slots[] = {
    {Py_tp_methods, PySimplex_methods},
    {Py_tp_getset, PySimplex_getseters},
    {Py_tp_init, (initproc)PySimplex_init},
    {Py_tp_new, PySimplex_new},
    {Py_tp_dealloc, (destructor)PySimplex_dealloc},
    {0, 0},  // Sentinel
};

static PyType_Spec PySimplexType_Spec = {
    .name = "pysimplex.PySimplex",
    .basicsize = sizeof(PySimplex),
    .flags = Py_TPFLAGS_DEFAULT | Py_TPFLAGS_BASETYPE,
    .slots = PySimplexType_Slots,
};



static int PySimplexModule_exec(PyObject* module) {
    PyObject* pysimplex_type;

    pysimplex_type = PyType_FromSpec(&PySimplexType_Spec);
    if (!pysimplex_type) {
        Py_XDECREF(pysimplex_type);
        Py_XDECREF(module);
        return -1;
    }

    if (PyModule_AddObject(module, "PySimplex", pysimplex_type)) {
        Py_XDECREF(pysimplex_type);
        Py_XDECREF(module);
        return -1;
    }

    return 0;
}


static PyModuleDef_Slot PySimplexModule_Slots[] = {
    {Py_mod_exec, PySimplexModule_exec},
    {0, NULL},
};


static PyModuleDef PySimplexModuleDef = {
    .m_base = PyModuleDef_HEAD_INIT,
    .m_name = "pysimplex",
    .m_doc = "The Simplex blendshape solver in Python",
    .m_size = 0,
    .m_methods = NULL,
    .m_slots = PySimplexModule_Slots,
};


PyMODINIT_FUNC PyInit_pysimplex(void) {

    return PyModuleDef_Init(&PySimplexModuleDef);
}











/*

static PyTypeObject PySimplexType = {
    .ob_base = PyVarObject_HEAD_INIT(NULL, 0)
    .tp_name = "pysimplex.PySimplex",
    .tp_doc = PyDoc_STR("PySimplex objects"),
    .tp_methods = PySimplex_methods,
    .tp_getset = PySimplex_getseters,
    .tp_init = (initproc)PySimplex_init,
    .tp_new = PySimplex_new,
};

static PyModuleDef PySimplexModuleDef = {
    .m_base = PyModuleDef_HEAD_INIT,
    .m_name = "pysimplex",
    .m_doc = "The Simplex blendshape solver in Python",
    .m_size = -1,
};


static PyObject * localInit(void)
{
    PyObject* m;

    // C++ doesn't like the tp flags out of order
    // so I've gotta set some of 'em here
    PySimplexType.tp_flags = Py_TPFLAGS_DEFAULT | Py_TPFLAGS_BASETYPE;
    PySimplexType.tp_basicsize = sizeof(PySimplex);
    PySimplexType.tp_dealloc = (destructor)PySimplex_dealloc;

    if (PyType_Ready(&PySimplexType) < 0)
        return NULL;

    m = PyModule_Create(&PySimplexModuleDef);

    if (m == NULL)
        return NULL;

    Py_INCREF(&PySimplexType);
    if (PyModule_AddObject(m, "PySimplex", (PyObject *) &PySimplexType) < 0) {
        Py_DECREF(&PySimplexType);
        Py_DECREF(m);
        return NULL;
    }
    return m;

}

PyMODINIT_FUNC PyInit_pysimplex(void) {
    return localInit();
}

*/







/*
static PyTypeObject PySimplexType = {
    PyVarObject_HEAD_INIT(NULL, 0)
    "pysimplex.PySimplex",             // tp_name
    sizeof(PySimplex),             // tp_basicsize
    0,                         // tp_itemsize
    (destructor)PySimplex_dealloc, // tp_dealloc
    0,                         // tp_print
    0,                         // tp_getattr
    0,                         // tp_setattr
    0,                         // tp_compare
    0,                         // tp_repr
    0,                         // tp_as_number
    0,                         // tp_as_sequence
    0,                         // tp_as_mapping
    0,                         // tp_hash
    0,                         // tp_call
    0,                         // tp_str
    0,                         // tp_getattro
    0,                         // tp_setattro
    0,                         // tp_as_buffer
    Py_TPFLAGS_DEFAULT |
        Py_TPFLAGS_BASETYPE,   // tp_flags
    "PySimplex objects",       // tp_doc
    0,                         // tp_traverse
    0,                         // tp_clear
    0,                         // tp_richcompare
    0,                         // tp_weaklistoffset
    0,                         // tp_iter
    0,                         // tp_iternext
    PySimplex_methods,         // tp_methods
    0,                         // tp_members
    PySimplex_getseters,       // tp_getset
    0,                         // tp_base
    0,                         // tp_dict
    0,                         // tp_descr_get
    0,                         // tp_descr_set
    0,                         // tp_dictoffset
    (initproc)PySimplex_init,  // tp_init
    0,                         // tp_alloc
    PySimplex_new,             // tp_new
};

static PyMethodDef module_methods[] = {
    {NULL}  // Sentinel
};

static struct PyModuleDef PySimplexModuleDef = {
    PyModuleDef_HEAD_INIT,
    "pysimplex",     // m_name
    "The Simplex blendshape solver in Python",  // m_doc
    -1,                  // m_size
    module_methods,      // m_methods
    NULL,                // m_reload
    NULL,                // m_traverse
    NULL,                // m_clear
    NULL,                // m_free
};

static PyObject * localInit(void)
{
    PyObject* m;

    if (PyType_Ready(&PySimplexType) < 0)
        return NULL;
    m = PyModule_Create(&PySimplexModuleDef);

    if (m == NULL)
        return NULL;

    Py_INCREF(&PySimplexType);
    PyModule_AddObject(m, "PySimplex", (PyObject *)&PySimplexType);
    return m;
}

PyMODINIT_FUNC PyInit_pysimplex(void) {
    return localInit();
}
*/






