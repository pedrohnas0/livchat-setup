"""Setup script for LivChat Setup"""

from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="livchat-setup",
    version="0.1.0",
    author="LivChat",
    description="Automated server setup and application deployment system",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/livchat/livchat-setup",
    package_dir={"livchat": "src"},
    packages=["livchat"],
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "Topic :: Software Development :: Build Tools",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
    ],
    python_requires=">=3.11",
    install_requires=[
        "pyyaml",
        "hcloud",
        "ansible-core",
        "cryptography",
    ],
    entry_points={
        "console_scripts": [
            "livchat=src.cli:main",
        ],
    },
)