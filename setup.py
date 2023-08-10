import os
import shutil
from pathlib import Path
from tempfile import TemporaryDirectory

from setuptools import setup  # type: ignore

with TemporaryDirectory() as tmp:
    source_dir = Path(__file__).parent

    tmp = Path(tmp)
    shutil.copytree(source_dir, tmp / "cicada-core")

    os.chdir(tmp)

    setup(
        name="cicada-core",
        version="0.0.0",
        package_dir={"": "cicada-core"},
        packages=[
            "cicada",
            "cicada.ast",
            "cicada.domain",
            "cicada.common",
            "cicada.eval",
            "cicada.eval.builtins",
            "cicada.parse",
        ],
    )
