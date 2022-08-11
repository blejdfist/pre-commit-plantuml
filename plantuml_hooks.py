import os
import hashlib
import tempfile
import functools
import subprocess
import multiprocessing
from pathlib import Path
from urllib.request import urlretrieve
from argparse import ArgumentParser

PLANTUML_DIST = {
    "url": "https://github.com/plantuml/plantuml/releases/download/v1.2022.6/plantuml-1.2022.6.jar",
    "sha256": "204def7102790f55d4adad7756b9c1c19cefcb16e7f7fbc056abb40f8cbe4eae",
}


def get_plantuml_jar_name():
    if "PRE_COMMIT" in os.environ:
        return os.path.join(os.environ["VIRTUAL_ENV"], "bin", "plantuml.jar")
    else:
        raise RuntimeError("It's only supported to run from pre-commit right now")


def parse_arguments():
    parser = ArgumentParser()
    parser.add_argument("files", nargs="*", type=Path)
    return parser.parse_args()


def validate_checksum(filename, checksum):
    sha256 = hashlib.sha256()
    with open(filename, "rb") as jar:
        while True:
            chunk = jar.read(4096)
            if not chunk:
                break
            sha256.update(chunk)

    return sha256.hexdigest() == checksum


def download_plantuml():
    jar_file = get_plantuml_jar_name()
    if os.path.exists(jar_file) and validate_checksum(jar_file, PLANTUML_DIST["sha256"]):
        return jar_file

    urlretrieve(PLANTUML_DIST["url"], jar_file)
    if not validate_checksum(jar_file, PLANTUML_DIST["sha256"]):
        raise RuntimeError("Checksum failed")

    return jar_file


def run_plantuml(jar_file, *args):
    proc = subprocess.run(["java", "-jar", jar_file, "-nometadata"] + list(args))
    return proc.returncode == 0


def generate_svg():
    options = parse_arguments()
    plantuml_jar = download_plantuml()

    puml_files = []

    for puml_file in options.files:
        svg_file = puml_file.with_suffix(".svg")
        if svg_file.exists() and svg_file.lstat().st_mtime > puml_file.lstat().st_mtime:
            # Skip
            continue
        puml_files.append(puml_file)

    if len(puml_files) == 0:
        # Nothing to generate
        return 0

    plantuml = functools.partial(run_plantuml, plantuml_jar, "-tsvg")

    with multiprocessing.Pool() as pool:
        results = pool.map(plantuml, puml_files)
        return 0 if all(results) else 1
