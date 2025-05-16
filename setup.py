# setup.py

from setuptools import setup, find_packages

setup(
    name='LogViewer',
    version='2.0.0',
    packages=find_packages(),
    install_requires=[
        'jinja2',
    ],
    entry_points={
        'console_scripts': [
            'LogViewer = __main__:main'
        ]
    },
    include_package_data=True,
    author="Jason Rojas",
    description="Aruba LogViewer with GUI and web interface",
)
