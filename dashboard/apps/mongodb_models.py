# apps/documents.py
import hashlib
import os
import threading
from datetime import date, datetime, time, timezone
from django.conf import settings
from django.core.exceptions import ValidationError
from loguru import logger

# ─── collection ───────────────────────────────────────────────────────────────
_col = None
_col_lock = threading.Lock()


def get_collection():
    global _col
    if _col is None:
        with _col_lock:
            if _col is None:
                _col = settings.MONGO_DB["maia_users"]
                # indexes
                _col.create_index("email", unique=True)
                _col.create_index("username", unique=True, sparse=True)
    return _col


# ─── meta "mock" for Django compatibility ─────────────────────────────────────
class _FakeField:
    """
    Simple mock field to mimic Django's model field interface for compatibility
    with forms/models internals that expect .name, .attname, etc.
    Implements __lt__ for sorting compatibility with Django forms/models.
    Also provides a simple .formfield method for Django form compatibility.
    Also provides has_default() method for Django compatibility.
    Provides save_form_data for model form compatibility.
    """

    def __init__(self, name, blank=False, default=None):
        self.name = name
        self.attname = name
        self.is_relation = False
        self.many_to_one = False
        self.many_to_many = False
        self.editable = True
        self.remote_field = None
        self.blank = blank

        # For compatibility with Django fields
        self.default = default
        self._has_default = default is not None

    def __lt__(self, other):
        # Allow Django's `sorted()`/ordering to work by name
        if isinstance(other, _FakeField):
            return self.name < other.name
        return NotImplemented

    def has_default(self):
        return self._has_default

    def formfield(self, **kwargs):
        from django import forms

        # Determine blank status: accept kwarg override but default to self.blank
        blank = kwargs.get("blank", self.blank)
        # Attempt to guess field type by name
        if self.name in {"email", "supervisor"}:
            return forms.EmailField(required=not blank)
        elif self.name == "username":
            return forms.CharField(required=not blank)
        elif self.name in {"is_active", "is_staff", "is_superuser", "is_anonymous", "is_authenticated", "auto_deploy"}:
            return forms.BooleanField(required=False)
        elif self.name in {"last_login", "date_joined", "created_at", "updated_at", "date"}:
            return forms.DateTimeField(required=False)
        elif self.name in {"users", "auto_deploy_apps", "project_configuration", "email_to_username_map"}:
            return forms.JSONField(required=not blank)
        else:
            return forms.CharField(required=not blank)

    # For Django model/form compatibility: apply cleaned_data value to the instance
    def save_form_data(self, instance, data):
        setattr(instance, self.name, data)


class _MAIAUserMeta:
    """
    Minimal _meta object to satisfy Django admin/forms expectations.
    """

    def __init__(self):
        self.model_name = "maiauser"
        self.app_label = "dashboard"
        # Create list of mock field objects
        field_names = [
            "id",
            "email",
            "username",
            "namespace",
            "password",
            "is_active",
            "is_staff",
            "is_superuser",
            "is_anonymous",
            "is_authenticated",
            "last_login",
            "date_joined",
            "created_at",
            "updated_at",
        ]
        self.fields = [_FakeField(name) for name in field_names]
        self.concrete_fields = self.fields
        self.private_fields = []
        self.many_to_many = []
        self.many_to_one = []

    @property
    def object_name(self):
        return "MAIAUser"

    @property
    def verbose_name(self):
        return "MAIA User"

    @property
    def verbose_name_plural(self):
        return "MAIA Users"

    def get_fields(self):
        return self.fields


# ─── exceptions (mirror Django) ───────────────────────────────────────────────
class DoesNotExist(Exception):
    pass


class MultipleObjectsReturned(Exception):
    pass


