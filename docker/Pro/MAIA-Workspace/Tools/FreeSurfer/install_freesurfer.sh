#!/bin/bash


# Check if FreeSurfer is already installed
INSTALL_DIR="$HOME/freesurfer"  # Change this to your desired directory
export FREESURFER_HOME="${INSTALL_DIR}/freesurfer"

if [ -f "$FREESURFER_HOME/SetUpFreeSurfer.sh" ]; then
    echo "FreeSurfer is already installed."
    source "$FREESURFER_HOME/SetUpFreeSurfer.sh"
    freesurfer --version
    exit 0
fi

# Set variables

TEMP_DIR="${PWD}/tmp/freesurfer_install"
URL="https://surfer.nmr.mgh.harvard.edu/pub/dist/freesurfer/7.4.1/freesurfer-linux-ubuntu22_amd64-7.4.1.tar.gz"
FILE_NAME="freesurfer-linux-ubuntu22_amd64-7.4.1.tar.gz"
MD5_SUM_EXPECTED="4275a307a1a91043587f659389b3e9a8"

# Create the temporary directory
echo "Creating temporary directory at $TEMP_DIR..."
mkdir -p "$TEMP_DIR"

# Change to the temporary directory
cd "$TEMP_DIR" || exit 1

# Step 1: Download the tarball file
echo "Downloading FreeSurfer to $TEMP_DIR..."
wget -O "$FILE_NAME" "$URL"

# Step 2: Verify the MD5 checksum
echo "Verifying checksum..."
MD5_SUM_ACTUAL=$(md5sum "$FILE_NAME" | awk '{print $1}')

if [ "$MD5_SUM_ACTUAL" != "$MD5_SUM_EXPECTED" ]; then
    echo "MD5 checksum verification failed!"
    echo "Expected: $MD5_SUM_EXPECTED"
    echo "Actual: $MD5_SUM_ACTUAL"
    exit 1
fi

echo "Checksum verified successfully."

# Step 3: Extract FreeSurfer to the custom installation directory
echo "Installing FreeSurfer to $INSTALL_DIR..."
mkdir -p "$INSTALL_DIR"
tar -xvzf "$FILE_NAME" -C "$INSTALL_DIR" --strip-components=1

# Step 4: Set up FreeSurfer environment
echo "Setting up FreeSurfer environment..."

source $FREESURFER_HOME/SetUpFreeSurfer.sh

# Step 5: Verify the installation
echo "Verifying FreeSurfer installation..."
freesurfer --version

# Step 6: Clean up
echo "Cleaning up temporary files..."
# rm -rf "$TEMP_DIR"
cp /etc/FreeView.desktop $HOME/Desktop/