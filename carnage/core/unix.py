"""Unix-like OS utilities."""

import grp
import os
import pwd


def is_user_in_group(username: str, group_name: str) -> bool:
    try:
        # Get user's primary GID
        user_info = pwd.getpwnam(username)
        # Get all group IDs for this user
        gids = os.getgrouplist(username, user_info.pw_gid)
        # Get the GID for the target group
        target_gid = grp.getgrnam(group_name).gr_gid

        return target_gid in gids
    except KeyError:
        # User or group does not exist
        return False


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
