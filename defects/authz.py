from dataclasses import dataclass

from django.contrib.auth.models import AnonymousUser


ROLE_OWNER = "owner"
ROLE_DEVELOPER = "developer"


@dataclass(frozen=True)
class ActorContext:
    actor_id: str
    is_owner: bool
    is_developer: bool


def actor_from_user(user) -> ActorContext:
    if not user or isinstance(user, AnonymousUser) or not user.is_authenticated:
        return ActorContext(actor_id="", is_owner=False, is_developer=False)

    actor_id = (getattr(user, "username", "") or "").strip()
    groups = set(user.groups.values_list("name", flat=True))
    is_owner = ROLE_OWNER in groups
    is_developer = ROLE_DEVELOPER in groups
    return ActorContext(actor_id=actor_id, is_owner=is_owner, is_developer=is_developer)
