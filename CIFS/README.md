# Mount CIFS share on MAIA

To mount a CIFS share on MAIA, you first need to install the `cifs-utils` package on all the nodes that will access the share. This package provides the necessary tools to mount and manage CIFS shares.
```bash
sudo apt-get install cifs-utils
```
## Mounting the Share on RKE 

```bash
#VOLUME_PLUGIN_DIR="/usr/libexec/kubernetes/kubelet-plugins/volume/exec"
VOLUME_PLUGIN_DIR="/var/lib/kubelet/volumeplugins"
mkdir -p "$VOLUME_PLUGIN_DIR/fstab~cifs"
cd "$VOLUME_PLUGIN_DIR/fstab~cifs"
curl -L -O https://raw.githubusercontent.com/minnelab/maia/master/CIFS/cifs
curl -L -O https://raw.githubusercontent.com/minnelab/maia/master/CIFS/decrypt_string.py
chmod 755 cifs
chmod 700 decrypt_string.py
```

Remember to save the private key in the same location, with the name `private_key.pem`. The private key is used to decrypt the credentials for the CIFS share. 

The private key should be set with permissions `644` to ensure that only the owner can read it. You can set the permissions with the following command:

```bash
chmod 644 private_key.pem
```

To check if the installation was successful, run the following command:

```bash
$VOLUME_PLUGIN_DIR/fstab~cifs/cifs init
```

It should output a JSON string containing `"status": "Success"`. This command is also run by Kubernetes itself when the cifs plugin is detected on the file system.

To verify that the CIFS script can correctly execute the decrypt_string.py script, run the following command:

```bash
$VOLUME_PLUGIN_DIR/fstab~cifs/decrypt_string.py
```

## Mounting the Share on MicroK8s

The only difference in the installation process for MicroK8s is the location of the volume plugin directory. For MicroK8s, the directory is located at `/usr/libexec/kubernetes/kubelet-plugins/volume/exec`.
