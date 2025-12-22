# keycloak_auth.py
from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed
import requests
import jwt
from django.conf import settings
from apps.models import MAIAUser
KEYCLOAK_REALM = settings.OIDC_REALM_NAME
KEYCLOAK_SERVER_URL = settings.OIDC_SERVER_URL
KEYCLOAK_CLIENT_ID = settings.OIDC_RP_CLIENT_ID

# Fetch Keycloak JWKS (public keys)
JWKS_URL = f"{KEYCLOAK_SERVER_URL}/realms/{KEYCLOAK_REALM}/protocol/openid-connect/certs"

class KeycloakAuthentication(BaseAuthentication):
    def authenticate(self, request):
        auth_header = request.headers.get("Authorization")
        if not auth_header:
            return None  # DRF will handle as unauthenticated

        parts = auth_header.split()
        if len(parts) != 2 or parts[0].lower() != "bearer":
            raise AuthenticationFailed("Invalid Authorization header. Expected format: 'Bearer <token>'.")

        token = parts[1]

        # Decode header to find which key to use
        try:  
            unverified_header = jwt.get_unverified_header(token)  
        except jwt.InvalidTokenError as e:  
            raise AuthenticationFailed(f"Invalid token header: {str(e)}")  

        kid = unverified_header.get("kid")  
        if not kid:  
            raise AuthenticationFailed("Missing key ID in token header")  

        try:  
            #verify_param = False #"/etc/MAIA/ca.crt"#getattr(settings, "OIDC_CA_BUNDLE", True)
            response = requests.get(JWKS_URL, verify=False, timeout=5)  
            response.raise_for_status()  
            jwks = response.json()
        except (requests.RequestException, ValueError) as e:  
            # Treat JWKS retrieval/parsing issues as authentication failures  
            raise AuthenticationFailed("Unable to fetch JWKS for token verification") from e  

        public_keys = {jwk["kid"]: jwt.algorithms.RSAAlgorithm.from_jwk(jwk) for jwk in jwks.get("keys", [])}  

        key = public_keys.get(kid)
        if not key:
            raise AuthenticationFailed("Unknown key ID")

        try:
            payload = jwt.decode(
                token,
                key=key,
                algorithms=["RS256"],
                audience=KEYCLOAK_CLIENT_ID,
                issuer=f"{KEYCLOAK_SERVER_URL}/realms/{KEYCLOAK_REALM}"
            )
        except jwt.ExpiredSignatureError:
            raise AuthenticationFailed("Token expired")
        except jwt.InvalidTokenError as e:
            raise AuthenticationFailed(f"Invalid token: {str(e)}")

        # Optionally, map Keycloak username/email to Django user
        email = payload.get("email")  
        if not email:  
            raise AuthenticationFailed("Token does not contain an email claim")  
        try:  
            user = MAIAUser.objects.get(email=email)  
        except MAIAUser.DoesNotExist:  
            raise AuthenticationFailed("User not found for the provided token")
        return (user, None)
