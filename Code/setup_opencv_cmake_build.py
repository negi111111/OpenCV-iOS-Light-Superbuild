#!/usr/bin/env python

from __future__ import print_function
import glob, re, os, os.path, shutil, string, sys, argparse, traceback, multiprocessing
from subprocess import check_call, check_output, CalledProcessError

def execute(cmd, cwd = None):
    print("Executing: %s in %s" % (cmd, cwd), file=sys.stderr)
    retcode = check_call(cmd, cwd = cwd)
    if retcode != 0:
        raise Exception("Child returned:", retcode)

def getXCodeMajor():
    ret = check_output(["xcodebuild", "-version"])
    m = re.match(r'Xcode\s+(\d+)\..*', ret, flags=re.IGNORECASE)
    if m:
        return int(m.group(1))
    else:
        raise Exception("Failed to parse Xcode version")

class Builder:
    def __init__(self, opencv, contrib, dynamic, bitcodedisabled, exclude, targets):
        self.opencv = os.path.abspath(opencv)
        self.contrib = None
        if contrib:
            modpath = os.path.join(contrib, "modules")
            if os.path.isdir(modpath):
                self.contrib = os.path.abspath(modpath)
            else:
                print("Note: contrib repository is bad - modules subfolder not found", file=sys.stderr)
        self.dynamic = dynamic
        self.bitcodedisabled = bitcodedisabled
        self.exclude = exclude
        self.targets = targets

    def getBD(self, parent, t):

        if len(t[0]) == 1:
            res = os.path.join(parent, 'build-%s-%s' % (t[0][0].lower(), t[1].lower()))
        else:
            res = os.path.join(parent, 'build-%s' % t[1].lower())

        if not os.path.isdir(res):
            os.makedirs(res)
        return os.path.abspath(res)

    def _build(self, outdir):
        outdir = os.path.abspath(outdir)
        if not os.path.isdir(outdir):
            os.makedirs(outdir)
        mainWD = os.path.join(outdir, "build")
        dirs = []

        xcode_ver = getXCodeMajor()

        if self.dynamic:
            alltargets = self.targets
        else:
            # if we are building a static library, we must build each architecture separately
            alltargets = []

            for t in self.targets:
                for at in t[0]:
                    current = ( [at], t[1] )

                    alltargets.append(current)

        for t in alltargets:
            mainBD = self.getBD(mainWD, t)
            dirs.append(mainBD)

            cmake_flags = []
            if self.contrib:
                cmake_flags.append("-DOPENCV_EXTRA_MODULES_PATH=%s" % self.contrib)
            if xcode_ver >= 7 and t[1] == 'iPhoneOS' and self.bitcodedisabled == False:
                cmake_flags.append("-DCMAKE_C_FLAGS=-fembed-bitcode")
                cmake_flags.append("-DCMAKE_CXX_FLAGS=-fembed-bitcode")
            self.buildOne(t[0], t[1], mainBD, cmake_flags)

            if self.dynamic == False:
                self.mergeLibs(mainBD)
        self.makeFramework(outdir, dirs)

    def build(self, outdir):
        try:
            self._build(outdir)
        except Exception as e:
            print("="*60, file=sys.stderr)
            print("ERROR: %s" % e, file=sys.stderr)
            print("="*60, file=sys.stderr)
            traceback.print_exc(file=sys.stderr)
            sys.exit(1)

    def getToolchain(self, arch, target):
        return None

    def getCMakeArgs(self, arch, target):

        args = [
            "cmake",
            "-GXcode",
            "-DAPPLE_FRAMEWORK=ON",
            "-DCMAKE_INSTALL_PREFIX=install",
            "-DCMAKE_BUILD_TYPE=Release",
            "-DOPENCV_INCLUDE_INSTALL_PATH=include",
            "-DOPENCV_3P_LIB_INSTALL_PATH=lib/3rdparty"
        ] + ([
            "-DBUILD_SHARED_LIBS=ON",
            "-DCMAKE_MACOSX_BUNDLE=ON",
            "-DCMAKE_XCODE_ATTRIBUTE_CODE_SIGNING_REQUIRED=NO",
        ] if self.dynamic else [])

        if len(self.exclude) > 0:
            args += ["-DBUILD_opencv_world=OFF"] if not self.dynamic else []
            args += ["-DBUILD_opencv_%s=OFF" % m for m in self.exclude]

        return args

    def getBuildCommand(self, archs, target):

        buildcmd = [
            "xcodebuild",
        ]

        if self.dynamic:
            buildcmd += [
                "IPHONEOS_DEPLOYMENT_TARGET=8.0",
                "ONLY_ACTIVE_ARCH=NO",
            ]

            if not self.bitcodedisabled:
                buildcmd.append("BITCODE_GENERATION_MODE=bitcode")

            for arch in archs:
                buildcmd.append("-arch")
                buildcmd.append(arch.lower())
        else:
            arch = ";".join(archs)
            buildcmd += [
                "IPHONEOS_DEPLOYMENT_TARGET=8.0",
                "ARCHS=%s" % arch,
            ]

        buildcmd += [
                "-sdk", target.lower(),
                "-configuration", "Release",
                "-parallelizeTargets",
                "-jobs", str(multiprocessing.cpu_count()),
            ] + (["-target","ALL_BUILD"] if self.dynamic else [])

        return buildcmd

    def getInfoPlist(self, builddirs):
        return os.path.join(builddirs[0], "ios", "Info.plist")

    def buildOne(self, arch, target, builddir, cmakeargs = []):
        # Run cmake
        toolchain = self.getToolchain(arch, target)
        cmakecmd = self.getCMakeArgs(arch, target) + \
            (["-DCMAKE_TOOLCHAIN_FILE=%s" % toolchain] if toolchain is not None else [])
        if target.lower().startswith("iphoneos"):
            cmakecmd.append("-DCPU_BASELINE=NEON;FP16")
        cmakecmd.append(self.opencv)
        cmakecmd.extend(cmakeargs)
        execute(cmakecmd, cwd = builddir)

        # Clean and build
        clean_dir = os.path.join(builddir, "install")
        if os.path.isdir(clean_dir):
            shutil.rmtree(clean_dir)
        buildcmd = self.getBuildCommand(arch, target)
        execute(buildcmd + ["-target", "ALL_BUILD", "build"], cwd = builddir)
        execute(["cmake", "-P", "cmake_install.cmake"], cwd = builddir)

    def mergeLibs(self, builddir):
        res = os.path.join(builddir, "lib", "Release", "libopencv_merged.a")
        libs = glob.glob(os.path.join(builddir, "install", "lib", "*.a"))
        libs3 = glob.glob(os.path.join(builddir, "install", "lib", "3rdparty", "*.a"))
        print("Merging libraries:\n\t%s" % "\n\t".join(libs + libs3), file=sys.stderr)
        execute(["libtool", "-static", "-o", res] + libs + libs3)

    def makeFramework(self, outdir, builddirs):
        name = "opencv2"

        # set the current dir to the dst root
        framework_dir = os.path.join(outdir, "%s.framework" % name)
        if os.path.isdir(framework_dir):
            shutil.rmtree(framework_dir)
        os.makedirs(framework_dir)

        if self.dynamic:
            dstdir = framework_dir
            libname = "opencv2.framework/opencv2"
        else:
            dstdir = os.path.join(framework_dir, "Versions", "A")
            libname = "libopencv_merged.a"

        # copy headers from one of build folders
        shutil.copytree(os.path.join(builddirs[0], "install", "include", "opencv2"), os.path.join(dstdir, "Headers"))

        # make universal static lib
        libs = [os.path.join(d, "lib", "Release", libname) for d in builddirs]
        lipocmd = ["lipo", "-create"]
        lipocmd.extend(libs)
        lipocmd.extend(["-o", os.path.join(dstdir, name)])
        print("Creating universal library from:\n\t%s" % "\n\t".join(libs), file=sys.stderr)
        execute(lipocmd)

        # dynamic framework has different structure, just copy the Plist directly
        if self.dynamic:
            resdir = dstdir
            shutil.copyfile(self.getInfoPlist(builddirs), os.path.join(resdir, "Info.plist"))
        else:
            # copy Info.plist
            resdir = os.path.join(dstdir, "Resources")
            os.makedirs(resdir)
            shutil.copyfile(self.getInfoPlist(builddirs), os.path.join(resdir, "Info.plist"))

            # make symbolic links
            links = [
                (["A"], ["Versions", "Current"]),
                (["Versions", "Current", "Headers"], ["Headers"]),
                (["Versions", "Current", "Resources"], ["Resources"]),
                (["Versions", "Current", name], [name])
            ]
            for l in links:
                s = os.path.join(*l[0])
                d = os.path.join(framework_dir, *l[1])
                os.symlink(s, d)

