import os
from pathlib import Path

from setuptools import setup  # type: ignore

os.chdir(Path(__file__).parent.parent)

setup(
    name="cicada-runner",
    version="0.0.0",
    packages=["cicada-runner"],
    package_dir={"cicada-runner": "runner"},
    install_requires=[
        "cicada-core==0.0.0",
        "websockets==11.0.3",
        "python-dotenv==1.0.0",
    ],
)
