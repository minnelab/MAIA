#!/usr/bin/env python

import os
import subprocess
from argparse import ArgumentParser, RawTextHelpFormatter
from pathlib import Path
import yaml
from subprocess import PIPE, Popen
from textwrap import dedent

DESC = dedent(
    """
    Script to Generate Basic User Environment in Hive-based Docker Images, including user creation, ssh-key authentication, optional
    FileBrowser, Conda environment and MLFlow Server.
    """  # noqa: E501 W291 W605
)
EPILOG = dedent(
    """
    Example call:
    ::
        {filename} --user <USERNAME> --password <PW> --create-conda "True"
    """.format(  # noqa: E501 W291
        filename=Path(__file__).name
    )
)


def get_arg_parser():
    pars = ArgumentParser(description=DESC, epilog=EPILOG, formatter_class=RawTextHelpFormatter)

    pars.add_argument(
        "--authorized-keys",
        type=str,
        required=False,
        default=None,
        help=" SSH Public keys. If set, SSH is disabled for password authentication.If multiple users, must be a comma-separated list.",
    )

    return pars


def main():
    parser = get_arg_parser()

    args = vars(parser.parse_args())

    if args["authorized_keys"] == None or args["authorized_keys"] == "":
        args["authorized_keys"] = [None]
    else:
        args["authorized_keys"] = args["authorized_keys"].split(",")

    user = "maia-user"
    
    if "ALLOW_PASSWORD_AUTHENTICATION" in os.environ:
        subprocess.run(["sed", "-i", "s/^PasswordAuthentication          no/PasswordAuthentication          yes/", "/opt/ssh/sshd_config"])
    
    for AUTHORIZED_KEYS in args["authorized_keys"]:

        if AUTHORIZED_KEYS is not None and AUTHORIZED_KEYS != "":
            subprocess.run(["mkdir", "-p", "/home/{}/.ssh".format(user)])
            subprocess.run(["chown", "{}".format(user), "/home/{}/.ssh".format(user)])
            subprocess.run(["chmod", "700", "/home/{}/.ssh".format(user)])
            subprocess.run(["touch", "/home/{}/.ssh/authorized_keys".format(user)])
            subprocess.run(["chown", "{}".format(user), "/home/{}/.ssh/authorized_keys".format(user)])
            subprocess.run(["chmod", "600", "/home/{}/.ssh/authorized_keys".format(user)])
            if AUTHORIZED_KEYS != "NOKEY":
                with open("/home/{}/.ssh/authorized_keys".format(user), "a+") as f:
                    subprocess.run(["echo", '{}'.format(AUTHORIZED_KEYS)], stdout=f)

    if "CONDA_ENV" in os.environ:
        env_name = yaml.safe_load(os.environ["CONDA_ENV"])['name']
        if Path(f"/home/{user}/.conda/envs/{env_name}").exists():
            print(f"Conda environment {env_name} already exists.")
            return
           
        with open(f"{env_name}_conda_env.yaml", "w") as f:
            f.write(os.environ["CONDA_ENV"])
        subprocess.run(["/opt/conda/bin/conda", "tos", "accept", "--override-channels", "--channel", "https://repo.anaconda.com/pkgs/main"])
        subprocess.run(["/opt/conda/bin/conda", "tos", "accept", "--override-channels", "--channel", "https://repo.anaconda.com/pkgs/r"])
        subprocess.run(["/opt/conda/bin/conda", "env", "create", "--prefix", f"/home/{user}/.conda/envs/{env_name}", f"--file={env_name}_conda_env.yaml"])
    #    with open("/home/{}/.bashrc".format(user), "a+") as f:
    #        subprocess.run(["echo", "conda","activate","{}".format(env_name)], stdout=f)
        subprocess.run(["/opt/conda/bin/conda", "install", "--prefix", f"/home/{user}/.conda/envs/{env_name}", "-c", "anaconda", "ipykernel", "-y"])
        subprocess.run([f"/home/{user}/.conda/envs/{env_name}/bin/python","-m","ipykernel","install","--user",f"--name={env_name}"])
    if "PIP_ENV" in os.environ:
        with open("pip_env.txt", "w") as f:
            f.write(os.environ["PIP_ENV"])
        subprocess.run(
            ["python", "-m", "pip", "install", "--break-system-packages", "-r", "pip_env.txt"])

if __name__ == "__main__":
    main()
