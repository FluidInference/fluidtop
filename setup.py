from setuptools import setup, find_packages

long_description = 'Performance monitoring CLI tool for Apple Silicon'

setup(
    name='fluid-top',
    version='0.0.22',
    author='Timothy Liu',
    author_email='tlkh.xms@gmail.com',
    url='https://github.com/FluidInference/fluidtop',
    description='Performance monitoring CLI tool for Apple Silicon',
    long_description=long_description,
    long_description_content_type="text/markdown",
    license='MIT',
    packages=find_packages(),
    entry_points={
            'console_scripts': [
                'fluidtop = fluidtop.fluidtop:main'
            ]
    },
    classifiers=(
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: MacOS",
    ),
    keywords='fluidtop fluid-top',
    install_requires=[
        "click",
        "dashing",
        "psutil",
    ],
    zip_safe=False
)