# ─── QuerySet-like class ───────────────────────────────────────────────────────
class MAIAUserQuerySet:
    def __init__(self, query=None, projection=None, sort=None, limit_val=None, skip_val=None, for_update=False):
        self._query = query or {}
        self._projection = projection
        self._sort = sort
        self._limit_val = limit_val
        self._skip_val = skip_val
        self._for_update = for_update  # stored but MongoDB has no row locks
        self._cache = None

    # ── internal ──────────────────────────────────────────────────────────────
    def _clone(self, **overrides):
        return MAIAUserQuerySet(
            query=overrides.get("query", dict(self._query)),
            projection=overrides.get("projection", self._projection),
            sort=overrides.get("sort", self._sort),
            limit_val=overrides.get("limit_val", self._limit_val),
            skip_val=overrides.get("skip_val", self._skip_val),
            for_update=overrides.get("for_update", self._for_update),
        )

    def _fetch(self):
        if self._cache is None:
            col = get_collection()
            cursor = col.find(self._query, self._projection)
            if self._sort:
                cursor = cursor.sort(self._sort)
            if self._skip_val:
                cursor = cursor.skip(self._skip_val)
            if self._limit_val:
                cursor = cursor.limit(self._limit_val)
            self._cache = [MAIAUser._from_doc(d) for d in cursor]
        return self._cache

    # ── chaining ──────────────────────────────────────────────────────────────
    def filter(self, **kwargs):
        q = {**self._query, **MAIAUser._build_query(kwargs)}
        return self._clone(query=q)

    def exclude(self, **kwargs):
        q = dict(self._query)
        for k, v in MAIAUser._build_query(kwargs).items():
            q[k] = {"$ne": v}
        return self._clone(query=q)

    def order_by(self, *fields):
        sort = []
        for f in fields:
            if f.startswith("-"):
                sort.append((f[1:], -1))
            else:
                sort.append((f, 1))
        return self._clone(sort=sort)

    def only(self, *fields):
        return self._clone(projection={f: 1 for f in fields})

    def defer(self, *fields):
        return self._clone(projection={f: 0 for f in fields})

    def select_for_update(self, **kwargs):
        # MongoDB has no pessimistic row locks; we flag it for awareness
        return self._clone(for_update=True)

    def distinct(self, field):
        return get_collection().distinct(field, self._query)

    def values(self, *fields):
        proj = {f: 1 for f in fields} if fields else None
        cursor = get_collection().find(self._query, proj)
        return [{k: v for k, v in doc.items() if k != "_id"} for doc in cursor]

    def values_list(self, *fields, flat=False):
        rows = self.values(*fields)
        if flat and len(fields) == 1:
            return [r[fields[0]] for r in rows]
        return [tuple(r[f] for f in fields) for r in rows]

    def count(self):
        return get_collection().count_documents(self._query)

    def exists(self):
        return get_collection().count_documents(self._query, limit=1) > 0

    def first(self):
        results = self._fetch()
        return results[0] if results else None

    def last(self):
        results = self._fetch()
        return results[-1] if results else None

    def none(self):
        # Use the MongoDB id field
        return self._clone(query={"id": {"$exists": False}})

    def all(self):
        return self._clone()

    def limit(self, n):
        return self._clone(limit_val=n)

    def offset(self, n):
        return self._clone(skip_val=n)

    # alias
    def __getitem__(self, key):
        if isinstance(key, slice):
            qs = self._clone(
                skip_val=key.start or 0,
                limit_val=(key.stop - (key.start or 0)) if key.stop else None,
            )
            return qs._fetch()
        return self._fetch()[key]

    def __iter__(self):
        return iter(self._fetch())

    def __len__(self):
        return len(self._fetch())

    def __repr__(self):
        return f"<MAIAUserQuerySet {self._fetch()}>"

    # ── terminal ──────────────────────────────────────────────────────────────
    def get(self, **kwargs):
        qs = self.filter(**kwargs) if kwargs else self
        results = qs._fetch()
        if len(results) == 0:
            raise MAIAUser.DoesNotExist("MAIAUser matching query does not exist.")
        if len(results) > 1:
            raise MAIAUser.MultipleObjectsReturned("get() returned more than one MAIAUser.")
        return results[0]

    def get_or_create(self, defaults=None, **kwargs):
        col = get_collection()
        query = MAIAUser._build_query(kwargs)
        doc = col.find_one(query)
        if doc:
            return MAIAUser._from_doc(doc), False
        data = {**kwargs, **(defaults or {})}
        user = MAIAUser(**data)
        user.save()
        return user, True

    def update_or_create(self, defaults=None, **kwargs):
        col = get_collection()
        query = MAIAUser._build_query(kwargs)
        update = {"$set": {**kwargs, **(defaults or {}), "updated_at": datetime.now(timezone.utc)}}
        result = col.find_one_and_update(query, update, upsert=True, return_document=True)
        return MAIAUser._from_doc(result), result is None

    def update(self, **kwargs):
        """
        Updates documents matching the current query set in MongoDB.
        Returns the number of documents modified.
        """
        if not kwargs:
            # Nothing to update, simply return 0
            return 0
        kwargs["updated_at"] = datetime.now(timezone.utc)
        update_result = get_collection().update_many(self._query, {"$set": kwargs})

        # If no documents matched and nothing was modified, consider raising or logging
        if update_result.matched_count == 0:
            # No documents matched the filter
            # You may add logging here if needed
            logger.error("No documents matched the filter")
            pass
        return update_result.modified_count

    def delete(self):
        result = get_collection().delete_many(self._query)
        return result.deleted_count, {"MAIAUser": result.deleted_count}

    def bulk_create(self, users):
        docs = [u._to_doc() for u in users]
        result = get_collection().insert_many(docs)
        for user, oid in zip(users, result.inserted_ids):
            user.id = oid
        return users

    def bulk_update(self, users, fields):
        from pymongo import UpdateOne

        ops = [UpdateOne({"_id": u.id}, {"$set": {f: getattr(u, f) for f in fields}}) for u in users]
        return get_collection().bulk_write(ops).modified_count

    def in_bulk(self, id_list=None, field_name="id"):
        query = dict(self._query)
        # Convert to Mongo _id for querying
        if id_list is not None:
            if field_name == "id":
                query["_id"] = {"$in": id_list}
            else:
                query[field_name] = {"$in": id_list}
        return {str(u.id): u for u in (MAIAUser._from_doc(d) for d in get_collection().find(query))}

    def iterator(self, chunk_size=100):
        col = get_collection()
        cursor = col.find(self._query).batch_size(chunk_size)
        for doc in cursor:
            yield MAIAUser._from_doc(doc)

    def aggregate(self, pipeline):
        return list(get_collection().aggregate(pipeline))


