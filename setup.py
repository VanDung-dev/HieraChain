"""
HieraChain - The Hierarchical Blockchain Enterprise Ledger

HieraChain is an enterprise ledger built on hierarchical blockchain technology.
It provides tools and libraries for modeling domains, recording events immutably,
and building secure, decentralized, and scalable enterprise ledgers.
"""

from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

with open("requirements.txt", "r", encoding="utf-8") as fh:
    requirements = [line.strip() for line in fh.readlines() if line.strip() and not line.startswith("#")]

with open("requirements_dev.txt", "r", encoding="utf-8") as fh:
    dev_requirements = [line.strip() for line in fh.readlines() if line.strip() and not line.startswith("#")]

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
    description="A HieraChain Ledger for enterprise applications",
    long_description=long_description,
    long_description_content_type="text/markdown",
    packages=find_packages(include=['hierachain', 'hierachain.*'], exclude=['tests*', 'testing*']),
    install_requires=requirements,
    extras_require={"dev": dev_requirements,},
    entry_points={
        "console_scripts": [
            "hrc=hierachain.cli.__init__:hrc",
        ],
    },
    python_requires=">=3.10",
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "Topic :: Software Development :: Libraries :: Application Ledgers",
        "License :: OSI Approved :: Apache Software License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Programming Language :: Python :: 3.13",
    ],
        keywords="blockchain, Ledger, enterprise, hierarchical",
    project_urls={
        "Bug Reports": "https://github.com/VanDung-dev/HieraChain/issues",
        "Source": "https://github.com/VanDung-dev/HieraChain",
    },
)
