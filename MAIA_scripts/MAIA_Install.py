#!/usr/bin/env python
from __future__ import annotations

import os
import subprocess
import sys
from argparse import ArgumentParser, RawTextHelpFormatter
from pathlib import Path
from textwrap import dedent

import MAIA
import json
import yaml

version = MAIA.__version__

DESC = dedent(
    """
    Script to install MAIA on a Kubernetes cluster. This script:
    1. Installs the MAIA Ansible collection
    2. Runs MAIA_Configure_Installation.sh to configure the installation
    3. Executes the MAIA installation playbooks in sequence
    """
)
EPILOG = dedent(
    """
    Example call:
    ::
        {filename} --config-folder /path/to/config
    """.format(
        filename=Path(__file__).stem
    )
)


def get_arg_parser():
    pars = ArgumentParser(description=DESC, epilog=EPILOG, formatter_class=RawTextHelpFormatter)

    pars.add_argument(
        "--config-folder",
        type=str,
        required=True,
        help="Configuration folder where MAIA configuration files will be stored.",
    )

    pars.add_argument(
        "--ansible-collection-path",
        type=str,
        default="git+https://github.com/minnelab/MAIA.git#/ansible/MAIA/Installation",
        help="Path to the MAIA Ansible collection directory. Default: git+https://github.com/minnelab/MAIA.git#/ansible/MAIA/Installation",
    )

    pars.add_argument(
        "--inventory-path",
        type=str,
        default=None,
        help="Path where the inventory file will be created. If not provided, defaults to <config-folder>/inventory",
    )

    pars.add_argument(
        "--skip-configure",
        action="store_true",
        help="Skip running MAIA_Configure_Installation.sh. Use this if configuration is already done.",
    )

    pars.add_argument(
        "--configure-local-host",
        action="store_true",
        help="Configure the local host with the subdomain and IP address for self-signed certificates.",
    )

    pars.add_argument(
        "--configure-no-prompt",
        action="store_true",
        help="Run MAIA_Configure_Installation.sh without prompts (requires env.json to exist).",
    )

    pars.add_argument("-v", "--version", action="version", version="%(prog)s " + version)

    return pars


def run_command(cmd, check=True, shell=False):
    """Run a shell command and print output."""
    print(f"Running: {' '.join(cmd) if isinstance(cmd, list) else cmd}")
    if isinstance(cmd, str):
        result = subprocess.run(cmd, shell=True, check=check)
    else:
        result = subprocess.run(cmd, check=check)
    return result


