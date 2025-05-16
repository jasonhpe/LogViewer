# setup.py

from setuptools import setup, find_packages

setup(
    name='LogViewer',
    version='2.0.0',
    packages=find_packages(),
    include_package_data=True,
    install_requires=[
        'jinja2',
    ],
    entry_points={
        'console_scripts': [
            'LogViewer = cli:main'
        ]
    },
    package_data={
        'LogViewer': ['templates/viewer_template.html']
    },
    author='Jason Rojas',
    description='Aruba LogViewer with GUI and web interface',
)
