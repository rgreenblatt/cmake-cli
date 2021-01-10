import os
import sys
import subprocess

from cmake_cli.base_cmake_builder import BaseCMakeBuilder

def try_run(path):
    if os.path.exists(path):
        sys.exit(subprocess.run([path] + sys.argv[1:], check=False).returncode)

def default_entry_point():
    try_run("./cmake_cli_extend")
    try_run("./.cmake_cli_extend")
    try_run("./scripts/cmake_cli_extend")
    try_run("./scripts/.cmake_cli_extend")
    BaseCMakeBuilder()

if __name__ == "__main__":
    default_entry_point()
