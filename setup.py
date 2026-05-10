"""setup.py -- note use setuptools==73.0.1; older versions fuck up the data files, newer versions include resources."""
from pathlib import Path
from setuptools import setup, find_packages

NAME = "robochan"
VERSION = "0.1"
DESCRIPTION = ("Robochan: middleware for interfacing between generic algorithms (controllers) and robotic platforms and"
               " environments (parrot, gym, robosim etc.)")
URL = "https://gitlab.com/video-representations-extractor/robochan"

CWD = Path(__file__).absolute().parent
with open(CWD/"README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

REQUIRED_CORE = [
    "loggez>=0.8.5",
    "numpy>=1.21",
    "Pillow==11.3.0",
    "overrides==7.7.0",
    "vre-video>=0.5.3",
]

REQUIRED_VENDOR = [
    "parrot-olympe==7.7.5",
    "gymnasium==1.2.3",
    "opencv-python>=4.12.0.88",
    "torch>=2.8.0",
    "ultralytics==8.3.229",
    "video-representations-extractor>=1.17.1",
    "pysdl2-dll==2.32.0",
    "pysdl2==0.9.17",
]

setup(
    name=NAME,
    version=VERSION,
    description=DESCRIPTION,
    long_description=long_description,
    long_description_content_type="text/markdown",
    url=URL,
    packages=find_packages(),
    install_requires=REQUIRED_CORE,
    extras_require={
        "vendor": REQUIRED_VENDOR,
    },
    dependency_links=[],
    license="MIT",
    python_requires=">=3.10",
    scripts=[], # cli/xxx in the future
)
