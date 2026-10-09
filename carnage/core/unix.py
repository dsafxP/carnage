"""Unix-like OS utilities."""

import grp
import os


def current_user_in_group(group_name: str) -> bool:
    try:
        target_gid = grp.getgrnam(group_name).gr_gid
        # os.getgroups() returns supplementary GIDs;
        # include primary group with os.getgid()
        current_gids = set(os.getgroups())
        current_gids.add(os.getgid())

        return target_gid in current_gids
    except KeyError:
        return False
