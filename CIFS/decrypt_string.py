#!/usr/bin/env python

import sys
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives import serialization
from loguru import logger


def decrypt_string(private_key, string):

    with open(private_key, "rb") as f:
        private_key = serialization.load_pem_private_key(f.read(), password=None)

    def decrypt_message(encrypted, private_key):
        decrypted = private_key.decrypt(
            encrypted,
            padding.OAEP(
                mgf=padding.MGF1(algorithm=hashes.SHA256()),
                algorithm=hashes.SHA256(),
                label=None
            )
        )
        return decrypted.decode()

    decrypted_message = decrypt_message(bytes.fromhex(string), private_key)
    
    return decrypted_message
    
    

if __name__ == "__main__":
    if len(sys.argv) != 3:
        logger.error("Usage: decrypt_string.py <private_key.pem> <encrypted_string>")
        sys.exit(1)
    logger.info(decrypt_string(sys.argv[1], sys.argv[2]))