# ─── Manager ──────────────────────────────────────────────────────────────────
class MAIAUserManager:
    def get_queryset(self):
        return MAIAUserQuerySet()

    def create(self, **kwargs):
        user = MAIAUser(**kwargs)
        user.save()
        return user

    def __getattr__(self, name):
        return getattr(self.get_queryset(), name)

    # ── user-specific factory methods ─────────────────────────────────────────
    def create_user(self, email, namespace, password=None, username=None, **extra):
        if not email:
            raise ValueError("email is required")
        user = MAIAUser(email=email.lower().strip(), namespace=namespace, username=username, **extra)
        user.set_password(password)
        user.save()
        return user

    def create_superuser(self, email, namespace, password, username=None, **extra):
        extra.setdefault("is_staff", True)
        extra.setdefault("is_superuser", True)
        extra.setdefault("is_active", True)
        return self.create_user(email, namespace, password, username=username, **extra)

    def active(self):
        return self.get_queryset().filter(is_active=True)

    def admins(self):
        return self.get_queryset().filter(is_superuser=True)


# ─── MAIAUser ─────────────────────────────────────────────────────────────────
class MAIAUser:
    DoesNotExist = DoesNotExist
    MultipleObjectsReturned = MultipleObjectsReturned
    objects = MAIAUserManager()

    _meta = _MAIAUserMeta()  # <-- This will satisfy Django forms/models.py expectations

    REQUIRED_FIELDS = ["email", "username"]
    USERNAME_FIELD = "username"

    def __init__(
        self,
        email=None,
        username=None,
        namespace="",
        password=None,
        is_active=True,
        is_staff=False,
        is_superuser=False,
        is_anonymous=False,
        is_authenticated=True,
        last_login=None,
        date_joined=None,
        id=None,
        **extra_fields,
    ):
        self.id = id
        self.email = email.lower().strip() if email else email
        self.username = username
        self.namespace = namespace
        self.password = password  # stored as hash
        self.is_active = is_active
        self.is_staff = is_staff
        self.is_superuser = is_superuser
        self.is_anonymous = is_anonymous
        self.is_authenticated = is_authenticated
        self.last_login = last_login
        self.date_joined = date_joined or datetime.now(timezone.utc)
        self.created_at = datetime.now(timezone.utc)
        self.updated_at = datetime.now(timezone.utc)
        for k, v in extra_fields.items():
            setattr(self, k, v)

        # Track clean/validation errors for form use
        self._errors = {}

    @property
    def pk(self):
        """Primary key alias for Django/DRF compatibility (e.g. UserRateThrottle)."""
        return self.id

    @pk.setter
    def pk(self, value):
        self.id = value

    # ── Add Django-compatible unique_error_message for form compatibility ─────
    def unique_error_message(self, model_class, unique_check):
        """
        Provide a Django-compatible unique_error_message hook,
        so that django.contrib.admin and forms handle unique errors gracefully.
        Returns a string message for backward compatibility with code paths
        expecting a `error_list` attribute on the result.
        """
        if not unique_check:
            return ""
        field = unique_check[0]
        if field == "username":
            msg = "A user with that username already exists."
        else:
            msg = "A user with this value already exists."
        # Return just the message string, not ValidationError object, for compatibility
        return msg

    # ── Django-compatible clean/full_clean stubs for ModelForm compatibility ──
    def clean(self):
        """
        This method is called during form/model validation.
        Accumulate validation errors in self._errors.
        """
        self._errors = {}
        # Enforce required fields even though `__init__` must tolerate None
        # for Django form construction on GET requests.
        if not self.email:
            self._errors["email"] = "This field is required."
        if not self.username:
            self._errors["username"] = "This field is required."

    def full_clean(self, exclude=None, validate_unique=True):
        """Stub method to support Django ModelForm compatibility.

        Args:
            exclude: Fields to exclude from validation.
            validate_unique: Whether to validate uniqueness.
        Returns:
            cleaned_data: Always returns cleaned_data dict with email, username, namespace.
        Raises:
            ValidationError: If there are validation errors (but always returns cleaned data).
        """
        self.clean()
        unique_errors = self.validate_unique(exclude=exclude) or {}

        if unique_errors:
            # Merge unique errors to main errors dict
            self._errors.update(unique_errors)

        # Determine if there's a validation error to handle just before raising.
        if self._errors:
            # Preserve submitted values so form.cleaned_data still contains
            # user input when validation fails (e.g. unique constraint errors).
            error = ValidationError(self._errors)
            raise error

        # Otherwise, normal cleaned_data
        cleaned_data = {
            "email": self.email,
            "username": self.username,
            "namespace": self.namespace,
        }

        return cleaned_data

    # ── Add Django-compatible validate_unique for ModelForm compatibility ──────
    def validate_unique(self, exclude=None):
        """
        Django-compatible method to check for unique field violations.
        Used by ModelForms and Django admin.
        Attaches errors to the instance for form display and prevents submission if errors exist.
        """
        unique_errors = {}

        exclude = set(exclude or [])

        # Only check if not excluded
        if "username" not in exclude and self.username:
            qs = type(self).objects.filter(username=self.username)
            if self.id is not None:
                qs = qs.exclude(id=self.id)
            if qs.exists():
                unique_errors["username"] = self.unique_error_message(type(self), ["username"])
        # Other unique checks can be added if needed

        return unique_errors

    # ── password ──────────────────────────────────────────────────────────────
    def set_password(self, raw_password):
        if raw_password is None:
            self.password = None
            return
        salt = os.urandom(16).hex()
        hashed = hashlib.sha256(f"{salt}{raw_password}".encode()).hexdigest()
        self.password = f"sha256${salt}${hashed}"

    def check_password(self, raw_password):
        if not self.password:
            return False
        try:
            _, salt, hashed = self.password.split("$")
        except ValueError:
            return False
        return hashlib.sha256(f"{salt}{raw_password}".encode()).hexdigest() == hashed

    def has_perm(self, perm, obj=None):
        return self.is_active and self.is_superuser

    def has_perms(self, perm_list, obj=None):
        return all(self.has_perm(p, obj) for p in perm_list)

    def has_module_perms(self, app_label):
        return self.is_active and self.is_superuser

    # ── persistence ───────────────────────────────────────────────────────────
    def _to_doc(self):
        doc = {
            "email": self.email,
            "namespace": self.namespace,
            "password": self.password,
            "is_active": self.is_active,
            "is_staff": self.is_staff,
            "is_superuser": self.is_superuser,
            "is_anonymous": self.is_anonymous,
            "is_authenticated": self.is_authenticated,
            "last_login": self.last_login,
            "date_joined": self.date_joined,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }
        if self.username is not None:
            doc["username"] = self.username
        if self.id:
            doc["_id"] = self.id
        return doc

    @classmethod
    def _from_doc(cls, doc):
        d = dict(doc)
        id_val = d.pop("_id", None)
        return cls(
            id=id_val,
            email=d.pop("email", ""),
            username=d.pop("username", None),
            namespace=d.pop("namespace", ""),
            password=d.pop("password", None),
            is_active=d.pop("is_active", True),
            is_staff=d.pop("is_staff", False),
            is_superuser=d.pop("is_superuser", False),
            is_anonymous=d.pop("is_anonymous", False),
            is_authenticated=d.pop("is_authenticated", True),
            last_login=d.pop("last_login", None),
            date_joined=d.pop("date_joined", None),
            **d,  # any extra fields stored in mongo
        )

    @classmethod
    def _build_query(cls, kwargs):
        """Translate Django-style lookups to MongoDB queries."""
        OPERATORS = {
            "gt": "$gt",
            "gte": "$gte",
            "lt": "$lt",
            "lte": "$lte",
            "ne": "$ne",
            "in": "$in",
            "nin": "$nin",
            "exists": "$exists",
        }
        query = {}
        for key, value in kwargs.items():
            parts = key.split("__")
            field = parts[0]
            op = parts[1] if len(parts) > 1 else None
            # If user searched by 'id', convert to MongoDB's '_id'
            mongo_field = "_id" if field == "id" else field
            if op == "iexact" or op == "icontains":
                query[mongo_field] = {"$regex": value, "$options": "i"}
            elif op == "contains":
                query[mongo_field] = {"$regex": value}
            elif op == "startswith":
                query[mongo_field] = {"$regex": f"^{value}"}
            elif op == "endswith":
                query[mongo_field] = {"$regex": f"{value}$"}
            elif op == "isnull":
                query[mongo_field] = None if value else {"$ne": None}
            elif op in OPERATORS:
                query[mongo_field] = {OPERATORS[op]: value}
            else:
                query[mongo_field] = value
        return query

    def save(self):
        col = get_collection()
        self.updated_at = datetime.now(timezone.utc)
        doc = self._to_doc()
        if self.id:
            col.update_one({"_id": self.id}, {"$set": doc})
        else:
            result = col.insert_one(doc)
            self.id = result.inserted_id
        return self

    def delete(self):
        if self.id:
            get_collection().delete_one({"_id": self.id})
            self.id = None

    def refresh_from_db(self):
        doc = get_collection().find_one({"_id": self.id})
        if not doc:
            raise DoesNotExist("MAIAUser no longer exists in MongoDB.")
        updated = MAIAUser._from_doc(doc)
        self.__dict__.update(updated.__dict__)

    def update_last_login(self):
        self.last_login = datetime.now(timezone.utc)
        get_collection().update_one({"_id": self.id}, {"$set": {"last_login": self.last_login}})

    # ── dunder ────────────────────────────────────────────────────────────────
    def __str__(self):
        return f"MAIAUser({self.email}, {self.username}, {self.namespace})"

    def __repr__(self):
        return f"<MAIAUser email={self.email} username={self.username} id={self.id}>"

    def __eq__(self, other):
        return isinstance(other, MAIAUser) and self.id == other.id

    def __hash__(self):
        return hash(self.id)


