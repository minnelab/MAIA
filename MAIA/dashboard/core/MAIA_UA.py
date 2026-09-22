import jwt
from django.conf import settings
from django.contrib.auth.models import Group
from django.core.exceptions import SuspiciousOperation
from mozilla_django_oidc.auth import OIDCAuthenticationBackend


class HoneyCombOIDCAB(OIDCAuthenticationBackend):
    # Allow small clock skew between Keycloak and the local host (esp. WSL).
    JWT_LEEWAY_SECONDS = 60

    def _verify_jws(self, payload, key):
        """Same as mozilla_django_oidc, but with leeway for iat/nbf/exp checks."""
        jws = jwt.get_unverified_header(payload)

        try:
            alg = jws["alg"]
        except KeyError:
            raise SuspiciousOperation("No alg value found in header")

        if alg != self.OIDC_RP_SIGN_ALGO:
            raise SuspiciousOperation(
                "The provider algorithm {!r} does not match the client's "
                "OIDC_RP_SIGN_ALGO.".format(alg)
            )

        try:
            return jwt.decode(
                payload,
                key,
                algorithms=alg,
                options={"verify_aud": False},
                leeway=self.JWT_LEEWAY_SECONDS,
            )
        except jwt.DecodeError:
            raise SuspiciousOperation("JWS token verification failed.")

    def verify_claims(self, claims):
        verified = super(HoneyCombOIDCAB, self).verify_claims(claims)
        groups = claims.get("groups", [])
        group_verified = False
        for group in groups:
            if "MAIA:" in group:
                group_verified = True
        return verified and group_verified

    def create_user(self, claims):
        user = super(HoneyCombOIDCAB, self).create_user(claims)

        user.username = claims.get("preferred_username", "")
        user.first_name = claims.get("name", "")
        user.last_name = claims.get("family_name", "")
        user.is_active = True
        groups_id = []
        is_admin = False
        for group in claims.get("groups", []):
            new_group, created = Group.objects.get_or_create(name=group)
            groups_id.append(new_group.id)
            if group == "MAIA:" + settings.ADMIN_GROUP:
                user.is_superuser = True
                is_admin = True
                user.is_staff = True
        if not is_admin:
            user.is_staff = False
            user.is_superuser = False

        user.groups.set(groups_id)
        user.save()

        return user

    def update_user(self, user, claims):
        user.username = claims.get("preferred_username", "")
        user.first_name = claims.get("name", "")
        user.last_name = claims.get("family_name", "")
        user.is_active = True
        groups_id = []
        is_admin = False
        for group in claims.get("groups", []):
            new_group, created = Group.objects.get_or_create(name=group)

            new_group.permissions.add(28)

            groups_id.append(new_group.id)
            if group == "MAIA:" + settings.ADMIN_GROUP:
                user.is_superuser = True
                is_admin = True
                user.is_staff = True

        if not is_admin:
            user.is_staff = False
            user.is_superuser = False
        user.groups.set(groups_id)

        user.save()

        return user
