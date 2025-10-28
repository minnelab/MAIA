#!/bin/bash
# Script to update maia-user credentials from $HOME/.env
# This script reads MAIA_USERNAME and MAIA_PASSWORD from $HOME/.env
# and updates the system user accordingly.

# Don't exit on errors - we want to handle them gracefully
set +e

# Define default values
DEFAULT_USER="maia-user"
CURRENT_USER="${USER:-maia-user}"
ENV_FILE="${HOME}/.env"

# Function to log non-sensitive messages
log_info() {
    echo "[INFO] $1"
}

# Function to update username
update_username() {
    local new_username="$1"
    local current_username="$2"
    
    if [ "$new_username" != "$current_username" ]; then
        log_info "Updating username from $current_username to $new_username"
        
        # Remove old sudoers file if it exists
        if [ -f "/etc/sudoers.d/$current_username" ]; then
            sudo rm -f "/etc/sudoers.d/$current_username"
        fi
        # Create new sudoers file for the new user
        echo "$new_username ALL=(ALL) NOPASSWD:ALL" | sudo tee "/etc/sudoers.d/$new_username" > /dev/null
        # Validate the new sudoers file
        sudo visudo -cf "/etc/sudoers.d/$new_username"
        # Set correct permissions
        sudo chmod 0440 "/etc/sudoers.d/$new_username"
        # Update username, home directory, and group
        sudo usermod --login "$new_username" --move-home --home "/home/$new_username" "$current_username" 2>/dev/null || true
        sudo groupmod --new-name "$new_username" "$current_username" 2>/dev/null || true
        sudo usermod -d /home/$current_username $new_username
        
        log_info "Username updated successfully"
    else
        log_info "Username is already set to $new_username"
    fi
}

# Function to update password
update_password() {
    local username="$1"
    local new_password="$2"
    
    if [ -n "$new_password" ]; then
        log_info "Updating password for user $username"
        # Update password without logging it
        echo "$username:$new_password" | sudo chpasswd
        log_info "Password updated successfully"
    fi
}

# Main execution
main() {
    log_info "Starting user credential update process"
    
    # Check if .env file exists
    if [ -f "$ENV_FILE" ]; then
        log_info "Found .env file at $ENV_FILE"
        
        # Source the .env file to read variables
        # Use a subshell to avoid polluting the environment
        # Only remove surrounding quotes, not quotes within the value
        MAIA_USERNAME=$(grep -E "^MAIA_USERNAME=" "$ENV_FILE" 2>/dev/null | cut -d'=' -f2- | sed -e 's/^"\(.*\)"$/\1/' -e "s/^'\(.*\)'$/\1/")
        MAIA_PASSWORD=$(grep -E "^MAIA_PASSWORD=" "$ENV_FILE" 2>/dev/null | cut -d'=' -f2- | sed -e 's/^"\(.*\)"$/\1/' -e "s/^'\(.*\)'$/\1/")
        
        # Update username if specified
        if [ -n "$MAIA_USERNAME" ]; then
            log_info "MAIA_USERNAME found in .env file"
            update_username "$MAIA_USERNAME" "$CURRENT_USER"
            CURRENT_USER="$MAIA_USERNAME"
        else
            log_info "MAIA_USERNAME not found in .env file, using default: $CURRENT_USER"
        fi
        
        # Update password if specified
        if [ -n "$MAIA_PASSWORD" ]; then
            log_info "MAIA_PASSWORD found in .env file"
            update_password "$CURRENT_USER" "$MAIA_PASSWORD"
        else
            log_info "MAIA_PASSWORD not found in .env file, skipping password update"
        fi
    else
        log_info ".env file not found at $ENV_FILE, using defaults"
    fi
    
    log_info "User credential update process completed"
}

# Execute main function
main
