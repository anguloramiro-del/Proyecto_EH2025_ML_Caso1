"""Entrada del proyecto; ajusta OpenMP en macOS usando la biblioteca del entorno."""
from pathlib import Path
import importlib.util
import os
import sys

root = Path(__file__).resolve().parent
if __name__ == '__main__':
    cache = root/'.cache/matplotlib'
    cache.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault('MPLCONFIGDIR', str(cache))
    if sys.platform == 'darwin' and os.environ.get('EH2025_OPENMP_READY') != '1':
        spec = importlib.util.find_spec('sklearn')
        if spec and spec.origin:
            lib = Path(spec.origin).parent/'.dylibs'
            if (lib/'libomp.dylib').exists():
                env = os.environ.copy()
                env['DYLD_LIBRARY_PATH'] = str(lib) + (os.pathsep + env['DYLD_LIBRARY_PATH']
                                                       if env.get('DYLD_LIBRARY_PATH') else '')
                env['EH2025_OPENMP_READY'] = '1'
                os.execve(sys.executable, [sys.executable, str(Path(__file__).resolve()), *sys.argv[1:]], env)
    os.chdir(root)
    os.execv(sys.executable, [sys.executable, '-m', 'src.workflow', *sys.argv[1:]])
