from setuptools import setup, Extension, find_namespace_packages
from setuptools.command.build_ext import build_ext
from setuptools.command.install import install
import os
import platform
import io
import sys
import shutil

# Ensure UTF-8 encoding is used
sys.stdout.reconfigure(encoding='utf-8') if hasattr(sys.stdout, 'reconfigure') else None

# Determine current system and architecture
system = platform.system()
machine = platform.machine()

# Get absolute path of current directory
base_dir = os.path.abspath(os.path.dirname(__file__))

class CustomInstall(install):
    def run(self):
        install.run(self)
        
        # Copy dynamic library files to package root directory
        if system == 'Windows':
            dll_dir = os.path.join(base_dir, 'libssp', 'lib', 'win_x64_vs2017')
            # libssp.dll is release version DLL file in win_x64_vs2017 directory
            dll_files = ['libssp.dll']
        elif system == 'Linux':
            dll_dir = os.path.join(base_dir, 'libssp', 'lib', 'linux_x64')
            dll_files = ['libssp.so']
        elif system == 'Darwin':
            # use mac_arm64 for arm64 architecture
            if machine == 'arm64':
                dll_dir = os.path.join(base_dir, 'libssp', 'lib', 'mac_arm64')
            else:
                dll_dir = os.path.join(base_dir, 'libssp', 'lib', 'mac')
            dll_files = ['libssp.dylib']
        else:
            raise ValueError(f"Unsupported system: {system}")

        # Copy dynamic library files to package root directory
        target_dir = os.path.join(self.install_lib, 'libssp')
        for dll_file in dll_files:
            src = os.path.join(dll_dir, dll_file)
            if os.path.exists(src):
                dst = os.path.join(target_dir, dll_file)
                shutil.copy2(src, dst)
                print(f"Copied {dll_file} to {dst}")

class BuildExt(build_ext):
    def build_extensions(self):
        print("\n=== Build Information ===")
        print(f"Build directory: {self.build_lib}")
        print(f"Package data: {self.distribution.package_data}")
        print(f"Current directory: {os.getcwd()}")
        print(f"Base directory: {base_dir}")
        print(f"System: {system}")
        print(f"Architecture: {machine}")
        
        # determine library directory and extension based on platform
        if system == 'Windows':
            lib_dir = os.path.join(base_dir, 'libssp', 'lib', 'win_x64_vs2017')
            lib_ext = '.dll'
            lib_files = ['libssp.dll']
        elif system == 'Linux':
            lib_dir = os.path.join(base_dir, 'libssp', 'lib', 'linux_x64')
            lib_ext = '.so'
            lib_files = ['libssp.so']
        elif system == 'Darwin':
            # use mac_arm64 for arm64 architecture
            if machine == 'arm64':
                lib_dir = os.path.join(base_dir, 'libssp', 'lib', 'mac_arm64')
            else:
                lib_dir = os.path.join(base_dir, 'libssp', 'lib', 'mac')
            lib_ext = '.dylib'
            lib_files = ['libssp.dylib']
        else:
            raise ValueError(f"Unsupported system: {system}")

        # check library files in source directory
        if os.path.exists(lib_dir):
            print(f"\nLibrary files in source directory ({lib_dir}):")
            for file in os.listdir(lib_dir):
                if file.endswith(lib_ext):
                    print(f"  - {file}")
        else:
            print(f"\nLibrary directory not found: {lib_dir}")
            raise RuntimeError(f"Required library directory not found: {lib_dir}")

        # build extension
        build_ext.build_extensions(self)
        
        # check library files in build directory
        if self.build_lib:
            build_lib_dir = os.path.join(self.build_lib, 'libssp')
            if os.path.exists(build_lib_dir):
                print(f"\nLibrary files in build directory ({build_lib_dir}):")
                for file in os.listdir(build_lib_dir):
                    if file.endswith(lib_ext):
                        print(f"  - {file}")
            else:
                print(f"\nBuild directory not found: {build_lib_dir}")
                raise RuntimeError(f"Failed to create build directory: {build_lib_dir}")

        # copy library files to build directory
        if not os.path.exists(build_lib_dir):
            os.makedirs(build_lib_dir)
        
        # copy only specified library files
        for lib_file in lib_files:
            src = os.path.join(lib_dir, lib_file)
            if os.path.exists(src):
                dst = os.path.join(build_lib_dir, lib_file)
                shutil.copy2(src, dst)
                print(f"Copied {lib_file} to {dst}")
            else:
                print(f"Warning: {lib_file} not found in {lib_dir}")

        print("\nBuild completed successfully")

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
    # use mac_arm64 for arm64 architecture
    if machine == 'arm64':
        library_dirs = [os.path.join(base_dir, 'libssp', 'lib', 'mac_arm64')]
    else:
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
    cmdclass={
        "build_ext": BuildExt,
        "install": CustomInstall
    },
    packages=find_namespace_packages(include=["libssp", "libssp.*"]),
    include_package_data=True,
)
