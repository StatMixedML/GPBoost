# coding: utf-8
"""Setup gpboost package."""
from __future__ import absolute_import

import distutils
import io
import logging
import os
import shutil
import struct
import subprocess
import sys

from platform import system
from setuptools import find_packages, setup
from setuptools.command.install import install
from setuptools.command.install_lib import install_lib
from setuptools.command.sdist import sdist


def find_lib():
    libpath_py = os.path.join(CURRENT_DIR, 'gpboost', 'libpath.py')
    libpath = {'__file__': libpath_py}
    exec(compile(open(libpath_py, "rb").read(), libpath_py, 'exec'), libpath, libpath)

    LIB_PATH = [os.path.relpath(path, CURRENT_DIR) for path in libpath['find_lib_path']()]
    logger.info("Installing lib_gpboost from: %s" % LIB_PATH)
    return LIB_PATH


def copy_files(use_gpu=False):

    def copy_files_helper(folder_name):
        src = os.path.join(CURRENT_DIR, os.path.pardir, folder_name)
        if os.path.exists(src):
            dst = os.path.join(CURRENT_DIR, 'compile', folder_name)
            shutil.rmtree(dst, ignore_errors=True)
            distutils.dir_util.copy_tree(src, dst, verbose=0)
        else:
            raise Exception('Cannot copy {0} folder'.format(src))

    if not os.path.isfile(os.path.join(CURRENT_DIR, '_IS_SOURCE_PACKAGE.txt')):
        copy_files_helper('include')
        copy_files_helper('src')
        copy_files_helper('CSparse')
        copy_files_helper('eigen')
#        if not os.path.exists(os.path.join(CURRENT_DIR, "compile", "windows")):
#            os.makedirs(os.path.join(CURRENT_DIR, "compile", "windows"))
#        distutils.file_util.copy_file(os.path.join(CURRENT_DIR, os.path.pardir, "windows", "GPBoost.sln"),
#                                      os.path.join(CURRENT_DIR, "compile", "windows", "GPBoost.sln"),
#                                      verbose=0)
#        distutils.file_util.copy_file(os.path.join(CURRENT_DIR, os.path.pardir, "windows", "GPBoost.vcxproj"),
#                                      os.path.join(CURRENT_DIR, "compile", "windows", "GPBoost.vcxproj"),
#                                      verbose=0)
        if use_gpu:
            copy_files_helper('compute')
        distutils.file_util.copy_file(os.path.join(CURRENT_DIR, os.path.pardir, "CMakeLists.txt"),
                                      os.path.join(CURRENT_DIR, "compile", "CMakeLists.txt"),
                                      verbose=0)
        distutils.file_util.copy_file(os.path.join(CURRENT_DIR, os.path.pardir, "LICENSE"),
                                      os.path.join(CURRENT_DIR, "LICENSE"),
                                      verbose=0)


def clear_path(path):
    if os.path.isdir(path):
        contents = os.listdir(path)
        for file_name in contents:
            file_path = os.path.join(path, file_name)
            if os.path.isfile(file_path):
                os.remove(file_path)
            else:
                shutil.rmtree(file_path)


def silent_call(cmd, raise_error=False, error_msg=''):
    try:
        output = subprocess.check_output(cmd, stderr=subprocess.STDOUT)
        with open(LOG_PATH, "ab") as log:
            log.write(output)
        return 0
    except Exception as err:
        if isinstance(err, subprocess.CalledProcessError):
            with open(LOG_PATH, "ab") as log:
                log.write(err.output)
        if raise_error:
            raise Exception("\n".join((error_msg, LOG_NOTICE)))
        return 1


