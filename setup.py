#!/usr/bin/env python
# -*- coding: utf-8 -*-

# For a fully annotated version of this file and what it does, see
# https://github.com/pypa/sampleproject/blob/master/setup.py

# To upload this file to PyPI you must build it then upload it:
# python setup.py sdist bdist_wheel  # build in 'dist' folder
# python-m twine upload dist/*  # 'twine' must be installed: 'pip install twine'

from setuptools import find_packages, setup
import os
import pathlib


DEPENDENCIES = []
with open('requirements/core.txt', 'r') as f:
    DEPENDENCIES = f.read().strip().split('\n')

DEV_DEPENDENCIES = []
with open('requirements/dev.txt', 'r') as f:
    DEV_DEPENDENCIES = f.read().strip().split('\n')

with open('README.md', 'r') as f:
    README = f.read()

with open('VERSION', 'r') as f:
    VERSION = f.read().strip()


setup(
    name='harmony-py',
    version=VERSION,
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
    package_dir={'': 'harmony'},
    packages=find_packages(where='harmony'),
    python_requires='>=3.6, <4',
    install_requires=DEPENDENCIES,
    extras_require={
        'dev': DEV_DEPENDENCIES,
    },
)