# ─── MAIAProject collection ───────────────────────────────────────────────────
_projects_col = None
_projects_col_lock = threading.Lock()


def get_projects_collection():
    global _projects_col
    if _projects_col is None:
        with _projects_col_lock:
            if _projects_col is None:
                _projects_col = settings.MONGO_DB["maia_projects"]
                _projects_col.create_index("namespace", unique=True)
    return _projects_col


class _MAIAProjectMeta:
    def __init__(self):
        self.model_name = "maiaproject"
        self.app_label = "dashboard"
        field_names = [
            "id",
            "namespace",
            "email",
            "users",
            "email_to_username_map",
            "memory_limit",
            "cpu_limit",
            "memory_request",
            "cpu_request",
            "project_tier",
            "gpu",
            "cluster",
            "date",
            "supervisor",
            "description",
            "auto_deploy",
            "auto_deploy_apps",
            "project_configuration",
            "created_at",
            "updated_at",
        ]
        # `id` is the MongoDB `_id` and is auto-generated on insert.
        # Mark it as non-required for Django `ModelForm` compatibility so
        # callers don't need to provide it in POST payloads.
        self.fields = [_FakeField(name, blank=(name == "id")) for name in field_names]
        self.concrete_fields = self.fields
        self.private_fields = []
        self.many_to_many = []
        self.many_to_one = []

    @property
    def object_name(self):
        return "MAIAProject"

    @property
    def verbose_name(self):
        return "MAIA Project"

    @property
    def verbose_name_plural(self):
        return "MAIA Projects"

    def get_fields(self):
        return self.fields


