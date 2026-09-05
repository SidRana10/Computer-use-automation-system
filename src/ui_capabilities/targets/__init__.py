"""Target profiles: everything the core needs to know about one application.

A profile is data, not a parallel engine. It supplies the policy, the known
runtime-condition rules, the fingerprint markers, the typed input registry, and
the evidence-redaction settings for one target. Discovery, the compiler, the
replay engine, the policy engine and the surface are identical across targets.
"""

from .registry import TargetProfile, get_profile, profile_names

__all__ = ["TargetProfile", "get_profile", "profile_names"]
