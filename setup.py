#!/usr/bin/env python
# -*- coding: utf-8 -*-

# For a fully annotated version of this file and what it does, see
# https://github.com/pypa/sampleproject/blob/master/setup.py

# To upload this file to PyPI you must build it then upload it:
# python setup.py sdist bdist_wheel  # build in 'dist' folder
# python-m twine upload dist/*  # 'twine' must be installed: 'pip install twine'

import ast
import os
import pathlib
import re
from setuptools import find_packages, setup

DEPENDENCIES = []
with open('requirements/core.txt', 'r') as f:
    DEPENDENCIES = f.read().strip().split('\n')

DEV_DEPENDENCIES = []
with open('requirements/dev.txt', 'r') as f:
    DEV_DEPENDENCIES = f.read().strip().split('\n')

with open('README.md', 'r') as f:
    README = f.read()

CURDIR = os.path.abspath(os.path.dirname(__file__))
def get_version():
    main_file = os.path.join(CURDIR, "harmony", "__init__.py")
    _version_re = re.compile(r"__version__\s+=\s+(?P<version>.*)")
    with open(main_file, "r", encoding="utf8") as f:
        match = _version_re.search(f.read())
        version = match.group("version") if match is not None else '"unknown"'
    return str(ast.literal_eval(version))


setup(
    name='harmony-py',
    version=get_version(),
    description='The NASA Harmony Python library',
    long_description=README,
    long_description_content_type='text/markdown',
    url='https://github.com/nasa/harmony-py',
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Intended Audience :: Developers',
        'Intended Audience :: Science/Research',
        'License :: OSI Approved :: Apache Software License',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
        'Programming Language :: Python :: 3 :: Only',
    ],
    keywords='nasa, harmony, remote-sensing, science, geoscience',
    packages=find_packages(exclude=['tests']),
    python_requires='>=3.6, <4',
    install_requires=DEPENDENCIES,
    extras_require={
        'dev': DEV_DEPENDENCIES,
    },
    include_package_data=True,
    test_suite="tests",
)
