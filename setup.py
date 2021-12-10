from setuptools import setup, find_packages


def scm_version():
    def local_scheme(version):
        if version.tag and not version.distance:
            return version.format_with("")
        else:
            return version.format_choice("+{node}", "+{node}.dirty")
    return {
        "relative_to": __file__,
        "version_scheme": "guess-next-dev",
        "local_scheme": local_scheme
    }


setup(
    name="amaranth-soc",
    use_scm_version=scm_version(),
    author="whitequark",
    author_email="whitequark@whitequark.org",
    description="System on Chip toolkit for Amaranth HDL",
    #long_description="""TODO""",
    license="BSD",
    setup_requires=["wheel", "setuptools", "setuptools_scm"],
    install_requires=[
        "amaranth>=0.2,<0.5",
        "importlib_metadata; python_version<'3.8'",
    ],
    packages=find_packages(),
    project_urls={
        "Source Code": "https://github.com/amaranth-lang/amaranth-soc",
        "Bug Tracker": "https://github.com/amaranth-lang/amaranth-soc/issues",
    },
)
