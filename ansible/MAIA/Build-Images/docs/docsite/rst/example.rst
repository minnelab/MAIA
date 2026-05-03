Example: Building MAIA Images
==============================

This section provides examples for building MAIA Docker images and pushing them to different container registries.

Basic Usage
-----------

The simplest way to build images is to use the provided playbook with all required variables:

.. code-block:: bash

    ansible-playbook -i inventory maia.build_images.build_images \
      -e config_folder=/path/to/config \
      -e cluster_name=maia-dev \
      -e GIT_USERNAME=myuser \
      -e GIT_TOKEN=mytoken \
      -e registry_base=https://index.docker.io/v1/ \
      -e registry_path=maiacloudai \
      -e credentials_json_filename=dockerhub-registry-credentials.json \
      -e maia_project_id=maia-image-dockerhub

Example 1: Docker Hub
---------------------

To build and push images to Docker Hub:

.. code-block:: bash

    ansible-playbook -i inventory maia.build_images.build_images \
      -e config_folder=/opt/maia/config \
      -e cluster_name=maia-prod \
      -e GIT_USERNAME=johndoe \
      -e GIT_TOKEN=ghp_xxxxxxxxxxxxx \
      -e registry_base=https://index.docker.io/v1/ \
      -e registry_path=maiacloudai \
      -e credentials_json_filename=dockerhub-registry-credentials.json \
      -e maia_project_id=maia-image-dockerhub

**Prerequisites:**

1. Create Docker Hub credentials file at ``/opt/maia/config/dockerhub-registry-credentials.json``:

.. code-block:: json

    {
      "username": "dockerhub-username",
      "password": "dockerhub-access-token"
    }

2. Ensure ``env.json`` and ``maia-prod.yaml`` exist in ``/opt/maia/config``

Example 2: GitHub Container Registry
-------------------------------------

To build and push images to GitHub Container Registry (ghcr.io):

.. code-block:: bash

    ansible-playbook -i inventory maia.build_images.build_images \
      -e config_folder=/opt/maia/config \
      -e cluster_name=maia-dev \
      -e GIT_USERNAME=janedoe \
      -e GIT_TOKEN=ghp_xxxxxxxxxxxxx \
      -e registry_base=ghcr.io \
      -e registry_path=/minnelab \
      -e credentials_json_filename=github-registry-credentials.json \
      -e maia_project_id=maia-image-github

**Prerequisites:**

1. Create GitHub credentials file at ``/opt/maia/config/github-registry-credentials.json``:

.. code-block:: json

    {
      "username": "github-username",
      "password": "ghp_personal-access-token"
    }

2. Ensure your GitHub personal access token has ``write:packages`` scope
3. Ensure ``env.json`` and ``maia-dev.yaml`` exist in ``/opt/maia/config``

Example 3: Private Registry
----------------------------

To build and push images to a private Harbor or other registry:

.. code-block:: bash

    ansible-playbook -i inventory maia.build_images.build_images \
      -e config_folder=/opt/maia/config \
      -e cluster_name=maia-prod \
      -e GIT_USERNAME=admin \
      -e GIT_TOKEN=xxxxxxxxxxxxx \
      -e registry_base=https://harbor.example.com \
      -e registry_path=/maia-images \
      -e credentials_json_filename=harbor-registry-credentials.json \
      -e maia_project_id=maia-image-harbor

**Prerequisites:**

1. Create Harbor credentials file at ``/opt/maia/config/harbor-registry-credentials.json``:

.. code-block:: json

    {
      "username": "harbor-username",
      "password": "harbor-password"
    }

2. Ensure the Harbor project exists and you have push permissions
3. Ensure ``env.json`` and ``maia-prod.yaml`` exist in ``/opt/maia/config``

Using with Inventory
--------------------

You can also create an inventory file for more complex setups:

**inventory.ini:**

.. code-block:: ini

    [local]
    localhost ansible_connection=local

**Run with inventory:**

.. code-block:: bash

    ansible-playbook -i inventory.ini maia.build_images.build_images \
      -e config_folder=/opt/maia/config \
      -e cluster_name=maia-dev \
      -e GIT_USERNAME=myuser \
      -e GIT_TOKEN=mytoken

Using the Role Directly
------------------------

You can also use the ``build_images`` role directly in your own playbooks:

.. code-block:: yaml

    ---
    - name: Build MAIA images
      hosts: localhost
      vars:
        config_folder: /opt/maia/config
        cluster_name: maia-dev
        GIT_USERNAME: "{{ lookup('env', 'GIT_USERNAME') }}"
        GIT_TOKEN: "{{ lookup('env', 'GIT_TOKEN') }}"
        registry_base: https://index.docker.io/v1/
        registry_path: maiacloudai
        credentials_json_filename: dockerhub-registry-credentials.json
        maia_project_id: maia-image-dockerhub
      vars_files:
        - "{{ config_folder }}/env.json"
        - "{{ config_folder }}/{{ cluster_name }}.yaml"
      roles:
        - maia.build_images.build_images

Environment Variables
---------------------

Instead of passing credentials as command-line arguments, you can set them as environment variables:

.. code-block:: bash

    export GIT_USERNAME=myuser
    export GIT_TOKEN=mytoken
    
    ansible-playbook -i inventory maia.build_images.build_images \
      -e config_folder=/opt/maia/config \
      -e cluster_name=maia-dev \
      -e GIT_USERNAME="{{ lookup('env', 'GIT_USERNAME') }}" \
      -e GIT_TOKEN="{{ lookup('env', 'GIT_TOKEN') }}"

Troubleshooting
---------------

Common Issues
~~~~~~~~~~~~~

**1. Authentication failures:**

- Verify Git credentials have access to MAIA repositories
- Ensure registry credentials are correct and have push permissions
- Check that personal access tokens have not expired

**2. Build failures:**

- Ensure Docker is running and accessible
- Check that ``MAIA_build_images`` command is available in PATH
- Verify ``config_folder`` contains all required configuration files

**3. Push failures:**

- Confirm network connectivity to the registry
- Verify registry path and project exist
- Check disk space on build host and registry

**4. Missing files:**

- Ensure ``env.json`` and ``<cluster_name>.yaml`` exist in ``config_folder``
- Verify credentials JSON file is in ``config_folder`` with correct filename
- Check file permissions for all configuration files

Verbose Output
~~~~~~~~~~~~~~

For detailed output during the build process, run with verbose mode:

.. code-block:: bash

    ansible-playbook -vvv -i inventory maia.build_images.build_images \
      -e config_folder=/opt/maia/config \
      -e cluster_name=maia-dev \
      (... other variables ...)
