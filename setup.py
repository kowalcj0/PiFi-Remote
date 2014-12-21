from setuptools import setup, find_packages  # Always prefer setuptools over distutils
from setuptools.command.install import install
from codecs import open  # To use a consistent encoding
import os
import pifi 

here = os.path.abspath(os.path.dirname(__file__))

class post_install(install):
    def run(self):
        install.run(self)
        print("*** Executing post install actions:")
        # update mpd configuration if necessary
        if not '/tmp/mpd.fifo' in open('/etc/mpd.conf').read():
            os.system("sudo cat /etc/fifo-mpd.conf >> /etc/mpd.conf") 
            os.system("sudo service mpd restart") 
        # update music display init script
        os.system("sudo chmod +x /etc/init.d/pifidisplay")
        os.system("sudo update-rc.d pifidisplay defaults")
        os.system("sudo service pifidisplay restart")
        # update remote control init script
        os.system("sudo chmod +x /etc/init.d/pifiremote")
        os.system("sudo update-rc.d pifiremote defaults")
        os.system("sudo service pifiremote restart") 


# Utility function to read the README file.
# Used for the long_description.  It's nice, because now 1) we have a top level
# README file and 2) it's easier to type in the README file than to put a raw
# string in below ...
def read(fname):
    return open(os.path.join(os.path.dirname(__file__), fname)).read()

setup(
    name='PiFi',

    # Versions should comply with PEP440.  For a discussion on single-sourcing
    # the version across setup.py and the project code, see
    # http://packaging.python.org/en/latest/tutorial.html#version
    version='1.1.4',

    description='Hi Fi music hub on Raspberry Pi',
    long_description='Hi Fi music hub on Raspberry Pi',

    # The project's main homepage.
    url='https://bitbucket.org/bertrandboichon/pi.hifi',

    # Author details
    author='Bertrand Boichon',
    author_email='b.boichon@gmail.com',

    # Choose your license
    license='MIT',

    # See https://pypi.python.org/pypi?%3Aaction=list_classifiers
    classifiers=[
        # How mature is this project? Common values are
        #   3 - Alpha
        #   4 - Beta
        #   5 - Production/Stable
        'Development Status :: 3 - Alpha',

        # Indicate who your project is intended for
        'Intended Audience :: Developers',
        'Topic :: Multimedia :: Sound/Audio :: Players',

        # Pick your license as you wish (should match "license" above)
        'License :: OSI Approved :: MIT License',

        # Specify the Python versions you support here. In particular, ensure
        # that you indicate whether you support Python 2, Python 3 or both.
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 2.6',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.2',
        'Programming Language :: Python :: 3.3',
        'Programming Language :: Python :: 3.4',
    ],

    # What does your project relate to?
    keywords='music hifi mpd raspberry pi rpi',

    # You can just specify the packages manually here if your project is
    # simple. Or you can use find_packages().
    packages=find_packages(exclude=['bin','contrib', 'docs', 'tests*']),

    # List run-time dependencies here.  These will be installed by pip when your
    # project is installed. For an analysis of "install_requires" vs pip's
    # requirements files see:
    # https://packaging.python.org/en/latest/technical.html#install-requires-vs-requirements-files
    install_requires=['python-mpd2',
                    'evdev',
                    'numpy',
                    'RPi.GPIO'],

    # If there are data files included in your packages that need to be
    # installed, specify them here.  If using Python 2.6 or less, then these
    # have to be included in MANIFEST.in as well.
    #package_data={
    #    'sample': ['package_data.dat'],
    #},

    # Although 'package_data' is the preferred approach, in some case you may
    # need to place data files outside of your packages.
    # see http://docs.python.org/3.4/distutils/setupscript.html#installing-additional-files
    # In this case, 'data_file' will be installed into '<sys.prefix>/my_data'
    #data_files=[('my_data', ['data/data_file'])],

    # To provide executable scripts, use entry points in preference to the
    # "scripts" keyword. Entry points provide cross-platform support and allow
    # pip to create the appropriate form of executable for the target platform.
    entry_points={
        'console_scripts': [
            'pifi-display = pifi.PiFiDisplay:main',
            'pifi-remote = pifi.PiFiRemote:main',
        ],
    },
    
    data_files=[
        ('/etc/init.d', ['etc/init.d/pifidisplay']),
        ('/etc/init.d', ['etc/init.d/pifiremote']),
        ('/etc/init.d', ['etc/init.d/shairport']),
        ('/etc',        ['etc/fifo-mpd.conf'])
    ],
    
    cmdclass = {'install': post_install},
)

