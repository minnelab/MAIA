# signals.py
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.conf import settings
from .models import MAIAUser, MAIAProject

# Get the pymongo database object from settings
if settings.MONGO_DB_ENABLED:
    db = settings.MONGO_DB

    # Create the collection if it does not exist
    if "maia_users" not in db.list_collection_names():
        db.create_collection("maia_users")

    mongo_collection_users = db["maia_users"]  # MongoDB collection

    if "maia_projects" not in db.list_collection_names():
        db.create_collection("maia_projects")

    mongo_collection_projects = db["maia_projects"]  # MongoDB collection

@receiver(post_save, sender=MAIAUser)
def sync_maia_user_to_mongo(sender, instance, created, **kwargs):
    if not settings.MONGO_DB_ENABLED:
        return
    print(f"Syncing MAIA user to MongoDB: {instance.email} {instance.namespace}")
    data = {
        "django_id": instance.id,
        "email": instance.email,
        "namespace": instance.namespace,
    }
    print(f"Data: {data}")
    print(f"Created: {created}")
    if created:
        mongo_collection_users.insert_one(data)
    else:
        mongo_collection_users.update_one(
            {"django_id": instance.id},
            {"$set": data}
        )

@receiver(post_delete, sender=MAIAUser)
def delete_maia_user_from_mongo(sender, instance, **kwargs):
    if not settings.MONGO_DB_ENABLED:
        return
    mongo_collection_users.delete_one({"django_id": instance.id})
    
@receiver(post_save, sender=MAIAProject)
def sync_maia_project_to_mongo(sender, instance, created, **kwargs):
    if not settings.MONGO_DB_ENABLED:
        return
    print(f"Syncing MAIA project to MongoDB: {instance.namespace}")
    data = {
        "django_id": instance.id,
        "namespace": instance.namespace,
    }
    print(f"Data: {data}")
    print(f"Created: {created}")
    if created:
        mongo_collection_projects.insert_one(data)
        
@receiver(post_delete, sender=MAIAProject)
def delete_maia_project_from_mongo(sender, instance, **kwargs):
    if not settings.MONGO_DB_ENABLED:
        return
    mongo_collection_projects.delete_one({"django_id": instance.id})