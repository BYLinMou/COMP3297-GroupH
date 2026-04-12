from django.db.models.signals import post_migrate
from django.dispatch import receiver

from .services import ensure_demo_seed


@receiver(post_migrate)
def seed_demo_data(sender, **kwargs):
    # Seed only after defects app migrations are applied.
    if getattr(sender, "name", "") != "defects":
        return
    ensure_demo_seed()