def compile_cpp(use_mingw=False, use_gpu=False, use_mpi=False,
                use_hdfs=False, boost_root=None, boost_dir=None,
                boost_include_dir=None, boost_librarydir=None,
                opencl_include_dir=None, opencl_library=None,
                nomp=False, bit32=False):

    if os.path.exists(os.path.join(CURRENT_DIR, "build_cpp")):
        shutil.rmtree(os.path.join(CURRENT_DIR, "build_cpp"))
    os.makedirs(os.path.join(CURRENT_DIR, "build_cpp"))
    os.chdir(os.path.join(CURRENT_DIR, "build_cpp"))

    logger.info("Starting to compile the library.")

    cmake_cmd = ["cmake", "../compile/"]
    if use_gpu:
        cmake_cmd.append("-DUSE_GPU=ON")
        if boost_root:
            cmake_cmd.append("-DBOOST_ROOT={0}".format(boost_root))
        if boost_dir:
            cmake_cmd.append("-DBoost_DIR={0}".format(boost_dir))
        if boost_include_dir:
            cmake_cmd.append("-DBoost_INCLUDE_DIR={0}".format(boost_include_dir))
        if boost_librarydir:
            cmake_cmd.append("-DBOOST_LIBRARYDIR={0}".format(boost_librarydir))
        if opencl_include_dir:
            cmake_cmd.append("-DOpenCL_INCLUDE_DIR={0}".format(opencl_include_dir))
        if opencl_library:
            cmake_cmd.append("-DOpenCL_LIBRARY={0}".format(opencl_library))
    if use_mpi:
        cmake_cmd.append("-DUSE_MPI=ON")
    if nomp:
        cmake_cmd.append("-DUSE_OPENMP=OFF")
    if use_hdfs:
        cmake_cmd.append("-DUSE_HDFS=ON")

    if system() in ('Windows', 'Microsoft'):
        if use_mingw:
            if use_mpi:
                raise Exception('MPI version cannot be compiled by MinGW due to the miss of MPI library in it')
            logger.info("Starting to compile with CMake and MinGW.")
            silent_call(cmake_cmd + ["-G", "MinGW Makefiles"], raise_error=True,
                        error_msg='Please install CMake and all required dependencies first')
            silent_call(["mingw32-make.exe", "_gpboost"], raise_error=True,
                        error_msg='Please install MinGW first')
        else:
            status = 1
            lib_path = os.path.join(CURRENT_DIR, "compile", "windows", "x64", "DLL", "lib_gpboost.dll")
            ## Installion using VS solution currently not supported
#            if not any((use_gpu, use_mpi, use_hdfs, nomp, bit32)):
#                logger.info("Starting to compile with MSBuild from existing solution file.")
#                platform_toolsets = ("v142", "v141", "v140")
#                for pt in platform_toolsets:
#                    status = silent_call(["MSBuild",
#                                          os.path.join(CURRENT_DIR, "compile", "windows", "GPBoost.sln"),
#                                          "/p:Configuration=DLL",
#                                          "/p:Platform=x64",
#                                          "/p:PlatformToolset={0}".format(pt)])
#                    if status == 0 and os.path.exists(lib_path):
#                        break
#                    else:
#                        clear_path(os.path.join(CURRENT_DIR, "compile", "windows", "x64"))
#                if status != 0 or not os.path.exists(lib_path):
#                    logger.warning("Compilation with MSBuild from existing solution file failed.")
            if status != 0 or not os.path.exists(lib_path):
                arch = "Win32" if bit32 else "x64"
                vs_versions = ("Visual Studio 16 2019", "Visual Studio 15 2017", "Visual Studio 14 2015")
                for vs in vs_versions:
                    logger.info("Starting to compile with %s." % vs)
#                    qqq=cmake_cmd+ ["-G", vs, "-A", arch]##DELETE THIS
#                    logger.info("CMAKE." + ' '.join(qqq))##DELETE THIS
                    status = silent_call(cmake_cmd + ["-G", vs, "-A", arch])
                    if status == 0:
                        break
                    else:
                        clear_path(os.path.join(CURRENT_DIR, "build_cpp"))
                if status != 0:
                    raise Exception("\n".join(('Please install Visual Studio or MS Build and all required dependencies first',
                                    LOG_NOTICE)))
                silent_call(["cmake", "--build", ".", "--target", "_gpboost", "--config", "Release"], raise_error=True,
                            error_msg='Please install CMake first')
    else:  # Linux, Darwin (macOS), etc.
        logger.info("Starting to compile with CMake.")
        silent_call(cmake_cmd, raise_error=True, error_msg='Please install CMake and all required dependencies first')
        silent_call(["make", "_gpboost", "-j4"], raise_error=True,
                    error_msg='An error has occurred while building the gpboost library file')
    os.chdir(CURRENT_DIR)


class CustomInstallLib(install_lib):

    def install(self):
        outfiles = install_lib.install(self)
        src = find_lib()[0]
        dst = os.path.join(self.install_dir, 'gpboost')
        dst, _ = self.copy_file(src, dst)
        outfiles.append(dst)
        return outfiles


