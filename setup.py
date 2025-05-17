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
            'LogViewer = logviewer.cli:main'
        ]
    },
    include_package_data=True,
    package_data={
        'logviewer': ['templates/viewer_template.html']
    },
    author='Jason Rojas',
    description='Aruba LogViewer with GUI and web interface',

    classifiers=[
        "Programming Language :: Python :: 3",
        "Operating System :: OS Independent",
    ],
    python_requires='>=3.7',
)
