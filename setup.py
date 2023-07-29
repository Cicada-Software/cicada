from setuptools import setup  # type: ignore

setup(
    name="cicada",
    version="0.0.0",
    packages=[
        "cicada",
        "cicada.ast",
        "cicada.domain",
        "cicada.common",
        "cicada.eval",
        "cicada.parse",
    ],
)