class MAIAProjectQuerySet:
    def __init__(self, query=None, projection=None, sort=None, limit_val=None, skip_val=None):
        self._query = query or {}
        self._projection = projection
        self._sort = sort
        self._limit_val = limit_val
        self._skip_val = skip_val
        self._cache = None

    def _clone(self, **overrides):
        return MAIAProjectQuerySet(
            query=overrides.get("query", dict(self._query)),
            projection=overrides.get("projection", self._projection),
            sort=overrides.get("sort", self._sort),
            limit_val=overrides.get("limit_val", self._limit_val),
            skip_val=overrides.get("skip_val", self._skip_val),
        )

    def _fetch(self):
        if self._cache is None:
            col = get_projects_collection()
            cursor = col.find(self._query, self._projection)
            if self._sort:
                cursor = cursor.sort(self._sort)
            if self._skip_val:
                cursor = cursor.skip(self._skip_val)
            if self._limit_val:
                cursor = cursor.limit(self._limit_val)
            self._cache = [MAIAProject._from_doc(d) for d in cursor]
        return self._cache

    def filter(self, **kwargs):
        q = {**self._query, **MAIAProject._build_query(kwargs)}
        return self._clone(query=q)

    def exclude(self, **kwargs):
        q = dict(self._query)
        for k, v in MAIAProject._build_query(kwargs).items():
            q[k] = {"$ne": v}
        return self._clone(query=q)

    def order_by(self, *fields):
        sort = []
        for f in fields:
            sort.append((f[1:], -1) if f.startswith("-") else (f, 1))
        return self._clone(sort=sort)

    def values(self, *fields):
        proj = {f: 1 for f in fields} if fields else None
        cursor = get_projects_collection().find(self._query, proj)
        return [{k: v for k, v in doc.items() if k != "_id"} for doc in cursor]

    def first(self):
        results = self._fetch()
        return results[0] if results else None

    def all(self):
        return self._clone()

    def exists(self):
        return get_projects_collection().count_documents(self._query, limit=1) > 0

    def count(self):
        return get_projects_collection().count_documents(self._query)

    def update(self, **kwargs):
        if not kwargs:
            return 0
        kwargs["updated_at"] = datetime.now(timezone.utc)
        result = get_projects_collection().update_many(self._query, {"$set": kwargs})
        return result.modified_count

    def delete(self):
        result = get_projects_collection().delete_many(self._query)
        return result.deleted_count, {"MAIAProject": result.deleted_count}

    def get(self, **kwargs):
        qs = self.filter(**kwargs) if kwargs else self
        results = qs._fetch()
        if len(results) == 0:
            raise MAIAProject.DoesNotExist("MAIAProject matching query does not exist.")
        if len(results) > 1:
            raise MAIAProject.MultipleObjectsReturned("get() returned more than one MAIAProject.")
        return results[0]

    def create(self, **kwargs):
        project = MAIAProject(**kwargs)
        project.save()
        return project

    def update_or_create(self, defaults=None, **kwargs):
        col = get_projects_collection()
        query = MAIAProject._build_query(kwargs)
        now = datetime.now(timezone.utc)
        set_payload = {**kwargs, **(defaults or {}), "updated_at": now}
        set_payload["date"] = MAIAProject._normalize_date_for_mongo(set_payload.get("date"))
        set_on_insert = {"created_at": now}
        result = col.find_one_and_update(
            query,
            {"$set": set_payload, "$setOnInsert": set_on_insert},
            upsert=True,
            return_document=True,
        )
        return MAIAProject._from_doc(result), result is None

    def __iter__(self):
        return iter(self._fetch())

    def __len__(self):
        return len(self._fetch())

    def __getitem__(self, key):
        if isinstance(key, slice):
            qs = self._clone(
                skip_val=key.start or 0,
                limit_val=(key.stop - (key.start or 0)) if key.stop else None,
            )
            return qs._fetch()
        return self._fetch()[key]


