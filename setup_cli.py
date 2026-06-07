from setuptools import setup, find_packages

setup(
    name="autoreach-cli",
    version="1.0.0",
    description="AI-powered cold email outreach — CLI version",
    packages=find_packages(include=["cli", "cli.*", "autoreach_core", "autoreach_core.*"]),
    install_requires=[
        "groq>=0.9.0",
        "requests>=2.31.0",
        "beautifulsoup4>=4.12.0",
    ],
    entry_points={
        "console_scripts": [
            "autoreach=cli.main:main",
        ],
    },
    python_requires=">=3.10",
)
