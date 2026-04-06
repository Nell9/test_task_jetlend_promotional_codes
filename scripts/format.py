import subprocess
import sys


def main():
    commands = [
        ["ruff", "check", "--fix", "."],
        ["isort", "."],
        ["black", "."],
    ]

    for cmd in commands:
        print(f"Running: {' '.join(cmd)}")
        result = subprocess.run(cmd)
        if result.returncode != 0:
            print(f"Command {' '.join(cmd)} failed")
            sys.exit(result.returncode)
    print("Formatting complete!")
