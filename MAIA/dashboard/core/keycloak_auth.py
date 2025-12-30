from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed
import requests
import jwt
import time
from django.conf import settings
from apps.models import MAIAUser, User
import threading
from loguru import logger

_jwks_cache = None
_jwks_cache_timestamp = 0
_jwks_cache_lock = threading.Lock()
_JWKS_CACHE_TTL = 300  # seconds
JWKS_TIMEOUT = getattr(settings, "JWKS_TIMEOUT", 10)  # seconds


def get_jwks():
    """
    Retrieve and cache the JSON Web Key Set (JWKS) from Keycloak.
    The JWKS is fetched from ``JWKS_URL`` and cached in-memory for
    ``_JWKS_CACHE_TTL`` seconds. Access to the shared cache is protected
    by ``_jwks_cache_lock`` to ensure thread safety in concurrent
    environments.
    Returns:
        dict[str, Any]: A mapping from Key ID (``kid``) to the corresponding
        public key object built via ``jwt.algorithms.RSAAlgorithm.from_jwk``,
        suitable for verifying RS256-signed tokens issued by Keycloak.
    Raises:
        AuthenticationFailed: If the JWKS cannot be retrieved from the
        Keycloak server or the response cannot be parsed.
    """
    KEYCLOAK_REALM = settings.OIDC_REALM_NAME
    KEYCLOAK_SERVER_URL = settings.OIDC_SERVER_URL
    JWKS_URL = f"{KEYCLOAK_SERVER_URL}/realms/{KEYCLOAK_REALM}/protocol/openid-connect/certs"
    global _jwks_cache, _jwks_cache_timestamp
    now = time.time()
    with _jwks_cache_lock:
        if _jwks_cache is not None and (now - _jwks_cache_timestamp < _JWKS_CACHE_TTL):
            return _jwks_cache
        try:
            ca_bundle = getattr(settings, "OIDC_CA_BUNDLE", None)
            ssl_verification = ca_bundle if ca_bundle else True
            response = requests.get(JWKS_URL, verify=ssl_verification, timeout=JWKS_TIMEOUT)
            response.raise_for_status()
            jwks = response.json()
            public_keys = {jwk["kid"]: jwt.algorithms.RSAAlgorithm.from_jwk(jwk) for jwk in jwks.get("keys", [])}
            _jwks_cache = public_keys
            _jwks_cache_timestamp = now

            return public_keys
        except (requests.RequestException, ValueError) as e:
            # Treat JWKS retrieval/parsing issues as authentication failures
            raise AuthenticationFailed("Unable to fetch JWKS for token verification") from e


class KeycloakAuthentication(BaseAuthentication):
    """
    Django REST Framework authentication backend for validating Keycloak access tokens.
    This backend expects an ``Authorization: Bearer <token>`` header on incoming requests.
    It retrieves the appropriate public key from Keycloak's JWKS endpoint based on the
    token's ``kid`` header, verifies the JWT signature, issuer and audience, and then
    maps the token's ``email`` claim to a ``MAIAUser`` record.
       On successful authentication, :meth:`authenticate` returns a ``(user, auth)`` tuple
    as expected by DRF, where ``auth`` is the authentication credentials. In this
    implementation the validated JWT is not stored or returned, so ``auth`` is always
    ``None``. If the header is missing, malformed, the token is invalid or expired, or
    no corresponding user can be found, it raises
    :class:`rest_framework.exceptions.AuthenticationFailed` or returns ``None`` to allow
    other authentication backends to run.
    """

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
            raise AuthenticationFailed("Invalid token header") from e

        kid = unverified_header.get("kid")
        if not kid:
            raise AuthenticationFailed("Missing key ID in token header")

        public_keys = get_jwks()

        key = public_keys.get(kid)
        if not key:
            raise AuthenticationFailed("Unknown key ID")
        KEYCLOAK_REALM = settings.OIDC_REALM_NAME
        KEYCLOAK_SERVER_URL = settings.OIDC_SERVER_URL
        KEYCLOAK_CLIENT_ID = settings.OIDC_RP_CLIENT_ID
        try:
            payload = jwt.decode(
                token,
                key=key,
                algorithms=["RS256"],
                audience=KEYCLOAK_CLIENT_ID,
                issuer=f"{KEYCLOAK_SERVER_URL}/realms/{KEYCLOAK_REALM}",
                options={"verify_exp": True},
            )
        except jwt.ExpiredSignatureError:
            raise AuthenticationFailed("Token expired")
        except jwt.InvalidTokenError as e:
            raise AuthenticationFailed("Invalid or malformed token") from e

        # Optionally, map Keycloak username/email to Django user
        email = payload.get("email")
        if not email or not isinstance(email, str) or not email.strip():
            raise AuthenticationFailed("Token does not contain an email claim")
        try:
            user = MAIAUser.objects.get(email=email)
        except MAIAUser.DoesNotExist:
            legacy_users_qs = User.objects.filter(email=email)
            if not legacy_users_qs.exists():
                raise AuthenticationFailed("User not found for the provided token")
            namespaces = [settings.USERS_GROUP]
            if legacy_users_qs.first().is_staff and legacy_users_qs.first().is_superuser:
                namespaces.append(settings.ADMIN_GROUP)
            deleted_count, _ = legacy_users_qs.delete()
            if deleted_count > 0:
                logger.warning(
                    "Deleting %d legacy User record(s) for email %s before creating MAIAUser",
                    deleted_count,
                    email,
                )
            user, created = MAIAUser.objects.get_or_create(
                email=email,
                defaults={
                    "username": email,
                    "namespace": ",".join(namespaces),
                    "is_staff": settings.ADMIN_GROUP in namespaces,
                    "is_superuser": settings.ADMIN_GROUP in namespaces,
                }
            )

        return (user, None)