class CustomInstall(install):

    user_options = install.user_options + [
        ('mingw', 'm', 'Compile with MinGW'),
        ('gpu', 'g', 'Compile GPU version'),
        ('mpi', None, 'Compile MPI version'),
        ('nomp', None, 'Compile version without OpenMP support'),
        ('hdfs', 'h', 'Compile HDFS version'),
        ('bit32', None, 'Compile 32-bit version'),
        ('precompile', 'p', 'Use precompiled library'),
        ('boost-root=', None, 'Boost preferred installation prefix'),
        ('boost-dir=', None, 'Directory with Boost package configuration file'),
        ('boost-include-dir=', None, 'Directory containing Boost headers'),
        ('boost-librarydir=', None, 'Preferred Boost library directory'),
        ('opencl-include-dir=', None, 'OpenCL include directory'),
        ('opencl-library=', None, 'Path to OpenCL library')
    ]

    def initialize_options(self):
        install.initialize_options(self)
        self.mingw = 0
        self.gpu = 0
        self.boost_root = None
        self.boost_dir = None
        self.boost_include_dir = None
        self.boost_librarydir = None
        self.opencl_include_dir = None
        self.opencl_library = None
        self.mpi = 0
        self.hdfs = 0
        self.precompile = 0
        self.nomp = 0
        self.bit32 = 0

    def run(self):
        if (8 * struct.calcsize("P")) != 64:
            if self.bit32:
                logger.warning("You're installing 32-bit version. "
                               "This version is slow and untested, so use it on your own risk.")
            else:
                raise Exception("Cannot install GPBoost in 32-bit Python, "
                                "please use 64-bit Python instead.")
        open(LOG_PATH, 'wb').close()
        if not self.precompile:
            copy_files(use_gpu=self.gpu)
            compile_cpp(use_mingw=self.mingw, use_gpu=self.gpu, use_mpi=self.mpi,
                        use_hdfs=self.hdfs, boost_root=self.boost_root, boost_dir=self.boost_dir,
                        boost_include_dir=self.boost_include_dir, boost_librarydir=self.boost_librarydir,
                        opencl_include_dir=self.opencl_include_dir, opencl_library=self.opencl_library,
                        nomp=self.nomp, bit32=self.bit32)
        install.run(self)
        if os.path.isfile(LOG_PATH):
            os.remove(LOG_PATH)


class CustomSdist(sdist):

    def run(self):
        copy_files(use_gpu=False)
        open(os.path.join(CURRENT_DIR, '_IS_SOURCE_PACKAGE.txt'), 'w').close()
        if os.path.exists(os.path.join(CURRENT_DIR, 'gpboost', 'Release')):
            shutil.rmtree(os.path.join(CURRENT_DIR, 'gpboost', 'Release'))
        if os.path.exists(os.path.join(CURRENT_DIR, 'gpboost', 'windows', 'x64')):
            shutil.rmtree(os.path.join(CURRENT_DIR, 'gpboost', 'windows', 'x64'))
        if os.path.isfile(os.path.join(CURRENT_DIR, 'gpboost', 'lib_gpboost.so')):
            os.remove(os.path.join(CURRENT_DIR, 'gpboost', 'lib_gpboost.so'))
        sdist.run(self)
        if os.path.isfile(os.path.join(CURRENT_DIR, '_IS_SOURCE_PACKAGE.txt')):
            os.remove(os.path.join(CURRENT_DIR, '_IS_SOURCE_PACKAGE.txt'))


if __name__ == "__main__":
    CURRENT_DIR = os.path.abspath(os.path.dirname(__file__))
    LOG_PATH = os.path.join(os.path.expanduser('~'), 'GPBoost_compilation.log')
    LOG_NOTICE = "The full version of error log was saved into {0}".format(LOG_PATH)
    if os.path.isfile(os.path.join(CURRENT_DIR, os.path.pardir, 'VERSION.txt')):
        distutils.file_util.copy_file(os.path.join(CURRENT_DIR, os.path.pardir, 'VERSION.txt'),
                                      os.path.join(CURRENT_DIR, 'gpboost', 'VERSION.txt'),
                                      verbose=0)
    version = io.open(os.path.join(CURRENT_DIR, 'gpboost', 'VERSION.txt'), encoding='utf-8').read().strip()
    readme = io.open(os.path.join(CURRENT_DIR, 'README.rst'), encoding='utf-8').read()

    sys.path.insert(0, CURRENT_DIR)

    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger('GPBoost')

    setup(name='gpboost',
          version=version,
          description='GPBoost Python Package',
          long_description=readme,
          install_requires=[
              'numpy',
              'scipy',
              'scikit-learn<=0.21.3'
          ],
          maintainer='Fabio Sigrist',
          maintainer_email='fabiosigrist@gmail.com',
          zip_safe=False,
          cmdclass={
              'install': CustomInstall,
              'install_lib': CustomInstallLib,
              'sdist': CustomSdist,
          },
          packages=find_packages(),
          include_package_data=True,
          license='Apache License, Version 2.0, + see LICENSE file',
          url='https://github.com/fabsig/GPBoost',
          classifiers=['Development Status :: 5 - Production/Stable',
                       'Intended Audience :: Science/Research',
                       'License :: OSI Approved :: Apache Software License',
                       'Natural Language :: English',
                       'Operating System :: MacOS',
                       'Operating System :: Microsoft :: Windows',
                       'Operating System :: POSIX',
                       'Operating System :: Unix',
                       'Programming Language :: Python :: 2',
                       'Programming Language :: Python :: 2.7',
                       'Programming Language :: Python :: 3',
                       'Programming Language :: Python :: 3.5',
                       'Programming Language :: Python :: 3.6',
                       'Programming Language :: Python :: 3.7',
                       'Topic :: Scientific/Engineering :: Artificial Intelligence'])
