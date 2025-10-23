# MAIA Workspace User Credentials Configuration

## Overview

The MAIA Workspace now supports customizing the default username and password during workspace initialization. This feature allows users to set their preferred credentials by specifying them in a `.env` file located in their home directory.

## How It Works

During workspace startup, the system checks for the existence of `$HOME/.env` and reads the following environment variables:

- `MAIA_USERNAME`: The desired username for the workspace user
- `MAIA_PASSWORD`: The desired password for the workspace user

If these variables are present and valid, the system updates the default "maia-user" username and password accordingly. If the variables are not present or empty, the system falls back to the default configuration.

## Configuration

### Setting Custom Credentials

To set custom credentials, create or edit the `.env` file in your home directory (`$HOME/.env`) and add the following lines:

```bash
MAIA_USERNAME=your-desired-username
MAIA_PASSWORD=your-secure-password
```

**Example:**

```bash
MAIA_USERNAME=john-doe
MAIA_PASSWORD=MySecureP@ssw0rd123
```

### Important Notes

1. **Security**: The `.env` file should be kept secure and not shared publicly. Ensure appropriate file permissions are set:
   ```bash
   chmod 600 ~/.env
   ```

2. **Username Requirements**: The username should follow standard Linux username conventions:
   - Start with a letter
   - Contain only lowercase letters, numbers, hyphens, and underscores
   - Be between 1 and 32 characters long

3. **Password Requirements**: Use a strong password that meets your organization's security policies.

4. **Timing**: The credential update happens during workspace initialization, so you need to set these variables before the workspace starts, or restart the workspace after creating/updating the `.env` file.

5. **Fallback Behavior**: If `MAIA_USERNAME` or `MAIA_PASSWORD` are not specified in the `.env` file, the system will use the default username "maia-user" and the password from the `PASSWD` environment variable (if set).

### Example `.env` File

```bash
# MAIA Workspace Configuration
MAIA_USERNAME=research-user
MAIA_PASSWORD=SecurePassword123!

# Other environment variables can also be defined here
# JUPYTERHUB_POD_NAME will be set automatically
```

## Security Considerations

- **Never commit `.env` files to version control**: Ensure `.env` is listed in your `.gitignore` file
- **Use strong passwords**: Follow best practices for password creation
- **Limit file access**: Set restrictive permissions on the `.env` file (`chmod 600`)
- **No sensitive information in logs**: The startup script is designed to never log passwords or other sensitive credentials

## Troubleshooting

### Credentials not updating

If your credentials are not being updated:

1. Verify the `.env` file exists in your home directory: `ls -la ~/.env`
2. Check the file format - ensure there are no spaces around the `=` sign
3. Verify the environment variables are correctly formatted:
   ```bash
   grep MAIA_ ~/.env
   ```
4. Check the workspace logs for any error messages during startup

### Username conflicts

If the desired username already exists on the system, the update may fail. Choose a unique username that doesn't conflict with system users.

### Permission errors

Ensure you have the necessary permissions to create and modify the `.env` file in your home directory.

## Technical Details

The credential update is handled by the `/etc/update_user_credentials.sh` script, which is automatically executed during workspace initialization via the `/etc/entrypoint.sh` script. The script:

1. Checks for the existence of `$HOME/.env`
2. Parses `MAIA_USERNAME` and `MAIA_PASSWORD` variables
3. Updates the system username and password using `usermod` and `chpasswd`
4. Logs non-sensitive information about the update process
5. Handles errors gracefully without interrupting workspace startup

## Support

For issues or questions related to workspace credential configuration, please refer to the [MAIA documentation](https://maia-toolkit.readthedocs.io/) or open an issue on the [MAIA GitHub repository](https://github.com/kthcloud/MAIA).
