from mozilla_django_oidc.auth import OIDCAuthenticationBackend
from django.contrib.auth.models import Group


class HoneyCombOIDCAB(OIDCAuthenticationBackend):
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
            if group == "MAIA:admin":
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
            if group == "MAIA:admin":
                user.is_superuser = True
                is_admin = True
                user.is_staff = True

        if not is_admin:
            user.is_staff = False
            user.is_superuser = False
        user.groups.set(groups_id)

        user.save()

        return user
