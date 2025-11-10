#!/usr/bin/env python

import os
import subprocess
from argparse import ArgumentParser, RawTextHelpFormatter
from pathlib import Path
from subprocess import PIPE, Popen
from textwrap import dedent

DESC = dedent(
    """
    Script to Generate Basic User Environment in Hive-based Docker Images, including user creation, ssh-key authentication, optional
    FileBrowser and MLFlow Server.
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
        "--user",
        type=str,
        required=True,
        help="Username. If multiple users, must be a comma-separated list.",
    )

    pars.add_argument(
        "--password",
        type=str,
        required=False,
        default=None,
        help="User password. If multiple users, must be a comma-separated list.",
    )


    pars.add_argument(
        "--authorized-keys",
        type=str,
        required=False,
        default=None,
        help=" SSH Public keys. If set, SSH is disabled for password authentication.If multiple users, must be a comma-separated list.",
    )


    pars.add_argument(
        "--run-file-browser",
        type=str,
        required=False,
        default="False",
        help="Flag to install and run FileBrowser.",
    )

    pars.add_argument(
        "--run-mlflow-server",
        type=str,
        required=False,
        default="False",
        help="Flag to run MLFlow Server.",
    )

    return pars


def main():
    parser = get_arg_parser()

    args = vars(parser.parse_args())


    if args["authorized_keys"] == None or args["authorized_keys"] == "":
        args["authorized_keys"] = [None] * len(args["user"].split(","))
    else:
        args["authorized_keys"] = args["authorized_keys"].split(",")

    if args["password"] == None or args["password"] == "":
        args["password"] = args["user"].split(",")
    else:
        args["password"] = args["password"].split(",")


    subprocess.run(["sudo", "chmod", "700", "/etc/ssh/sshd_config"])
    first_uid = 1001
    id = first_uid
    first_user = None
    for user, password, AUTHORIZED_KEYS in zip(args["user"].split(","), args["password"],
                                                      args["authorized_keys"]):
        if first_user is None:
            first_user = user
        subprocess.run(["useradd", "-m", "-s", "/bin/bash", "-u", "{}".format(id), "{}".format(user)])
        proc = Popen(['chpasswd'], stdin=PIPE, stdout=PIPE, stderr=PIPE)
        stdout, stderr = proc.communicate('{}:{}'.format(user, password).encode())
        with open("/etc/sudoers", "a+") as f:
            subprocess.run(["echo", f"{user} ALL=(ALL) NOPASSWD: ALL"], stdout=f)

        subprocess.run(["adduser", "{}".format(user), "sudo"])


        if AUTHORIZED_KEYS is not None and AUTHORIZED_KEYS != "":
            subprocess.run(["mkdir", "-p", "/home/{}/.ssh".format(user)])
            subprocess.run(["chown", "{}".format(user), "/home/{}/.ssh".format(user)])
            subprocess.run(["chmod", "700", "/home/{}/.ssh".format(user)])
            subprocess.run(["touch", "/home/{}/.ssh/authorized_keys".format(user)])
            subprocess.run(["chown", "{}".format(user), "/home/{}/.ssh/authorized_keys".format(user)])
            subprocess.run(["chmod", "600", "/home/{}/.ssh/authorized_keys".format(user)])
            with open("/home/{}/.ssh/authorized_keys".format(user), "a+") as f:
                subprocess.run(["echo", '{}'.format(AUTHORIZED_KEYS)], stdout=f)

            if id == first_uid:
                with open("/etc/ssh/sshd_config", "a+") as f:
                    subprocess.run(["echo", "\nPasswordAuthentication          no"], stdout=f)
                    subprocess.run(["echo", "AuthenticationMethods           publickey"], stdout=f)
        else:
            if id == first_uid:
                with open("/etc/ssh/sshd_config", "a+") as f:
                    subprocess.run(["echo", "\nPasswordAuthentication          yes"], stdout=f)
                    subprocess.run(["echo", "AuthenticationMethods           password"], stdout=f)


        if args["run_file_browser"] == "True":
            if id == first_uid:
                subprocess.run(["mkdir", "/database"])
                with open("/home/{}/filebrowser.sh".format(user), "w") as f:
                    subprocess.run(
                        ["curl", "-fsSL", "https://raw.githubusercontent.com/filebrowser/get/master/get.sh"],
                        stdout=f)
                subprocess.run(
                    ["sudo", "chmod", "+x", "/home/{}/filebrowser.sh".format(user)])
                subprocess.run(["/home/{}/filebrowser.sh".format(user)])
                subprocess.run(["filebrowser", "config", "init", "-d", "/database/filebrowser.db"])

            subprocess.run(["filebrowser", "users", "add", user, password,"--perm.admin", "-d", "/database/filebrowser.db"])

        if args["run_mlflow_server"] != "False":
            if id == first_uid:
                subprocess.run(["pip", "install", "mlflow", "pymysql", "cryptography", "pysftp", "boto3"])
                mysql_service = os.environ["MYSQL_URL"]
                mysql_user = os.environ["MYSQL_USER"]


                bucket_path = "s3://{}/{}".format(os.environ["BUCKET_NAME"],os.environ["BUCKET_PATH"])
                backend_uri = "mysql+pymysql://{}:{}@{}:3306/mysql".format(mysql_user, os.environ["MYSQL_PASSWORD"],
                                                                           mysql_service)
                os.environ["GUNICORN_CMD_ARGS"] = "--timeout 3600"
                subprocess.run(
                    ["mlflow", "server", "--backend-store-uri", "{}".format(backend_uri), "--host", "0.0.0.0", "--port",
                     "5000", "--serve-artifacts","--artifacts-destination", bucket_path])
        id += 1


if __name__ == "__main__":
    main()
