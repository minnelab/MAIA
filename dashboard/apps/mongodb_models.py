# apps/documents.py
import hashlib
import os
import threading
from datetime import datetime, timezone
from bson import ObjectId
from django.conf import settings
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
                _col.create_index("namespace")
                _col.create_index("username", unique=True, sparse=True)
    return _col

# ─── meta "mock" for Django compatibility ─────────────────────────────────────
class _FakeField:
    """
    Simple mock field to mimic Django's model field interface for compatibility
    with forms/models internals that expect .name, .attname, etc.
    Implements __lt__ for sorting compatibility with Django forms/models.
    Also provides a simple .formfield method for Django form compatibility.
    """
    def __init__(self, name):
        self.name = name
        self.attname = name
        self.is_relation = False
        self.many_to_one = False
        self.many_to_many = False
        self.editable = True
        self.remote_field = None

    def __lt__(self, other):
        # Allow Django's `sorted()`/ordering to work by name
        if isinstance(other, _FakeField):
            return self.name < other.name
        return NotImplemented

    def formfield(self, **kwargs):
        # Provide a very simple dummy formfield for Django admin/forms compatibility
        from django import forms
        # Attempt to guess field type by name
        if self.name == "email":
            return forms.EmailField(required=not kwargs.get('blank', False))
        elif self.name == "username":
            return forms.CharField(required=not kwargs.get('blank', False))
        elif self.name in {"is_active", "is_staff", "is_superuser", "is_anonymous", "is_authenticated"}:
            return forms.BooleanField(required=False)
        elif self.name in {"last_login", "date_joined", "created_at", "updated_at"}:
            return forms.DateTimeField(required=False)
        else:
            return forms.CharField(required=not kwargs.get('blank', False))

