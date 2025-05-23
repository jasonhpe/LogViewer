# setup.py

from setuptools import setup, find_packages

setup(
    name='LogViewer',
    version='1.1.0',
    packages=find_packages(),
    include_package_data=True,
    install_requires=[
        'jinja2',
        'streamlit',
        'pandas',

      
    ],
    entry_points={
        'console_scripts': [
            'LogViewer = logviewer.cli:main'
        ]
    },

    package_data={
        'logviewer': ['templates/*.html', 'README.md']
    },

    
  
    author='Jason Rojas',
    description='Aruba LogViewer with GUI and web interface',

    classifiers=[
        "Programming Language :: Python :: 3",
        "Operating System :: OS Independent",
    ],
    python_requires='>=3.7',
)
