import argparse
import subprocess
import multiprocessing
import shutil
import os
import sys


class BaseCMakeBuilder():
    base_build_dir = "build"
    pager_list = [["less", "-R"], ["bat", "-p"], ["more"]]
    name = "cmake_cli"

    @staticmethod
    def exists_in_path(cmd):
        return shutil.which(cmd) is not None

    def get_directory(self, is_release, forced=None):
        if forced is not None:
            return forced

        return os.path.join(self.base_build_dir,
                            "release" if is_release else "debug")

    def get_pager(self):
        for pager in self.pager_list:
            if self.exists_in_path(pager[0]):
                return pager
        return None

    def base_cmake_command(self, piped_commands):
        if piped_commands and self.exists_in_path("unbuffer"):
            return ["unbuffer", "cmake"]
        else:
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

    def build(self,
              directory,
              is_release,
              debug_info=True,
              additional_gen_args=None,
              additional_build_args=None,
              piped_commands=None,
              skip_gen=False,
              skip_build=False):
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

        if self.args.page:
            pager = self.get_pager()
            if pager is not None:
                piped_commands.append(pager)

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
            "-S.",
            "-G" + self.args.cmake_generator,
            "-B" + directory,
            "-DCMAKE_BUILD_TYPE=" + build_type,
        ]

        if self.args.use_ccache:
            gen_args += [
                "-DCMAKE_C_COMPILER_LAUNCHER=ccache",
                "-DCMAKE_CXX_COMPILER_LAUNCHER=ccache",
                "-DCMAKE_CUDA_COMPILER_LAUNCHER=ccache"
            ]

        gen_cmd = base_cmake + gen_args + additional_gen_args

        build_cmd = base_cmake + ["--build", directory] + additional_build_args

        if self.args.threads is None:
            if self.args.cmake_generator == "Unix Makefiles":
                build_cmd += ["-j", str(multiprocessing.cpu_count())]
        else:
            build_cmd += ["-j", str(self.args.threads)]

        if not skip_gen:
            self.piped_runner([gen_cmd] + piped_commands)
        if not skip_build:
            self.piped_runner([build_cmd] + piped_commands)

    @staticmethod
    def build_default_command_parser(description,
                                     release_default=False,
                                     has_release=True):
        parser = argparse.ArgumentParser(description=description)
        if has_release:
            parser.add_argument('--release',
                                default=release_default,
                                dest='release',
                                action='store_true')
            parser.add_argument('--debug',
                                dest='release',
                                action='store_false')

        return parser

    @staticmethod
    def parse_no_args(description, remaining_args):
        parser = argparse.ArgumentParser(description=description)
        parser.parse_args(remaining_args)

    def build_command(self, remaining_args):
        args = self.build_default_command_parser('build project').parse_args(
            remaining_args)
        self.build(args, self.get_directory(args))

    def run_command(self, remaining_args):
        parser = self.build_default_command_parser('run executable')
        parser.add_argument('executable', help='bin to run')
        parser.add_argument('executable_args', nargs=argparse.REMAINDER)
        args = parser.parse_args(remaining_args)
        directory = self.get_directory(args)
        self.build(args,
                   directory,
                   additional_build_args=["--target", args.executable])
        self.runner([os.path.join(directory, args.executable)] +
                    args.executable_args)

    def cc_command(self, remaining_args):
        args = self.parse_no_args('generate compile_commands.json',
                                  remaining_args)
        directory = os.path.join(self.base_build_dir, "compile_commands_dir")
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
        shutil.rmtree(self.base_build_dir, ignore_errors=True)

    def format_command(self, remaining_args):
        self.parse_no_args('format code with clang-format', remaining_args)
        needed = ["bash", "clang-format", "fd"]
        has_needed = [self.exists_in_path(e) for e in needed]
        if not all(has_needed):
            print("can't format, missing: ",
                  ", ".join(e for e, has in zip(needed, has_needed) if has))
        self.runner(
            ['bash', '-c', 'clang-format -i $(fd -e cu -e cpp -e h -e cuh'])

    @staticmethod
    def extend_main_parser(_):
        pass

    def build_main_parser(self):
        main_parser = argparse.ArgumentParser(
            description='Simple and extensible cmake wrapper',
            usage="{} [OPTIONS] <COMMAND> [<SUBOPTIONS>]".format(self.name))
        main_parser.add_argument('command', help='subcommand to run')
        main_parser.add_argument(
            '--generator',
            default='Ninja',
            help='cmake generator (Ninja, Unix Makefiles, ...)')
        main_parser.add_argument('-p',
                                 '--pager',
                                 dest='pager',
                                 action='store_true',
                                 help='page output')
        main_parser.add_argument('-P',
                                 '--no-pager',
                                 dest='pager',
                                 action='store_false',
                                 help="don't page output")
        main_parser.add_argument('--ccache',
                                 dest='ccache',
                                 action='store_false',
                                 default=True,
                                 help='use ccache')
        main_parser.add_argument('--no-ccache',
                                 dest='ccache',
                                 action='store_true',
                                 default=True,
                                 help="don't use ccache")
        main_parser.add_argument('-j',
                                 '--threads',
                                 type=int,
                                 default=None,
                                 help='set num threads')
        main_parser.add_argument('--directory',
                                 help='force specific directory')

        self.extend_main_parser(main_parser)

        return main_parser

    @staticmethod
    def extend_commands(_):
        pass

    def commands(self):
        commands = {
            "build": self.build_command,
            "run": self.run_command,
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
                self.name, self.args.command))
            sys.exit(1)
        cmd(remaining_args)

    def __init__(self):
        main_parser = self.build_main_parser()

        self.args, unknown = main_parser.parse_known_args()

        self.pick_and_use_sub_command(unknown)
