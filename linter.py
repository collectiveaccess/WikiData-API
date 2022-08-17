import subprocess


def lint():
    _exec("black main.py")
    _exec("flake8 main.py")


def _exec(command):
    process = subprocess.Popen(command.split())
    output, error = process.communicate()


if __name__ == "__main__":
    lint()