class MAIAProjectManager:
    def get_queryset(self):
        return MAIAProjectQuerySet()

    def __getattr__(self, name):
        return getattr(self.get_queryset(), name)

    def create(self, **kwargs):
        return self.get_queryset().create(**kwargs)


class MAIAProject:
    DoesNotExist = DoesNotExist
    MultipleObjectsReturned = MultipleObjectsReturned
    objects = MAIAProjectManager()
    _meta = _MAIAProjectMeta()

    def __init__(
        self,
        namespace=None,
        email=None,
        users=[],
        memory_limit="2 Gi",
        cpu_limit="2",
        memory_request="2 Gi",
        cpu_request="2",
        project_tier="Base",
        gpu="N/A",
        cluster="N/A",
        date=None,
        supervisor=None,
        description=None,
        auto_deploy=False,
        auto_deploy_apps=None,
        project_configuration=None,
        email_to_username_map=None,
        id=None,
        created_at=None,
        updated_at=None,
        **extra_fields,
    ):
        self.id = id
        self.namespace = (namespace or "").strip()
        self.email = email.lower().strip() if email else None
        self.users = users or []
        self.email_to_username_map = email_to_username_map or {}
        self.memory_limit = memory_limit
        self.cpu_limit = cpu_limit
        self.memory_request = memory_request
        self.cpu_request = cpu_request
        self.project_tier = project_tier
        self.gpu = gpu
        self.cluster = cluster
        self.date = date
        self.supervisor = supervisor
        self.description = description
        self.auto_deploy = auto_deploy
        self.auto_deploy_apps = auto_deploy_apps or []
        self.project_configuration = project_configuration or {}
        self.created_at = created_at or datetime.now(timezone.utc)
        self.updated_at = updated_at or datetime.now(timezone.utc)
        for k, v in extra_fields.items():
            setattr(self, k, v)

    def _to_doc(self):
        doc = {
            "namespace": self.namespace,
            "email": self.email,
            "users": self.users,
            "email_to_username_map": self.email_to_username_map,
            "memory_limit": self.memory_limit,
            "cpu_limit": self.cpu_limit,
            "memory_request": self.memory_request,
            "cpu_request": self.cpu_request,
            "project_tier": self.project_tier,
            "gpu": self.gpu,
            "cluster": self.cluster,
            "date": self._normalize_date_for_mongo(self.date),
            "supervisor": self.supervisor,
            "description": self.description,
            "auto_deploy": self.auto_deploy,
            "auto_deploy_apps": self.auto_deploy_apps,
            "project_configuration": self.project_configuration,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }
        if self.id:
            doc["_id"] = self.id
        return doc

    @staticmethod
    def _normalize_date_for_mongo(value):
        if isinstance(value, date) and not isinstance(value, datetime):
            return datetime.combine(value, time.min, tzinfo=timezone.utc)
        return value

    @classmethod
    def _from_doc(cls, doc):
        d = dict(doc)
        id_val = d.pop("_id", None)
        doc_date = d.pop("date", None)
        if isinstance(doc_date, datetime):
            doc_date = doc_date.date()
        return cls(
            id=id_val,
            namespace=d.pop("namespace", ""),
            email=d.pop("email", None),
            users=d.pop("users", []),
            email_to_username_map=d.pop("email_to_username_map", {}),
            memory_limit=d.pop("memory_limit", "16 Gi"),
            cpu_limit=d.pop("cpu_limit", "4"),
            memory_request=d.pop("memory_request", "8 Gi"),
            cpu_request=d.pop("cpu_request", "2"),
            project_tier=d.pop("project_tier", "Base"),
            gpu=d.pop("gpu", "1"),
            cluster=d.pop("cluster", "maia-small"),
            date=doc_date,
            supervisor=d.pop("supervisor", None),
            description=d.pop("description", None),
            auto_deploy=d.pop("auto_deploy", True),
            auto_deploy_apps=d.pop("auto_deploy_apps", []),
            project_configuration=d.pop("project_configuration", {}),
            created_at=d.pop("created_at", None),
            updated_at=d.pop("updated_at", None),
            **d,
        )

    @classmethod
    def _build_query(cls, kwargs):
        operators = {
            "gt": "$gt",
            "gte": "$gte",
            "lt": "$lt",
            "lte": "$lte",
            "ne": "$ne",
            "in": "$in",
            "nin": "$nin",
            "exists": "$exists",
        }
        aliases = {"id": "_id"}
        query = {}
        for key, value in kwargs.items():
            parts = key.split("__")
            field = aliases.get(parts[0], parts[0])
            op = parts[1] if len(parts) > 1 else None
            if op in {"iexact", "icontains"}:
                query[field] = {"$regex": value, "$options": "i"}
            elif op == "contains":
                query[field] = {"$regex": value}
            elif op == "startswith":
                query[field] = {"$regex": f"^{value}"}
            elif op == "endswith":
                query[field] = {"$regex": f"{value}$"}
            elif op == "isnull":
                query[field] = None if value else {"$ne": None}
            elif op in operators:
                query[field] = {operators[op]: value}
            else:
                query[field] = value
        return query

    def save(self):
        col = get_projects_collection()
        self.updated_at = datetime.now(timezone.utc)
        doc = self._to_doc()
        if self.id:
            col.update_one({"_id": self.id}, {"$set": doc})
        else:
            result = col.insert_one(doc)
            self.id = result.inserted_id
        return self

    def delete(self):
        if self.id:
            get_projects_collection().delete_one({"_id": self.id})
            self.id = None

    def __str__(self):
        return f"MAIAProject({self.namespace}, owner={self.email})"

        # ── Django-compatible clean/full_clean stubs for ModelForm compatibility ──

    def clean(self):
        """
        This method is called during form/model validation.
        Accumulate validation errors in self._errors.
        """
        self._errors = {}
        # Enforce required fields even though `__init__` must tolerate None
        # for Django form construction on GET requests.
        if not self.email:
            self._errors["email"] = "This field is required."
        if not self.namespace:
            self._errors["namespace"] = "This field is required."

    def full_clean(self, exclude=None, validate_unique=True):
        """Stub method to support Django ModelForm compatibility.

        Args:
            exclude: Fields to exclude from validation.
            validate_unique: Whether to validate uniqueness.
        Returns:
            cleaned_data: Always returns cleaned_data dict with email, username, namespace.
        Raises:
            ValidationError: If there are validation errors (but always returns cleaned data).
        """
        self.clean()
        unique_errors = self.validate_unique(exclude=exclude) or {}

        if unique_errors:
            # Merge unique errors to main errors dict
            self._errors.update(unique_errors)

        # Determine if there's a validation error to handle just before raising.
        if self._errors:
            # Preserve submitted values so form.cleaned_data still contains
            # user input when validation fails (e.g. unique constraint errors).
            error = ValidationError(self._errors)
            raise error

        # Otherwise, normal cleaned_data
        cleaned_data = {
            "namespace": self.namespace,
            "email": self.email,
            "users": self.users,
            "email_to_username_map": self.email_to_username_map,
            "memory_limit": self.memory_limit,
            "cpu_limit": self.cpu_limit,
            "memory_request": self.memory_request,
            "cpu_request": self.cpu_request,
            "project_tier": self.project_tier,
            "gpu": self.gpu,
            "cluster": self.cluster,
            "date": self.date,
            "supervisor": self.supervisor,
            "description": self.description,
            "auto_deploy": self.auto_deploy,
            "auto_deploy_apps": self.auto_deploy_apps,
            "project_configuration": self.project_configuration,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

        return cleaned_data

    def validate_unique(self, exclude=None):
        """
        Django-compatible method to check for unique field violations.
        Used by ModelForms and Django admin.
        Attaches errors to the instance for form display and prevents submission if errors exist.
        """
        unique_errors = {}

        exclude = set(exclude or [])

        # Only check if not excluded
        if "namespace" not in exclude and self.namespace:
            qs = type(self).objects.filter(namespace=self.namespace)
            if self.id is not None:
                qs = qs.exclude(id=self.id)
            if qs.exists():
                unique_errors["namespace"] = self.unique_error_message(type(self), ["namespace"])
        # Other unique checks can be added if needed

        return unique_errors
