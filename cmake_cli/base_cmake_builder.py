import argparse
import subprocess
import multiprocessing
import shutil
import os
import sys
from contextlib import suppress

base_has_build_testing_default = True
base_build_testing_default = None


class BaseCMakeBuilder():
    @staticmethod
    def base_build_dir():
        return "build"

    @staticmethod
    def pager_list():
        return [["less", "-RFX"], ["bat", "-p"], ["more"]]

    @staticmethod
    def name():
        return "cmake_cli"

    @staticmethod
    def ccache_default():
        return False

    @staticmethod
    def default_cxx_compiler():
        return None

    @staticmethod
    def default_c_compiler():
        return None

    @staticmethod
    def default_cuda_compiler():
        return None

    @staticmethod
    def has_build_testing_default():
        return base_has_build_testing_default

    @staticmethod
    def build_testing_default():
        return base_build_testing_default

    @staticmethod
    def c_family_file_extensions():
        return [
            "C", "cc", "cpp", "cxx", "c++", "h", "H", "hh", "hpp", "hxx",
            "h++", "c", "cu", "cuh"
        ]

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

    @staticmethod
    def cmake_command():
        return ["cmake"]

    def build_cmake_command(self):
        return self.cmake_command()

    @staticmethod
    def piped_runner(cmds, env=None):
        processes = []
        cmd_process = None
        print("running:", cmds)
        for i, c in enumerate(cmds):
            last = i == len(cmds) - 1
            first = i == 0
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
                stdin=None if cmd_process is None else cmd_process.stdout,
                env=env if first else None)
            processes.append(cmd_process)

        for process in reversed(processes):
            process.wait()
            if process.returncode != 0:
                sys.exit(process.returncode)

    def runner(self, cmd, env=None):
        self.piped_runner([cmd], env=env)

    @staticmethod
    def extend_piped_commands():
        return []

    @staticmethod
    def extend_gen_cmd():
        return []

    @staticmethod
    def extend_build_cmd():
        return []

    def build(self,
              directory,
              is_release=False,
              release_debug_info=True,
              additional_gen_args=None,
              additional_build_args=None,
              piped_commands=None,
              skip_gen=False,
              skip_build=False):
        with suppress(AttributeError):
            skip_gen = self.args.skip_gen
        with suppress(AttributeError):
            skip_build = self.args.skip_build

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

        def append_args(cmd, args):
            if args is not None:
                cmd += args.split()

        if not skip_gen:
            with suppress(AttributeError):
                is_release = self.args.release
            with suppress(AttributeError):
                release_debug_info = self.args.release_debug_info

            if is_release:
                if release_debug_info:
                    build_type = "RelWithDebInfo"
                else:
                    build_type = "Release"
            else:
                build_type = "Debug"

            gen_args = []

            with suppress(AttributeError):
                gen_args.append("-G" + self.args.generator)

            gen_args += [
                "-B" + directory,
                "-DCMAKE_BUILD_TYPE=" + build_type,
            ]

            if self.args.source_dir is not None:
                gen_args += [self.args.source_dir]

            with suppress(AttributeError):
                if self.args.ccache:
                    if self.exists_in_path_warn("ccache"):
                        gen_args += [
                            "-DCMAKE_C_COMPILER_LAUNCHER=ccache",
                            "-DCMAKE_CXX_COMPILER_LAUNCHER=ccache",
                            "-DCMAKE_CUDA_COMPILER_LAUNCHER=ccache"
                        ]

            with suppress(AttributeError):
                if self.args.build_testing is not None:
                    if self.args.build_testing:
                        gen_args += ["-DBUILD_TESTING=ON"]
                    else:
                        gen_args += ["-DBUILD_TESTING=OFF"]

            gen_cmd = (self.cmake_command() + gen_args + additional_gen_args +
                       self.extend_gen_cmd())
            with suppress(AttributeError):
                append_args(gen_cmd, self.args.gen_args)

            self.runner(gen_cmd)
        if not skip_build:
            build_args = ["--build", directory]

            if self.args.threads is None:
                if self.args.generator == "Unix Makefiles":
                    build_args += ["-j", str(multiprocessing.cpu_count())]
            else:
                build_args += ["-j", str(self.args.threads)]

            with suppress(AttributeError):
                if self.args.page:
                    pager = self.get_pager()
                    if pager is not None:
                        piped_commands.append(pager)

            piped_commands += self.extend_piped_commands()

            build_cmd = (self.build_cmake_command() + build_args +
                         additional_build_args + self.extend_build_cmd())
            with suppress(AttributeError):
                append_args(build_cmd, self.args.build_args)

            native_build_tool_args = ["--"]

            if self.args.keep_going:
                if self.args.generator == "Unix Makefiles":
                    native_build_tool_args += ["-k"]
                elif self.args.generator == "Ninja":
                    native_build_tool_args += ["-k", "0"]
            with suppress(AttributeError):
                append_args(native_build_tool_args,
                            self.args.native_build_tool_args)

            build_env = None
            if self.args.force_color or (piped_commands
                                         and self.args.force_color_when_piped):
                build_env = {"CLICOLOR_FORCE": "TRUE"}

            self.piped_runner([build_cmd + native_build_tool_args] +
                              piped_commands,
                              env=build_env)

    def build_default_command_parser(self,
                                     parser,
                                     skip_build=False,
                                     never_built=False,
                                     **kwargs):
        if never_built:
            skip_build = True
        self.build_default_command_parser_impl(parser,
                                               skip_build=skip_build,
                                               never_built=never_built,
                                               **kwargs)

    def build_default_command_parser_impl(
            self,
            parser,
            release_default=False,
            has_release=True,
            has_build_testing=base_has_build_testing_default,
            build_testing_default=base_build_testing_default,
            skip_gen=False,
            skip_build=False,
            never_built=False,
            has_ccache=False):
        if never_built:
            skip_build = True
        parser.add_argument('--directory', help='force specific directory')
        if not skip_gen:
            if not never_built:
                parser.add_argument(
                    '--generator',
                    default='Ninja',
                    help='cmake generator (Ninja, Unix Makefiles, ...)')
            if has_ccache:
                parser.add_argument('--ccache',
                                    dest='ccache',
                                    action='store_true',
                                    default=self.ccache_default(),
                                    help='use ccache')
                parser.add_argument('--no-ccache',
                                    dest='ccache',
                                    action='store_false',
                                    default=self.ccache_default(),
                                    help="don't use ccache")
            parser.add_argument('--source-dir', help='source directory')

            parser.add_argument(
                '--gen-args', help='additional arguments for cmake generation')
            if has_release:
                parser.add_argument('--release',
                                    default=release_default,
                                    dest='release',
                                    action='store_true')
                parser.add_argument('--debug',
                                    dest='release',
                                    action='store_false')
                parser.add_argument('--release-debug-info',
                                    default=False,
                                    dest='release_debug_info',
                                    action='store_true',
                                    help='enable debug info for release build')
                parser.add_argument('--no-release-debug-info',
                                    default=False,
                                    dest='release_debug_info',
                                    action='store_false')

            if has_build_testing:
                parser.add_argument('--build-testing',
                                    default=build_testing_default,
                                    dest='build_testing',
                                    action='store_true')
                parser.add_argument('--no-build-testing',
                                    dest='build_testing',
                                    action='store_false')
        if not skip_build:
            parser.add_argument('-p',
                                '--pager',
                                dest='page',
                                action='store_true',
                                help='page build output')
            parser.add_argument('-P',
                                '--no-pager',
                                dest='page',
                                action='store_false')
            parser.add_argument('-j',
                                '--threads',
                                type=int,
                                default=None,
                                help='set num threads')
            parser.add_argument('-k',
                                '--keep-going',
                                action='store_true',
                                help='keep going after build failure')
            parser.add_argument(
                '--force-color-when-piped',
                action='store_true',
                dest='force_color_when_piped',
                default=True,
                help='force color from build tool only if output is piped')
            parser.add_argument('--no-force-color-when-piped',
                                action='store_false',
                                dest='force_color_when_piped',
                                default=True)
            parser.add_argument('--force-color',
                                action='store_false',
                                dest='force_color',
                                default=False,
                                help="force color from build tool")
            parser.add_argument('--no-force-color',
                                action='store_false',
                                dest='force_color',
                                default=False)
            parser.add_argument('--build-args',
                                help='additional args for cmake building')
            parser.add_argument(
                '--native-build-tool-args',
                help='additional args for the native build tool (generator)')
        if (not skip_build) and (not skip_gen):
            parser.add_argument(
                '--skip-gen',
                action='store_true',
                help="don't generate, assume already generated")
            parser.add_argument('--skip-build',
                                action='store_true',
                                help="don't build, just generate")

    @staticmethod
    def extend_directory():
        return ""

    # should be able to take args from build_default_command_parser
    # build_default_command_parser must be called with has_release=True or
    # forced_base must be set
    def get_directory(self, forced_base=None):
        if self.args.directory is not None:
            return self.args.directory

        if forced_base is None:
            if self.args.release:
                base = "release"
                if self.args.release_debug_info:
                    base += "_deb_info"
            else:
                base = "debug"

        else:
            base = forced_base

        return os.path.join(self.base_build_dir(),
                            base + self.extend_directory())

    def build_add_args(self, parser):
        parser.description = 'build project'
        self.build_default_command_parser(
            parser,
            has_build_testing=self.has_build_testing_default(),
            build_testing_default=self.build_testing_default(),
        )
        parser.add_argument('--target', help='cmake target')

    def build_command(self):
        additional_build_args = None
        if self.args.target is not None:
            additional_build_args = ["--target", self.args.target]

        self.build(self.get_directory(),
                   additional_build_args=additional_build_args)

    def cc_add_args(self, parser):
        parser.description = 'generate compile_commands.json'
        self.build_default_command_parser(parser,
                                          has_release=False,
                                          never_built=True)

    def cc_command(self):
        directory = os.path.join(self.base_build_dir(), "compile_commands_dir")
        if self.args.directory is not None:
            directory = self.args.directory
        self.build(directory,
                   additional_gen_args=["-DCMAKE_EXPORT_COMPILE_COMMANDS=YES"],
                   skip_build=True)
        if os.path.exists("compile_commands.json"):
            print("compile_commands.json exists - not overriding")
        else:
            os.symlink(os.path.join(directory, "compile_commands.json"),
                       "compile_commands.json")

    @staticmethod
    def clean_add_args(parser):
        parser.description = 'clean project'

    def clean_command(self):
        shutil.rmtree(self.base_build_dir(), ignore_errors=True)

    def find_c_family_files_command(self):
        return (
            'fd ' +
            ' '.join(['-e ' + ext
                      for ext in self.c_family_file_extensions()]), ['fd'])

    def check_needed(self, message, needed):
        has_needed = [self.exists_in_path(e) for e in needed]
        if not all(has_needed):
            print(message + "missing: ",
                  ", ".join(e for e, has in zip(needed, has_needed) if has))
            sys.exit(1)  # TODO: don't exit???

    @staticmethod
    def xargs_cmd():
        return 'xargs --no-run-if-empty -n 1'

    # should formatting even be part of this project?
    @staticmethod
    def format_add_args(parser):
        parser.description = 'format code with clang-format'
        parser.add_argument('--clang-format-args', default="-i")

    def base_format_command(self, find_cmd, base_needed):
        needed = ["bash", "clang-format"]
        needed += base_needed
        self.check_needed("can't format, ", needed)
        self.runner([
            'bash', '-c',
            '{0} | {1} clang-format {2}'.format(find_cmd, self.xargs_cmd(),
                                                self.args.clang_format_args)
        ])

    def format_command(self):
        self.base_format_command(*self.find_c_family_files_command())

    def find_staged_c_family_files_cmd(self):
        # use fd to read ignore file
        return ("git diff --cached --name-only --diff-filter=ACMR " + ' '.join(
            ['"*.{}"'.format(ext)
             for ext in self.c_family_file_extensions()]) +
                '| {} fd --fixed-strings --full-path'.format(self.xargs_cmd()),
                ['git', 'fd'])

    @staticmethod
    def staged_format_check_add_args(parser):
        parser.description = 'error if staged files need formating'
        parser.add_argument('--clang-format-args',
                            default="--dry-run --Werror")

    def staged_format_check_command(self):
        self.base_format_command(*self.find_staged_c_family_files_cmd())

    @staticmethod
    def extend_main_parser(_):
        pass

    @staticmethod
    def extend_commands(_):
        pass

    def commands(self):
        commands = {
            "build": (self.build_add_args, self.build_command),
            "compile_commands": (self.cc_add_args, self.cc_command),
            "clean": (self.clean_add_args, self.clean_command),
            "format": (self.format_add_args, self.format_command),
            "staged_format_check": (self.staged_format_check_add_args,
                                    self.staged_format_check_command),
        }
        self.extend_commands(commands)

        return commands

    def build_parser(self):
        parser = argparse.ArgumentParser(
            description='Simple and extensible cmake wrapper',
            # usage="{} [OPTIONS] <COMMAND> [<SUBOPTIONS>]".format(self.name())
        )
        self.extend_main_parser(parser)
        subparsers = parser.add_subparsers(dest="command")
        for command_name, (add_args, _) in self.commands().items():
            add_args(subparsers.add_parser(command_name))

        return parser

    def pick_and_use_sub_command(self):
        commands = self.commands()
        try:
            _, cmd = commands[self.args.command]
        except KeyError:
            print("internal subcommand error: got", self.args.command)
            sys.exit(1)
        cmd()

    def run_with_cli_args(self):
        main_parser = self.build_parser()

        self.args = main_parser.parse_args()

        self.pick_and_use_sub_command()