def main():
    parser = get_arg_parser()
    args = parser.parse_args()

    # Resolve paths
    config_folder = Path(args.config_folder).resolve()
    config_folder.mkdir(parents=True, exist_ok=True)

    if Path(config_folder).joinpath("config.yaml").exists():
        config_dict = yaml.safe_load(Path(config_folder).joinpath("config.yaml").read_text())
        os.environ["CONFIG_FOLDER"] = str(config_folder)
        if "env" in config_dict:
            for key, value in config_dict["env"].items():
                if key != "MAIA_PRIVATE_REGISTRY":
                    os.environ[key] = value
    else:
        config_dict = {}

    playbooks_dir = "maia.installation"

    # Step 1: Install Ansible collection
    print("\n=== Step 1: Installing Ansible collection ===")
    ansible_galaxy_cmd = [
        "ansible-galaxy",
        "collection",
        "install",
        str(args.ansible_collection_path),
    ]
    try:
        run_command(ansible_galaxy_cmd)
    except subprocess.CalledProcessError as e:
        print(f"Error installing Ansible collection: {e}")
        sys.exit(1)

    inventory_path = args.inventory_path if args.inventory_path else config_folder / "inventory"
    # Step 2: Run MAIA_Configure_Installation.sh
    if not args.skip_configure:
        print("\n=== Step 2: Running MAIA_Configure_Installation.sh ===")
        configure_script = "MAIA_Configure_Installation.sh"

        # Check if env.json exists for no-prompt mode
        env_json = config_folder / "env.json"
        if args.configure_no_prompt:
            if not env_json.exists():
                print(f"Error: --configure-no-prompt requires env.json to exist at {env_json}")
                sys.exit(1)
            configure_cmd = [str(configure_script), str(env_json)]
        else:
            # Run with prompts
            configure_cmd = [str(configure_script)]
            if env_json.exists():
                configure_cmd.append(str(env_json))

        try:
            # Run the script interactively (allows prompts)
            subprocess.run(configure_cmd, check=True)
        except subprocess.CalledProcessError as e:
            print(f"Error running configuration script: {e}")
            sys.exit(1)
    else:
        print("\n=== Step 2: Skipping MAIA_Configure_Installation.sh ===")

    # Verify config_folder is set (from environment or config)
    if "CONFIG_FOLDER" not in os.environ:
        # Try to get it from env.json if it exists
        env_json = config_folder / "env.json"
        if env_json.exists():
            with open(env_json) as f:
                env_data = json.load(f)
                if "CONFIG_FOLDER" in env_data:
                    os.environ["CONFIG_FOLDER"] = env_data["CONFIG_FOLDER"]
                else:
                    os.environ["CONFIG_FOLDER"] = str(config_folder)
        else:
            os.environ["CONFIG_FOLDER"] = str(config_folder)

    config_folder_env = os.environ["CONFIG_FOLDER"]
    if "cluster_config_extra_env" in config_dict:
        cluster_name = os.environ["CLUSTER_NAME"]
        with open(Path(config_folder_env).joinpath(f"{cluster_name}.yaml"), "r") as f:
            existing_data = yaml.safe_load(f) or {}
            for key, value in config_dict["cluster_config_extra_env"].items():
                existing_data[key] = value
        with open(Path(config_folder_env).joinpath(f"{cluster_name}.yaml"), "w") as f:
            yaml.dump(existing_data, f)
    # Step 3: Run prepare_hosts.yaml
    print("\n=== Step 3: Running prepare_hosts.yaml ===")
    prepare_hosts_cmd = [
        "ansible-playbook",
        "-i",
        str(inventory_path),
        str(playbooks_dir + ".prepare_hosts"),
        "-e",
        f"config_folder={config_folder_env}",
    ]
    if "prepare_hosts" in config_dict:
        for key, value in config_dict["prepare_hosts"].items():
            prepare_hosts_cmd.extend(
                [
                    "-e",
                    f"{key}={value}",
                ]
            )
    if "steps" in config_dict and "prepare_hosts" in config_dict["steps"]:
        try:
            run_command(prepare_hosts_cmd)
        except subprocess.CalledProcessError as e:
            print(f"Error running prepare_hosts.yaml: {e}")
            sys.exit(1)
    else:
        print("\n=== Step 3: Skipping prepare_hosts.yaml ===")

    if "selfsigned" in config_dict["cluster_config_extra_env"] and "configure_hosts" in config_dict["steps"]:
        cluster_domain = config_dict["env"]["CLUSTER_DOMAIN"]
        if args.configure_local_host:
            print("\n=== Step 3.1: Running configure_host_linux.yaml for localhost ===")
            target_hosts = "localhost"        
            host_ip = "127.0.0.1"
            configure_host_linux_cmd = [
                "ansible-playbook",
                "-K",
                "-i",
                str(inventory_path),
                str(playbooks_dir + ".configure_host"),
                "-e",
                f"target_hosts={target_hosts}",
                "-e",
                f"cluster_domain={cluster_domain}",
                "-e",
                f"host_ip={host_ip}",
            ]
            try:
                run_command(configure_host_linux_cmd)
            except subprocess.CalledProcessError as e:
                print(f"Error running configure_host_linux.yaml: {e}")
                sys.exit(1)
            else:
                print("\n=== Step 3.1: Skipping configure_host_linux.yaml for localhost ===")
        print("\n=== Step 3.2: Running configure_host_linux.yaml for all hosts ===")
        target_hosts = "all"
        configure_host_cmd = [
            "ansible-playbook",
            "-i",
            str(inventory_path),
            str(playbooks_dir + ".configure_host"),
            "-e",
            f"target_hosts={target_hosts}",
            "-e",
            f"cluster_domain={cluster_domain}",
        ]
        try:
            run_command(configure_host_cmd)
        except subprocess.CalledProcessError as e:
            print(f"Error running configure_host.yaml: {e}")
            sys.exit(1)
        else:
            print("\n=== Step 3.2: Skipping configure_host.yaml for all hosts ===")
    # Step 4: Run install_microk8s.yaml
    print("\n=== Step 4: Running install_microk8s.yaml ===")
    install_microk8s_cmd = [
        "ansible-playbook",
        "-i",
        str(inventory_path),
        str(playbooks_dir + ".install_microk8s"),
        "-e",
        f"config_folder={config_folder_env}",
    ]
    if "install_microk8s" in config_dict:
        for key, value in config_dict["install_microk8s"].items():
            install_microk8s_cmd.extend(
                [
                    "-e",
                    f"{key}={value}",
                ]
            )
    if "steps" in config_dict and "install_microk8s" in config_dict["steps"]:
        try:
            run_command(install_microk8s_cmd)
        except subprocess.CalledProcessError as e:
            print(f"Error running install_microk8s.yaml: {e}")
            sys.exit(1)
    else:
        print("\n=== Step 4: Skipping install_microk8s.yaml ===")
    # Step 5: Run install_maia_core.yaml
    print("\n=== Step 5: Running install_maia_core.yaml ===")
    install_maia_core_cmd = [
        "ansible-playbook",
        "-i",
        str(inventory_path),
        str(playbooks_dir + ".install_maia_core"),
        "-e",
        f"config_folder={config_folder_env}",
    ]
    if "install_maia_core" in config_dict:
        for key, value in config_dict["install_maia_core"].items():
            install_maia_core_cmd.extend(
                [
                    "-e",
                    f"{key}={value}",
                ]
            )
    if "steps" in config_dict and "install_maia_core" in config_dict["steps"]:
        try:
            run_command(install_maia_core_cmd)
        except subprocess.CalledProcessError as e:
            print(f"Error running install_maia_core.yaml: {e}")
            sys.exit(1)
    else:
        print("\n=== Step 5: Skipping install_maia_core.yaml ===")

    # Step 6: Run install_maia_admin.yaml
    print("\n=== Step 6: Running install_maia_admin.yaml ===")
    install_maia_admin_cmd = [
        "ansible-playbook",
        "-i",
        str(inventory_path),
        str(playbooks_dir + ".install_maia_admin"),
        "-e",
        f"config_folder={config_folder_env}",
    ]
    if "install_maia_admin" in config_dict:
        for key, value in config_dict["install_maia_admin"].items():
            install_maia_admin_cmd.extend(
                [
                    "-e",
                    f"{key}={value}",
                ]
            )
    if "steps" in config_dict and "install_maia_admin" in config_dict["steps"]:
        try:
            run_command(install_maia_admin_cmd)
        except subprocess.CalledProcessError as e:
            print(f"Error running install_maia_admin.yaml: {e}")
            sys.exit(1)
    else:
        print("\n=== Step 6: Skipping install_maia_admin.yaml ===")

    # Step 7: Run configure_oidc_authentication.yaml
    print("\n=== Step 7: Running configure_oidc_authentication.yaml ===")
    configure_oidc_authentication_cmd = [
        "ansible-playbook",
        "-i",
        str(inventory_path),
        str(playbooks_dir + ".configure_oidc_authentication"),
        "-e",
        f"config_folder={config_folder_env}",
    ]
    if "configure_oidc_authentication" in config_dict:
        for key, value in config_dict["configure_oidc_authentication"].items():
            configure_oidc_authentication_cmd.extend(
                [
                    "-e",
                    f"{key}={value}",
                ]
            )
    if "steps" in config_dict and "configure_oidc_authentication" in config_dict["steps"]:
        try:
            run_command(configure_oidc_authentication_cmd)

        except subprocess.CalledProcessError as e:
            print(f"Error running configure_oidc_authentication.yaml: {e}")
            sys.exit(1)
    else:
        print("\n=== Step 7: Skipping configure_oidc_authentication.yaml ===")

    # Step 8: Run get_kubeconfig_from_rancher_local.yaml
    print("\n=== Step 8: Running get_kubeconfig_from_rancher_local.yaml ===")
    get_kubeconfig_from_rancher_local_cmd = [
        "ansible-playbook",
        "-i",
        str(inventory_path),
        str(playbooks_dir + ".get_kubeconfig_from_rancher_local"),
        "-e",
        f"config_folder={config_folder_env}",
    ]
    if "get_kubeconfig_from_rancher_local" in config_dict:
        for key, value in config_dict["get_kubeconfig_from_rancher_local"].items():
            get_kubeconfig_from_rancher_local_cmd.extend(
                [
                    "-e",
                    f"{key}={value}",
                ]
            )
    if "steps" in config_dict and "get_kubeconfig_from_rancher_local" in config_dict["steps"]:
        try:
            run_command(get_kubeconfig_from_rancher_local_cmd)
        except subprocess.CalledProcessError as e:
            print(f"Error running get_kubeconfig_from_rancher_local.yaml: {e}")
            sys.exit(1)
        else:
            print("\n=== Step 8: Skipping get_kubeconfig_from_rancher_local.yaml ===")
    else:
        print("\n=== Step 8: Skipping get_kubeconfig_from_rancher_local.yaml ===")

    # Step 9: Run configure_maia_dashboard.yaml
    print("\n=== Step 9: Running configure_maia_dashboard.yaml ===")
    configure_maia_dashboard_cmd = [
        "ansible-playbook",
        "-i",
        str(inventory_path),
        str(playbooks_dir + ".configure_maia_dashboard"),
        "-e",
        f"config_folder={config_folder_env}",
    ]
    if "configure_maia_dashboard" in config_dict:
        for key, value in config_dict["configure_maia_dashboard"].items():
            configure_maia_dashboard_cmd.extend(
                [
                    "-e",
                    f"{key}={value}",
                ]
            )
    if "steps" in config_dict and "configure_maia_dashboard" in config_dict["steps"]:
        try:
            run_command(configure_maia_dashboard_cmd)
        except subprocess.CalledProcessError as e:
            print(f"Error running configure_maia_dashboard.yaml: {e}")
            sys.exit(1)
        else:
            print("\n=== Step 9: Skipping configure_maia_dashboard.yaml ===")
    else:
        print("\n=== Step 9: Skipping configure_maia_dashboard.yaml ===")

    print("\n=== MAIA Installation Complete ===")


if __name__ == "__main__":
    main()
