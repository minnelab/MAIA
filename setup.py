import os

import setuptools
from setuptools import setup

import versioneer


def resolve_requirements(file):
    requirements = []
    with open(file) as f:
        req = f.read().splitlines()
        for r in req:
            if r.startswith("-r"):
                requirements += resolve_requirements(os.path.join(os.path.dirname(file), r.split(" ")[1]))
            else:
                requirements.append(r)
    return requirements


def read_file(file):
    with open(file) as f:
        content = f.read()
    return content


setup(
    version=versioneer.get_version(),
    packages=setuptools.find_packages(),
    cmdclass=versioneer.get_cmdclass(),
    zip_safe=False,
    data_files=[('', ["requirements.txt"]), ],
    package_data={
        "": ["configs/*.yaml", "configs/*.json", "configs/*.yml","MAIA_scripts/*.sh"],
    },
    scripts=["MAIA_scripts/MAIA_Configure_Installation.sh"],
    entry_points={
        "console_scripts": [
            "MAIA_deploy_helm_chart = MAIA_scripts.MAIA_deploy_helm_chart:main",
            "MAIA_install_admin_toolkit = MAIA_scripts.MAIA_install_admin_toolkit:main",
            "MAIA_install_project_toolkit = MAIA_scripts.MAIA_install_project_toolkit:main",
            "MAIA_install_core_toolkit = MAIA_scripts.MAIA_install_core_toolkit:main",
            "MAIA_create_JupyterHub_config = MAIA_scripts.MAIA_create_JupyterHub_config:main",
            "MAIA_send_welcome_user_email = MAIA_scripts.MAIA_send_welcome_user_email:main",
            "MAIA_send_all_user_email = MAIA_scripts.MAIA_send_all_user_email:main",
            "MAIA_change_keycloak_client_secret = MAIA_scripts.MAIA_change_keycloak_client_secret:main",
            "MAIA_configure_keycloak = MAIA_scripts.MAIA_configure_keycloak:main",
            "MAIA_build_images = MAIA_scripts.MAIA_build_images:main",
            "MAIA_Install = MAIA_scripts.MAIA_Install:main",
        ],
    },
    keywords=["helm", "kubernetes", "maia", "resource deployment"],

)
