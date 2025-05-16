# setup.py
from setuptools import setup, find_packages

setup(
    name="LogViewer",
    version="2.0.0",
    packages=find_packages(),
    include_package_data=True,
    entry_points={
        'LogViewer = cli:main'
        ]
    },
    install_requires=[
        "jinja2"
    ],
    package_data={
        "": ["templates/*.html"]
    },
    author="Jason Rojas",
    description="Aruba LogViewer with GUI and web interface",
)
