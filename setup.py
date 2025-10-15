"""Setup script for LivChat Setup"""

from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="livchat-setup",
    version="0.2.4",
    author="Pedro Nascimento",
    author_email="team@livchat.ai",
    description="Automated server setup and application deployment system with AI control via MCP (v0.2.0: DNS-first architecture)",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/pedrohnas/livchat-setup",
    project_urls={
        "Bug Reports": "https://github.com/pedrohnas/livchat-setup/issues",
        "Source": "https://github.com/pedrohnas/livchat-setup",
    },
    package_dir={"": "src"},
    packages=find_packages(where="src"),
    py_modules=[
        "orchestrator",
        "storage",
        "app_registry",
        "app_deployer",
        "job_manager",
        "job_executor",
        "job_log_manager",
        "ssh_manager",
        "server_setup",
        "ansible_executor",
        "security_utils",
        "cli",
    ],
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "Intended Audience :: System Administrators",
        "Topic :: Software Development :: Build Tools",
        "Topic :: System :: Systems Administration",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
    ],
    python_requires=">=3.11",
    install_requires=[
        "pyyaml>=6.0",
        "hcloud>=1.35.0",
        "ansible-core>=2.16.0",
        "ansible-runner>=2.3.0",
        "cryptography>=41.0.0",
        "jsondiff>=2.2.0",
        "httpx>=0.25.0",
        "tenacity>=8.0.0",
        "cloudflare>=3.0.0",
        "jsonschema>=4.0.0",
        "fastapi>=0.104.0",
        "uvicorn[standard]>=0.24.0",
        "pydantic>=2.0.0",
    ],
    extras_require={
        "dev": [
            "pytest>=7.4.0",
            "pytest-asyncio>=0.21.0",
            "pytest-mock>=3.11.0",
            "pytest-cov>=4.1.0",
            "pytest-timeout>=2.1.0",
        ],
    },
    entry_points={
        "console_scripts": [
            "livchat-setup=cli:main",
        ],
    },
)