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
import tempfile
import atexit
import shutil
from loguru import logger

version = MAIA.__version__

DESC = dedent("""
    Script to install MAIA on a Kubernetes cluster. This script:
    1. Installs the MAIA Ansible collection
    2. Runs MAIA_Configure_Installation.sh to configure the installation
    3. Executes the MAIA installation playbooks in sequence
    """)
EPILOG = dedent("""
    Example call:
    ::
        {filename} --config-folder /path/to/config
    """.format(filename=Path(__file__).stem))


_SENSITIVE = ("PASSWORD", "SECRET", "TOKEN", "KEY", "PW")


def _loggable(key, value):
    """Mask values of keys that look like credentials before they reach the log."""
    return "***" if any(s in key.upper() for s in _SENSITIVE) else value


def _export_config_env(config_dict):
    """Export config.yaml `env:` values (non-empty, except MAIA_PRIVATE_REGISTRY) to os.environ for the playbooks."""
    for key, value in (config_dict or {}).get("env", {}).items():
        if key != "MAIA_PRIVATE_REGISTRY":
            logger.info(f"Setting environment variable {key} to {_loggable(key, value)}")
            if value is not None and value != "":
                os.environ[key] = value


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

    pars.add_argument(
        "--steps",
        nargs="+",
        default=None,
        help="Steps to run. Default: None. If provided, only the specified steps will be run, overriding the steps in the config.yaml file.",
    )

    pars.add_argument(
        "--upgrade-maia-core",
        action="store_true",
        help="Upgrade MAIA core. Default: False. If provided, the MAIA core will be upgraded.",
    )

    pars.add_argument(
        "--upgrade-maia-admin",
        action="store_true",
        help="Upgrade MAIA admin. Default: False. If provided, the MAIA admin will be upgraded.",
    )

    pars.add_argument(
        "--upgrade-maia-dashboard",
        action="store_true",
        help="Upgrade MAIA dashboard. Default: False. If provided, the MAIA dashboard will be upgraded.",
    )

    pars.add_argument(
        "--auto-sync",
        action="store_true",
        help="Auto sync. Default: False. If provided, the auto sync will be enabled.",
    )

    pars.add_argument("-v", "--version", action="version", version="%(prog)s " + version)

    return pars


