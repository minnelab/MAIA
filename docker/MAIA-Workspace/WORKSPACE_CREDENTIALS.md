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

1. **Security - Password Storage**: 
   - **WARNING**: Storing passwords in plaintext in the `.env` file poses a security risk. The password is stored unencrypted on disk.
   - **Best Practice**: Use strong, unique passwords and ensure the `.env` file has restrictive permissions (mode 600).
   - **Recommended**: Set file permissions immediately after creating the `.env` file:
     ```bash
     chmod 600 ~/.env
     ```
   - **Alternative**: Consider using SSH key-based authentication instead of password authentication when possible.
   - **Important**: Never commit the `.env` file to version control or share it publicly.
   - The `.env` file should be treated as a secret and handled with the same care as SSH private keys.

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

### Password Storage Risk

**⚠️ IMPORTANT**: This feature stores passwords in plaintext in the `$HOME/.env` file, which poses inherent security risks:

1. **Plaintext Storage**: Passwords are stored unencrypted on the filesystem
2. **File System Access**: Anyone with access to your home directory can read the password
3. **Backup Exposure**: The password may be included in filesystem backups
4. **Process Visibility**: The password may be briefly visible in process listings during startup

### Recommended Security Practices

To mitigate these risks:

- **Never commit `.env` files to version control**: Ensure `.env` is listed in your `.gitignore` file
- **Use strong, unique passwords**: Don't reuse passwords from other systems
- **Set restrictive file permissions**: Always use `chmod 600 ~/.env` to limit access to the file owner only
- **Consider alternatives**: 
  - Use SSH key-based authentication instead of passwords when possible
  - Use environment variables set by the orchestration system (e.g., Kubernetes secrets)
  - Use a secrets management system if available in your environment
- **Regular rotation**: Change passwords periodically
- **Monitor access**: Be aware of who has access to your workspace and home directory
- **No sensitive information in logs**: The startup script is designed to never log passwords or other sensitive credentials
- **Secure workspace**: Ensure your workspace itself is properly secured and access-controlled

### Alternative Approaches

For enhanced security, consider these alternatives:

1. **SSH Key Authentication**: Configure SSH keys instead of using password authentication
2. **Kubernetes Secrets**: Use Kubernetes secrets to inject credentials as environment variables
3. **Temporary Passwords**: Use one-time or temporary passwords that expire after first use
4. **External Authentication**: Integrate with external authentication providers (LDAP, OAuth, etc.)

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

For issues or questions related to workspace credential configuration, please refer to the [MAIA documentation](https://maia-toolkit.readthedocs.io/) or open an issue on the [MAIA GitHub repository](https://github.com/minnelab/MAIA).
