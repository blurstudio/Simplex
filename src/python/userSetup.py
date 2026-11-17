import os
import sys
from importlib.machinery import PathFinder


class SimplexFinder:
    """A import finder that ensures that simplexui and pysimplex are loaded
    from the maya module and not anywhere elses

    Use `SimplexFinder.install()` or `SimplexFinder.uninstall()` as needed
    """

    _is_simplex_finder = True
    _names = ("simplexui", "pysimplex")
    _paths = []

    @classmethod
    def find_spec(cls, fullname, path=None, target=None):
        # Submodules resolve through their parent's __path__, which already points into the module
        if fullname not in cls._names:
            return None
        # None if it's not in the module, so the normal import machinery takes over
        return PathFinder.find_spec(fullname, cls._paths)

    @classmethod
    def install(cls, module_root):
        """Installs this class at the front of sys.meta_path, searching the sys.path
        entries that live inside `module_root`. It's safe to call this repeatedly as
        it will call uninstall.
        """
        root = os.path.normcase(os.path.abspath(module_root)) + os.sep
        cls._paths = [
            p for p in sys.path
            if os.path.normcase(os.path.abspath(p)).startswith(root)
        ]
        cls.uninstall()
        sys.meta_path.insert(0, cls)

    @classmethod
    def uninstall(cls):
        """Remove this finder from sys.meta_path if installed."""
        remove = [f for f in sys.meta_path if getattr(f, '_is_simplex_finder', False)]
        for finder in remove:
            sys.meta_path.remove(finder)


def _init_simplex():
    # Maya execfile's this into __main__, so __file__ isn't ours. The code object knows the real path
    # This file lives at <module>/scripts/userSetup.py
    scripts_dir = os.path.dirname(os.path.abspath(_init_simplex.__code__.co_filename))
    SimplexFinder.install(os.path.dirname(scripts_dir))


_init_simplex()