class iOSBuilder(Builder):

    def getToolchain(self, arch, target):
        toolchain = os.path.join(self.opencv, "platforms", "ios", "cmake", "Toolchains", "Toolchain-%s_Xcode.cmake" % target)
        return toolchain

    def getCMakeArgs(self, arch, target):
        arch = ";".join(arch)

        args = Builder.getCMakeArgs(self, arch, target)
        args = args + [
            '-DIOS_ARCH=%s' % arch
        ]
        return args


if __name__ == "__main__":
    folder = os.path.abspath(os.path.join(os.path.dirname(sys.argv[0]), "../.."))
    parser = argparse.ArgumentParser(description='The script builds OpenCV.framework for iOS.')
    parser.add_argument('out', metavar='OUTDIR', help='folder to put built framework')
    parser.add_argument('--opencv', metavar='DIR', default=folder, help='folder with opencv repository (default is "../.." relative to script location)')
    parser.add_argument('--contrib', metavar='DIR', default=None, help='folder with opencv_contrib repository (default is "None" - build only main framework)')
    parser.add_argument('--without', metavar='MODULE', default=[], action='append', help='OpenCV modules to exclude from the framework')
    parser.add_argument('--dynamic', default=False, action='store_true', help='build dynamic framework (default is "False" - builds static framework)')
    parser.add_argument('--disable-bitcode', default=False, dest='bitcodedisabled', action='store_true', help='disable bitcode (enabled by default)')
    parser.add_argument('--armv7-arch', default=False, dest='include_armv7_arch', action='store_true', help='include armv7 architecture')
    parser.add_argument('--armv7s-arch', default=False, dest='include_armv7s_arch', action='store_true', help='include armv7s architecture')
    parser.add_argument('--arm64-arch', default=True, dest='include_arm64_arch', action='store_true', help='include arm64 architecture (the script builds arm64 arch by default')
    parser.add_argument('--i386-arch', default=False, dest='include_i386_arch', action='store_true', help='include i386 architecture')
    parser.add_argument('--x86_64-arch', default=False, dest='include_x86_64_arch', action='store_true', help='include x86_64 architecture')

    args = parser.parse_args()

    archs = []

    # Include arm64 arch by default
    iphoneOSArchs = ["arm64"]
    if args.include_armv7_arch:
        iphoneOSArchs.extend(["armv7"])
    if args.include_armv7s_arch:
        iphoneOSArchs.extend(["armv7s"])

    iphoneSimulatorArchs = []
    if args.include_i386_arch:
        iphoneSimulatorArchs.extend(["i386"])
    if args.include_x86_64_arch:
        iphoneSimulatorArchs.extend(["x86_64"])

    if iphoneSimulatorArchs == []:
        archs = [ (iphoneOSArchs, "iPhoneOS"), ]
    else:
        archs = [ (iphoneOSArchs, "iPhoneOS"), (iphoneSimulatorArchs, "iPhoneSimulator"), ]

    b = iOSBuilder(args.opencv, args.contrib, args.dynamic, args.bitcodedisabled, args.without, archs)
    b.build(args.out)
