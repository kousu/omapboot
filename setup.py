#!/usr/bin/env python

import sys
import os

try:
    from setuptools import setup
except ImportError:
    from ez_setup import use_setuptools
    use_setuptools()

from setuptools import find_packages, setup

setup(
    name="omapboot",
    version="0.1.0",
    author="Nick Guenther",
    author_email="nguenthe@uwaterloo.ca",
    packages=find_packages(),
    entry_points={
        'console_scripts': [
            'omapboot = omapboot:main',
        ]
    },
    scripts=[],
    description=" .. ",
    long_description=" ... ",
    requires=[
    ],
)
