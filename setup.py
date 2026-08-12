from setuptools import find_packages, setup


setup(
    name="forgeguard-harness",
    version="0.1.0",
    description="A governed, testable coding-agent harness",
    long_description=open("README.md", encoding="utf-8").read(),
    long_description_content_type="text/markdown",
    packages=find_packages(exclude=("tests", "tests.*")),
    package_data={"forgeguard": ["static/*.html"]},
    include_package_data=True,
    python_requires=">=3.7",
    entry_points={"console_scripts": ["forgeguard=forgeguard.cli:main"]},
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
)
