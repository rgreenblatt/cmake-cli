import argparse
import subprocess
import multiprocessing
import shutil
import os
import sys


class BaseCMakeBuilder():
    @staticmethod
    def base_build_dir():
        return "build"

    @staticmethod
    def pager_list():
        return  [["less", "-R"], ["bat", "-p"], ["more"]]

    @staticmethod
    def name():
        return "cmake_cli"

    @staticmethod
    def ccache_default():
        return False

    @staticmethod
    def has_build_testing_default():
        return True

    @staticmethod
    def build_testing_default():
        return False

    @staticmethod
    def exists_in_path(cmd):
        return shutil.which(cmd) is not None

    def exists_in_path_warn(self, cmd):
        out = self.exists_in_path(cmd)
        if not out:
            print("WARN:", cmd, "not found in path")
        return out

    def get_pager(self):
        for pager in self.pager_list():
            if self.exists_in_path(pager[0]):
                return pager
        return None

    def base_cmake_command(self, piped_commands):
        if piped_commands and self.exists_in_path("unbuffer"):
            return ["unbuffer", "cmake"]
        return ["cmake"]

    @staticmethod
    def piped_runner(cmds):
        processes = []
        cmd_process = None
        print("running:", cmds)
        for i, c in enumerate(cmds):
            last = i == len(cmds) - 1
            if last:
                stdout = None
                stderr = None
            else:
                stdout = subprocess.PIPE
                stderr = subprocess.STDOUT
            cmd_process = subprocess.Popen(
                c,
                stdout=stdout,
                stderr=stderr,
                stdin=None if cmd_process is None else cmd_process.stdout)
            processes.append(cmd_process)

        for process in reversed(processes):
            process.wait()
            if process.returncode != 0:
                sys.exit(process.returncode)

    def runner(self, cmd):
        self.piped_runner([cmd])

    @staticmethod
    def extend_piped_commands(_):
        pass

    @staticmethod
    def extend_gen_cmd(*_):
        pass

    @staticmethod
    def extend_build_cmd(*_):
        pass

    def build(self,
              subargs,
              directory,
              is_release=False,
              debug_info=True,
              additional_gen_args=None,
              additional_build_args=None,
              piped_commands=None,
              skip_gen=False,
              skip_build=False):
        try:
            skip_gen = skip_gen or subargs.skip_gen
        except AttributeError:
            pass

        if skip_gen and skip_build:
            print(
                "WARN: no commands will be run as gen and build were skipped")
            return

        if additional_gen_args is None:
            additional_gen_args = []
        if additional_build_args is None:
            additional_build_args = []
        if piped_commands is None:
            piped_commands = []

        self.extend_piped_commands(piped_commands)

        if self.args.page:
            pager = self.get_pager()
            if pager is not None:
                piped_commands.append(pager)

        try:
            is_release = subargs.release
        except AttributeError:
            pass

        try:
            debug_info = subargs.debug_info
        except AttributeError:
            pass

        if is_release:
            if debug_info:
                build_type = "RelWithDebInfo"
            else:
                build_type = "Release"
        else:
            build_type = "Debug"
            assert debug_info

        base_cmake = self.base_cmake_command(piped_commands)

        gen_args = [
            "-G" + self.args.generator,
            "-B" + directory,
            "-DCMAKE_BUILD_TYPE=" + build_type,
        ]

        if self.args.source_dir is not None:
            gen_args += [self.args.source_dir]

        if self.args.ccache:
            if self.exists_in_path_warn("ccache"):
                gen_args += [
                    "-DCMAKE_C_COMPILER_LAUNCHER=ccache",
                    "-DCMAKE_CXX_COMPILER_LAUNCHER=ccache",
                    "-DCMAKE_CUDA_COMPILER_LAUNCHER=ccache"
                ]

        try:
            if subargs.build_testing:
                gen_args += ["-DBUILD_TESTING=ON"]
            else:
                gen_args += ["-DBUILD_TESTING=OFF"]
        except AttributeError:
            pass

        def append_args(cmd, args):
            if args is not None:
                cmd += args.split()

        gen_cmd = base_cmake + gen_args + additional_gen_args
        self.extend_gen_cmd(subargs, gen_cmd)
        try:
            append_args(gen_cmd, subargs.gen_args)
        except AttributeError:
            pass

        build_cmd = base_cmake + ["--build", directory] + additional_build_args
        self.extend_build_cmd(subargs, build_cmd)
        try:
            append_args(build_cmd, subargs.build_args)
        except AttributeError:
            pass

        if self.args.threads is None:
            if self.args.generator == "Unix Makefiles":
                build_cmd += ["-j", str(multiprocessing.cpu_count())]
        else:
            build_cmd += ["-j", str(self.args.threads)]

        if not skip_gen:
            self.piped_runner([gen_cmd] + piped_commands)
        if not skip_build:
            self.piped_runner([build_cmd] + piped_commands)

    def build_default_command_parser(self,
                                     description,
                                     release_default=False,
                                     has_release=True,
                                     has_build_testing=None,
                                     skip_gen=False,
                                     skip_build=False):
        parser = argparse.ArgumentParser(description=description)
        parser.add_argument('--directory', help='force specific directory')
        if not skip_gen:
            parser.add_argument(
                '--gen-args',
                help='additional arguments for cmake generation')
            parser.add_argument(
                '--skip-gen',
                action='store_true',
                help="don't generate, assume already generated")
            if has_release:
                parser.add_argument('--release',
                                    default=release_default,
                                    dest='release',
                                    action='store_true')
                parser.add_argument('--debug',
                                    dest='release',
                                    action='store_false')
                parser.add_argument('--debug-info',
                                    default=True,
                                    dest='debug_info',
                                    action='store_true')
                parser.add_argument('--no-debug-info',
                                    default=True,
                                    dest='debug_info',
                                    action='store_false')

            if has_build_testing is None:
                has_build_testing = self.has_build_testing_default()
            if has_build_testing:
                parser.add_argument('--build-testing',
                                    default=self.build_testing_default(),
                                    dest='build_testing',
                                    action='store_true')
                parser.add_argument('--no-build-testing',
                                    dest='build_testing',
                                    action='store_false')
        if not skip_build:
            parser.add_argument('--build-args',
                                help='additional arguments for cmake building')

        return parser

    @staticmethod
    def extend_directory(_):
        return ""

    # should be able to take args from build_default_command_parser
    # build_default_command_parser must be called with has_release=True
    def get_directory(self, args, forced_base=None):
        if args.directory is not None:
            return args.directory

        if forced_base is None:
            base = "release" if args.release else "debug"
        else:
            base = forced_base

        return os.path.join(self.base_build_dir(),
                            base + self.extend_directory(args))

    @staticmethod
    def parse_no_args(description, remaining_args):
        parser = argparse.ArgumentParser(description=description)
        parser.parse_args(remaining_args)

    def build_command(self, remaining_args):
        args = self.build_default_command_parser('build project').parse_args(
            remaining_args)
        self.build(args, self.get_directory(args))

    def cc_command(self, remaining_args):
        args = self.build_default_command_parser(
            'generate compile_commands.json',
            has_release=False, skip_build=True).parse_args(remaining_args)
        directory = os.path.join(self.base_build_dir(), "compile_commands_dir")
        self.build(args,
                   directory,
                   additional_gen_args=["-DCMAKE_EXPORT_COMPILE_COMMANDS=YES"],
                   skip_build=True)
        if os.path.exists("compile_commands.json"):
            print("compile_commands.json exists - not overriding")
        else:
            os.symlink(os.path.join(directory, "compile_commands.json"),
                       "compile_commands.json")

    def clean_command(self, remaining_args):
        self.parse_no_args('clean project', remaining_args)
        shutil.rmtree(self.base_build_dir(), ignore_errors=True)

    def format_command(self, remaining_args):
        self.parse_no_args('format code with clang-format', remaining_args)
        needed = ["bash", "clang-format", "fd"]
        has_needed = [self.exists_in_path(e) for e in needed]
        if not all(has_needed):
            print("can't format, missing: ",
                  ", ".join(e for e, has in zip(needed, has_needed) if has))
            sys.exit(1)
        self.runner(
            ['bash', '-c', 'clang-format -i $(fd -e cu -e cpp -e h -e cuh)'])

    @staticmethod
    def extend_main_parser(_):
        pass

    def build_main_parser(self):
        main_parser = argparse.ArgumentParser(
            description='Simple and extensible cmake wrapper',
            usage="{} [OPTIONS] <COMMAND> [<SUBOPTIONS>]".format(self.name()))
        main_parser.add_argument('command', help='subcommand to run')
        main_parser.add_argument(
            '--generator',
            default='Ninja',
            help='cmake generator (Ninja, Unix Makefiles, ...)')
        main_parser.add_argument('-p',
                                 '--pager',
                                 dest='page',
                                 action='store_true',
                                 help='page output')
        main_parser.add_argument('-P',
                                 '--no-pager',
                                 dest='page',
                                 action='store_false',
                                 help="don't page output")
        main_parser.add_argument('--ccache',
                                 dest='ccache',
                                 action='store_true',
                                 default=self.ccache_default(),
                                 help='use ccache')
        main_parser.add_argument('--no-ccache',
                                 dest='ccache',
                                 action='store_false',
                                 default=self.ccache_default(),
                                 help="don't use ccache")
        main_parser.add_argument('-j',
                                 '--threads',
                                 type=int,
                                 default=None,
                                 help='set num threads')
        main_parser.add_argument('--source-dir', help='source directory')

        self.extend_main_parser(main_parser)

        return main_parser

    @staticmethod
    def extend_commands(_):
        pass

    def commands(self):
        commands = {
            "build": self.build_command,
            "compile_commands": self.cc_command,
            "clean": self.clean_command,
            "format": self.format_command,
        }
        self.extend_commands(commands)

        return commands

    def pick_and_use_sub_command(self, remaining_args):
        commands = self.commands()
        try:
            cmd = commands[self.args.command]
        except KeyError:
            print("{0}: '{1}' is not a command. See '{0} --help'.".format(
                self.name(), self.args.command))
            sys.exit(1)
        cmd(remaining_args)

    def __init__(self):
        main_parser = self.build_main_parser()

        self.args, unknown = main_parser.parse_known_args()

        self.pick_and_use_sub_command(unknown)
