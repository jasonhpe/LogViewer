# setup.py

from setuptools import setup, find_packages
from setuptools.command.install import install
import os
import stat

class CustomInstallCommand(install):
    def run(self):
        install.run(self)
        # Automatically make fastlogParser executable
        try:
            import logviewer
            path = os.path.join(os.path.dirname(logviewer.__file__), "fastlogParser")
            if os.path.exists(path):
                os.chmod(path, os.stat(path).st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
                print(f"✅ Set executable permissions on {path}")
            else:
                print(f"⚠️ fastlogParser not found at {path}")
        except Exception as e:
            print(f"❌ Failed to set executable permission: {e}")

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
        'logviewer': ['fastlogParser', 'README.md']
    },
    cmdclass={
        'install': CustomInstallCommand,
    },
    author='Jason Rojas',
    description='Aruba LogViewer with GUI and web interface',
    classifiers=[
        "Programming Language :: Python :: 3",
        "Operating System :: OS Independent",
    ],
    python_requires='>=3.7',
)
