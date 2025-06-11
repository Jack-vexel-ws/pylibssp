from setuptools import setup, Extension
from setuptools.command.build_ext import build_ext
import os
import platform
import io
import sys

# Ensure UTF-8 encoding is used
sys.stdout.reconfigure(encoding='utf-8') if hasattr(sys.stdout, 'reconfigure') else None

# Determine current system
system = platform.system()

# Get absolute path of current directory
base_dir = os.path.abspath(os.path.dirname(__file__))

class BuildExt(build_ext):
    def build_extensions(self):
        for ext in self.extensions:
            ext.extra_compile_args += ['-std=c++11']
        build_ext.build_extensions(self)

# Import pybind11 to get include path
import pybind11

# Set include directories
include_dirs = [
    os.path.join(base_dir, 'libssp', 'include'),
    os.path.join(base_dir, 'libssp', 'include', 'imf'),
    os.path.join(base_dir, 'libssp', 'include', 'libuv', 'include'),
    pybind11.get_include()
]

# Set library directories and names
if system == 'Windows':
    library_dirs = [os.path.join(base_dir, 'libssp', 'lib', 'win_x64_vs2017')]
    libraries = ['libssp']
    extra_compile_args = ['/EHsc', "/DPYBIND11_DETAILED_ERROR_MESSAGES"]
    extra_link_args = []
elif system == 'Linux':
    library_dirs = [os.path.join(base_dir, 'libssp', 'lib', 'linux_x64')]
    libraries = ['libssp']
    extra_compile_args = ['-std=c++11']
    extra_link_args = []
elif system == 'Darwin':
    library_dirs = [os.path.join(base_dir, 'libssp', 'lib', 'mac')]
    libraries = ['libssp']
    extra_compile_args = ['-std=c++11']
    extra_link_args = []
else:
    raise ValueError(f"Unsupported system: {system}")

ssp_modules = Extension(
        "libssp._libssp",
        sources=["libssp/_libssp.cpp"],
        libraries = ['libssp'],
        include_dirs = include_dirs,
        library_dirs = library_dirs,
        extra_compile_args=extra_compile_args,
        extra_link_args=extra_link_args,
        language="c++"
)

setup(
    ext_modules = [ssp_modules],
    cmdclass={"build_ext": BuildExt},
)