class _MAIAUserMeta:
    """
    Minimal _meta object to satisfy Django admin/forms expectations.
    """
    def __init__(self):
        self.model_name = 'maiauser'
        self.app_label = 'dashboard'
        # Create list of mock field objects
        field_names = [
            'id', 'email', 'username', 'namespace', 'password', 'is_active', 'is_staff', 
            'is_superuser', 'is_anonymous', 'is_authenticated', 'last_login', 
            'date_joined', 'created_at', 'updated_at'
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
    def __init__(self, query=None, projection=None, sort=None, limit_val=None,
                 skip_val=None, for_update=False):
        self._query      = query or {}
        self._projection = projection
        self._sort       = sort
        self._limit_val  = limit_val
        self._skip_val   = skip_val
        self._for_update = for_update   # stored but MongoDB has no row locks
        self._cache      = None

    # ── internal ──────────────────────────────────────────────────────────────
    def _clone(self, **overrides):
        return MAIAUserQuerySet(
            query      = overrides.get("query",      dict(self._query)),
            projection = overrides.get("projection", self._projection),
            sort       = overrides.get("sort",       self._sort),
            limit_val  = overrides.get("limit_val",  self._limit_val),
            skip_val   = overrides.get("skip_val",   self._skip_val),
            for_update = overrides.get("for_update", self._for_update),
        )

    def _fetch(self):
        if self._cache is None:
            col    = get_collection()
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
        proj   = {f: 1 for f in fields} if fields else None
        cursor = get_collection().find(self._query, proj)
        return [
            {k: v for k, v in doc.items() if k != "_id"}
            for doc in cursor
        ]

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
                skip_val  = key.start or 0,
                limit_val = (key.stop - (key.start or 0)) if key.stop else None,
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
        col   = get_collection()
        query = MAIAUser._build_query(kwargs)
        doc   = col.find_one(query)
        if doc:
            return MAIAUser._from_doc(doc), False
        data  = {**kwargs, **(defaults or {})}
        user  = MAIAUser(**data)
        user.save()
        return user, True

    def update_or_create(self, defaults=None, **kwargs):
        col    = get_collection()
        query  = MAIAUser._build_query(kwargs)
        update = {"$set": {**kwargs, **(defaults or {}), "updated_at": datetime.now(timezone.utc)}}
        result = col.find_one_and_update(
            query, update,
            upsert=True, return_document=True
        )
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
        docs   = [u._to_doc() for u in users]
        result = get_collection().insert_many(docs)
        for user, oid in zip(users, result.inserted_ids):
            user.id = oid
        return users

    def bulk_update(self, users, fields):
        from pymongo import UpdateOne
        ops = [
            UpdateOne(
                {"_id": u.id},
                {"$set": {f: getattr(u, f) for f in fields}}
            )
            for u in users
        ]
        return get_collection().bulk_write(ops).modified_count

    def in_bulk(self, id_list=None, field_name="id"):
        query = dict(self._query)
        # Convert to Mongo _id for querying
        if id_list is not None:
            if field_name == "id":
                query["_id"] = {"$in": id_list}
            else:
                query[field_name] = {"$in": id_list}
        return {
            str(u.id): u
            for u in (MAIAUser._from_doc(d) for d in get_collection().find(query))
        }

    def iterator(self, chunk_size=100):
        col    = get_collection()
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

    def create_user(self, email, namespace, password=None, username=None, **extra):
        if not email:
            raise ValueError("email is required")
        user = MAIAUser(email=email.lower().strip(), namespace=namespace, username=username, **extra)
        user.set_password(password)
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
    DoesNotExist            = DoesNotExist
    MultipleObjectsReturned = MultipleObjectsReturned
    objects                 = MAIAUserManager()

    _meta = _MAIAUserMeta()  # <-- This will satisfy Django forms/models.py expectations

    REQUIRED_FIELDS = ["email", "namespace"]
    USERNAME_FIELD  = "email"

    def __init__(
        self,
        email,
        namespace,
        password        = None,
        username        = None,
        is_active       = True,
        is_staff        = False,
        is_superuser    = False,
        is_anonymous    = False,
        is_authenticated= True,
        last_login      = None,
        date_joined     = None,
        id              = None,
        **extra_fields,
    ):
        self.id                = id
        self.email             = email.lower().strip() if email else email
        self.username          = username
        self.namespace         = namespace
        self.password          = password      # stored as hash
        self.is_active         = is_active
        self.is_staff          = is_staff
        self.is_superuser      = is_superuser
        self.is_anonymous      = is_anonymous
        self.is_authenticated  = is_authenticated
        self.last_login        = last_login
        self.date_joined       = date_joined or datetime.now(timezone.utc)
        self.created_at        = datetime.now(timezone.utc)
        self.updated_at        = datetime.now(timezone.utc)
        for k, v in extra_fields.items():
            setattr(self, k, v)

    # ── password ──────────────────────────────────────────────────────────────
    def set_password(self, raw_password):
        if raw_password is None:
            self.password = None
            return
        salt          = os.urandom(16).hex()
        hashed        = hashlib.sha256(f"{salt}{raw_password}".encode()).hexdigest()
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
            "email"           : self.email,
            "username"        : self.username,
            "namespace"       : self.namespace,
            "password"        : self.password,
            "is_active"       : self.is_active,
            "is_staff"        : self.is_staff,
            "is_superuser"    : self.is_superuser,
            "is_anonymous"    : self.is_anonymous,
            "is_authenticated": self.is_authenticated,
            "last_login"      : self.last_login,
            "date_joined"     : self.date_joined,
            "created_at"      : self.created_at,
            "updated_at"      : self.updated_at,
        }
        if self.id:
            doc["_id"] = self.id
        return doc

    @classmethod
    def _from_doc(cls, doc):
        d = dict(doc)
        id_val = d.pop("_id", None)
        return cls(
            id              = id_val,
            email           = d.pop("email", ""),
            username        = d.pop("username", None),
            namespace       = d.pop("namespace", ""),
            password        = d.pop("password", None),
            is_active       = d.pop("is_active", True),
            is_staff        = d.pop("is_staff", False),
            is_superuser    = d.pop("is_superuser", False),
            is_anonymous    = d.pop("is_anonymous", False),
            is_authenticated= d.pop("is_authenticated", True),
            last_login      = d.pop("last_login", None),
            date_joined     = d.pop("date_joined", None),
            **d,   # any extra fields stored in mongo
        )

    @classmethod
    def _build_query(cls, kwargs):
        """Translate Django-style lookups to MongoDB queries."""
        OPERATORS = {
            "gt" : "$gt",  "gte": "$gte",
            "lt" : "$lt",  "lte": "$lte",
            "ne" : "$ne",  "in" : "$in",
            "nin": "$nin", "exists": "$exists",
        }
        query = {}
        for key, value in kwargs.items():
            parts = key.split("__")
            field = parts[0]
            op    = parts[1] if len(parts) > 1 else None
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
        col              = get_collection()
        self.updated_at  = datetime.now(timezone.utc)
        doc              = self._to_doc()
        if self.id:
            col.update_one({"_id": self.id}, {"$set": doc})
        else:
            result  = col.insert_one(doc)
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
        get_collection().update_one(
            {"_id": self.id},
            {"$set": {"last_login": self.last_login}}
        )

    # ── dunder ────────────────────────────────────────────────────────────────
    def __str__(self):
        return f"MAIAUser({self.email}, {self.username}, {self.namespace})"

    def __repr__(self):
        return f"<MAIAUser email={self.email} username={self.username} id={self.id}>"

    def __eq__(self, other):
        return isinstance(other, MAIAUser) and self.id == other.id

    def __hash__(self):
        return hash(self.id)