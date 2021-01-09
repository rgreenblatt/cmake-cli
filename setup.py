import setuptools

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setuptools.setup(
    name="cmake_cli",
    version="0.0.1",
    author="Ryan Greenblatt",
    author_email="ryan_greenblatt@brown.edu",
    description="Simple and extensible cmake wrapper",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/rgreenblatt/cmake_cli",
    packages=setuptools.find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires='>=3.6',
    entry_points = {
        'console_scripts': [
            'cmake_cli = cmake_cli.entry_point:default_entry_point',
        ],
    },
)
