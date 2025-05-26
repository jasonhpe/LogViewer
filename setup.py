from setuptools import setup, find_packages
from setuptools.command.install import install
import os
import stat
import platform
import shutil

class CustomInstallCommand(install):
    def run(self):
        install.run(self)
        try:
            import logviewer
            root = os.path.dirname(logviewer.__file__)
            fastlog_path = os.path.join(root, "fastlogParser")
            is_windows = platform.system() == "Windows"

            if os.path.exists(fastlog_path):
                if is_windows:
                    # Windows: check WSL
                    if shutil.which("wsl") is None:
                        print(" WSL not found. Fastlog parsing will not work unless WSL is installed.")
                        print(" To install WSL manually (Windows 10+):\n"
                              "1. Open PowerShell as Administrator\n"
                              "2. Run: wsl --install\n"
                              "3. Restart your computer\n"
                              "More: https://aka.ms/wslinstall\n"
                              " Once WSL is installed, you can use fastlogParser from within Windows.\n")
                    else:
                        print(" WSL is available. Fastlog parsing should work via WSL.")
                else:
                    # Linux: set executable bits
                    os.chmod(fastlog_path, os.stat(fastlog_path).st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
                    print(f" Set executable permissions on {fastlog_path}")
            else:
                print(f" fastlogParser not found at {fastlog_path}")
        except Exception as e:
            print(f" Failed during post-install setup: {e}")

setup(
    name='LogViewer',
    version='1.1.0-beta3',
    packages=find_packages(),
    include_package_data=True,
    install_requires=[
        'jinja2',
        'streamlit',
        'pandas',
        'psutil',
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
