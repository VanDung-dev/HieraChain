from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

with open("requirements.txt", "r", encoding="utf-8") as fh:
    requirements = [line.strip() for line in fh.readlines() if line.strip() and not line.startswith("#")]

# Get version from the package
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '.'))
from hierachain.units.version import get_version
from hierachain import VERSION

setup(
    name="HieraChain",
    version=get_version(VERSION),
    author="Nguyễn Lê Văn Dũng",
    description="A HieraChain framework for enterprise applications",
    long_description=long_description,
    long_description_content_type="text/markdown",
    packages=find_packages(include=['hierachain', 'hierachain.*'], exclude=['tests*', 'testing*']),
    install_requires=requirements,
    entry_points={
        "console_scripts": [
            "hbc=hierachain.cli.__init__:hbc",
        ],
    },
    python_requires=">=3.10",
    classifiers=[
        "Development Status :: 2 - Pre-Alpha",
        "Intended Audience :: Developers",
        "Topic :: Software Development :: Libraries :: Application Frameworks",
        "License :: OSI Approved :: Apache Software License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Programming Language :: Python :: 3.13",
    ],
        keywords="blockchain, framework, enterprise, hierarchical",
    project_urls={
        "Bug Reports": "https://github.com/VanDung-dev/HieraChainissues",
        "Source": "https://github.com/VanDung-dev/HieraChain",
    },
)