def run_command(cmd, check=True, shell=False):
    """Run a shell command and print output."""
    logger.debug(f"Running: {' '.join(cmd) if isinstance(cmd, list) else cmd}")
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
        _export_config_env(config_dict)
    else:
        config_dict = {}

    if args.steps:
        config_dict["steps"] = args.steps
    if args.upgrade_maia_core:
        config_dict["steps"] = ["install_maia_core"]
        config_dict["install_maia_core"] = {"auto_sync": args.auto_sync}
    if args.upgrade_maia_admin:
        config_dict["steps"] = ["install_maia_admin"]
        config_dict["install_maia_admin"] = {"auto_sync": args.auto_sync}
    if args.upgrade_maia_dashboard:
        config_dict["steps"] = ["configure_maia_dashboard"]
        config_dict["configure_maia_dashboard"] = {"auto_sync": args.auto_sync}
    playbooks_dir = "maia.installation"

    # Step 1: Install Ansible collection
    logger.info("\n=== Step 1: Installing Ansible collection ===")
    ansible_galaxy_cmd = [
        "ansible-galaxy",
        "collection",
        "install",
        str(args.ansible_collection_path),
    ]
    try:
        run_command(ansible_galaxy_cmd)
    except subprocess.CalledProcessError as e:
        logger.error(f"Error installing Ansible collection: {e}")
        sys.exit(1)

    inventory_path = args.inventory_path if args.inventory_path else config_folder / "inventory"
    # Step 2: Run MAIA_Configure_Installation.sh
    if not args.skip_configure:
        logger.info("\n=== Step 2: Running MAIA_Configure_Installation.sh ===")
        configure_script = "MAIA_Configure_Installation.sh"

        # Check if env.json exists for no-prompt mode
        env_json = config_folder / "env.json"
        if args.configure_no_prompt:
            if not env_json.exists():
                logger.error(f"Error: --configure-no-prompt requires env.json to exist at {env_json}")
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
            logger.error(f"Error running configuration script: {e}")
            sys.exit(1)
    else:
        logger.info("\n=== Step 2: Skipping MAIA_Configure_Installation.sh ===")

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
            
    # Become password: never on the command line (visible in ps). Pass it through a private 0600 vars
    # file when PW is set; without PW, rely on passwordless sudo (agents, CI).
    become_args = []
    if os.environ.get("PW"):
        become_dir = tempfile.mkdtemp(prefix="maia-become-")
        become_file = Path(become_dir) / "become.json"
        fd = os.open(become_file, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w") as f:
            json.dump({"ansible_become_password": os.environ["PW"]}, f)
        atexit.register(shutil.rmtree, become_dir, ignore_errors=True)
        become_args = ["-e", f"@{become_file}"]
    else:
        logger.info("PW not set: assuming passwordless sudo for the ansible user")
    # Step 3: Run prepare_hosts.yaml
    logger.info("\n=== Step 3: Running prepare_hosts.yaml ===")
    prepare_hosts_cmd = [
        "ansible-playbook",
        "-i",
        str(inventory_path),
        str(playbooks_dir + ".prepare_hosts"),
        *become_args,
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
            logger.error(f"Error running prepare_hosts.yaml: {e}")
            sys.exit(1)
    else:
        logger.info("\n=== Step 3: Skipping prepare_hosts.yaml ===")

    if "selfsigned" in config_dict["cluster_config_extra_env"] and "configure_hosts" in config_dict["steps"]:
        cluster_domain = config_dict["env"]["CLUSTER_DOMAIN"]
        if args.configure_local_host:
            logger.info("\n=== Step 3.1: Running configure_host_linux.yaml for localhost ===")
            target_hosts = "localhost"
            host_ip = "127.0.0.1"
            configure_host_linux_cmd = [
                "ansible-playbook",
                *become_args,
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
            if "proxy_ip" in config_dict["cluster_config_extra_env"]:
                configure_host_linux_cmd.extend(
                    [
                        "-e",
                        f"proxy_ip={config_dict['cluster_config_extra_env']['proxy_ip']}",
                    ]
                )
            if "no_proxy_ips" in config_dict["cluster_config_extra_env"]:
                configure_host_linux_cmd.extend(
                    [
                        "-e",
                        f"no_proxy_ips={config_dict['cluster_config_extra_env']['no_proxy_ips']}",
                    ]
                )
            try:
                run_command(configure_host_linux_cmd)
            except subprocess.CalledProcessError as e:
                logger.error(f"Error running configure_host_linux.yaml: {e}")
                sys.exit(1)
            else:
                logger.info("\n=== Step 3.1: Skipping configure_host_linux.yaml for localhost ===")
        logger.info("\n=== Step 3.2: Running configure_host_linux.yaml for all hosts ===")
        target_hosts = "all"
        configure_host_cmd = [
            "ansible-playbook",
            "-i",
            str(inventory_path),
            str(playbooks_dir + ".configure_host"),
            *become_args,
            "-e",
            f"target_hosts={target_hosts}",
            "-e",
            f"cluster_domain={cluster_domain}",
        ]
        if "proxy_ip" in config_dict["cluster_config_extra_env"]:
            configure_host_cmd.extend(
                [
                    "-e",
                    f"proxy_ip={config_dict['cluster_config_extra_env']['proxy_ip']}",
                ]
            )
        if "no_proxy_ips" in config_dict["cluster_config_extra_env"]:
            configure_host_cmd.extend(
                [
                    "-e",
                    f"no_proxy_ips={config_dict['cluster_config_extra_env']['no_proxy_ips']}",
                ]
            )
        try:
            run_command(configure_host_cmd)
        except subprocess.CalledProcessError as e:
            logger.error(f"Error running configure_host.yaml: {e}")
            sys.exit(1)
        else:
            logger.info("\n=== Step 3.2: Skipping configure_host.yaml for all hosts ===")
    # Step 4: Run install_k8s_distribution.yaml
    logger.info(f"\n=== Step 4: Running install_{os.environ['K8S_DISTRIBUTION']}.yaml ===")
    install_k8s_distribution_cmd = [
        "ansible-playbook",
        "-i",
        str(inventory_path),
        *become_args,
        str(playbooks_dir + f".install_{os.environ['K8S_DISTRIBUTION']}"),
        "-e",
        f"config_folder={config_folder_env}",
    ]
    if f"install_{os.environ['K8S_DISTRIBUTION']}" in config_dict:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as tf:
            if "proxy_ip" in config_dict["cluster_config_extra_env"]:
                config_dict[f"install_{os.environ['K8S_DISTRIBUTION']}"]["proxy_ip"] = config_dict["cluster_config_extra_env"][
                    "proxy_ip"
                ]
            if "no_proxy_ips" in config_dict["cluster_config_extra_env"]:
                config_dict[f"install_{os.environ['K8S_DISTRIBUTION']}"]["no_proxy_ips"] = config_dict[
                    "cluster_config_extra_env"
                ]["no_proxy_ips"]
            yaml.dump(config_dict[f"install_{os.environ['K8S_DISTRIBUTION']}"], tf)
            vars_file = tf.name

        install_k8s_distribution_cmd.extend(["-e", f"@{vars_file}"])
    if "steps" in config_dict and f"install_{os.environ['K8S_DISTRIBUTION']}" in config_dict["steps"]:
        try:
            run_command(install_k8s_distribution_cmd)
        except subprocess.CalledProcessError as e:
            logger.error(f"Error running install_{os.environ['K8S_DISTRIBUTION']}.yaml: {e}")
            sys.exit(1)
    else:
        logger.info(f"\n=== Step 4: Skipping install_{os.environ['K8S_DISTRIBUTION']}.yaml ===")
    # Step 5: Run install_maia_core.yaml
    logger.info("\n=== Step 5: Running install_maia_core.yaml ===")
    install_maia_core_cmd = [
        "ansible-playbook",
        "-i",
        str(inventory_path),
        *become_args,
        str(playbooks_dir + ".install_maia_core"),
        "-e",
        f"config_folder={config_folder_env}",
    ]
    if "install_maia_core" in config_dict:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as tf:
            yaml.dump(config_dict["install_maia_core"], tf)
            vars_file = tf.name

        install_maia_core_cmd.extend(["-e", f"@{vars_file}"])
    if "steps" in config_dict and "install_maia_core" in config_dict["steps"]:
        try:
            run_command(install_maia_core_cmd)
        except subprocess.CalledProcessError as e:
            logger.error(f"Error running install_maia_core.yaml: {e}")
            sys.exit(1)
    else:
        logger.info("\n=== Step 5: Skipping install_maia_core.yaml ===")

    # Step 6: Run install_maia_admin.yaml
    logger.info("\n=== Step 6: Running install_maia_admin.yaml ===")
    install_maia_admin_cmd = [
        "ansible-playbook",
        "-i",
        str(inventory_path),
        *become_args,
        str(playbooks_dir + ".install_maia_admin"),
        "-e",
        f"config_folder={config_folder_env}",
    ]
    if "install_maia_admin" in config_dict:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as tf:
            yaml.dump(config_dict["install_maia_admin"], tf)
            vars_file = tf.name

        install_maia_admin_cmd.extend(["-e", f"@{vars_file}"])
    if "steps" in config_dict and "install_maia_admin" in config_dict["steps"]:
        try:
            run_command(install_maia_admin_cmd)
        except subprocess.CalledProcessError as e:
            logger.error(f"Error running install_maia_admin.yaml: {e}")
            sys.exit(1)
    else:
        logger.info("\n=== Step 6: Skipping install_maia_admin.yaml ===")

    # Step 7: Run configure_oidc_authentication.yaml
    logger.info("\n=== Step 7: Running configure_oidc_authentication.yaml ===")
    configure_oidc_authentication_cmd = [
        "ansible-playbook",
        "-i",
        str(inventory_path),
        *become_args,
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
            logger.error(f"Error running configure_oidc_authentication.yaml: {e}")
            sys.exit(1)
    else:
        logger.info("\n=== Step 7: Skipping configure_oidc_authentication.yaml ===")

    # Step 8: Run get_kubeconfig_from_rancher_local.yaml
    logger.info("\n=== Step 8: Running get_kubeconfig_from_rancher_local.yaml ===")
    get_kubeconfig_from_rancher_local_cmd = [
        "ansible-playbook",
        "-i",
        str(inventory_path),
        *become_args,
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
            logger.error(f"Error running get_kubeconfig_from_rancher_local.yaml: {e}")
            sys.exit(1)
        else:
            logger.info("\n=== Step 8: Skipping get_kubeconfig_from_rancher_local.yaml ===")
    else:
        logger.info("\n=== Step 8: Skipping get_kubeconfig_from_rancher_local.yaml ===")

    # Step 9: Run configure_maia_dashboard.yaml
    logger.info("\n=== Step 9: Running configure_maia_dashboard.yaml ===")
    # install_maia_admin writes env.OPENWEBUI_API_KEY into config.yaml after this process started; re-export the env so
    # that the dashboard gets it in a single run of all steps.
    if Path(config_folder).joinpath("config.yaml").exists():
        _export_config_env(yaml.safe_load(Path(config_folder).joinpath("config.yaml").read_text()))
    configure_maia_dashboard_cmd = [
        "ansible-playbook",
        "-i",
        str(inventory_path),
        *become_args,
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
            logger.error(f"Error running configure_maia_dashboard.yaml: {e}")
            sys.exit(1)
        else:
            logger.info("\n=== Step 9: Skipping configure_maia_dashboard.yaml ===")
    else:
        logger.info("\n=== Step 9: Skipping configure_maia_dashboard.yaml ===")

    logger.info("\n=== MAIA Installation Complete ===")


if __name__ == "__main__":
    main()
