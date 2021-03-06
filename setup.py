#!/usr/bin/env python
from setuptools import setup, find_packages
import os

README_PATH = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'README')

description = '''
feincms-forum simple, modular, easily integrated forum application 
for feincms based sites.
'''

if os.path.exists(README_PATH):
    long_description = open(README_PATH).read()
else:
    long_description = description

setup(name='feincms-forum',
    version='',
    description=description,
    license='BSD',
    url='https://github.com/vencax/feincms-forum',
    author='vencax',
    author_email='vencax@centrum.cz',
    packages=find_packages(),
    install_requires=[
        'django>=1.3',
        'feincms',
        'django-haystack',
        'south',
        'postmarkup',
        'setuptools',
        'django-gravatar',
    ],
    keywords="django feincms forum application",
    include_package_data=True,
)
