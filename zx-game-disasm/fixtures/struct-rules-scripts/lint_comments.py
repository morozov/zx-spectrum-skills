"""A stand-in lint_comments.py: validate_rules.py reads GATING_KINDS without running it."""

GATING_KINDS = frozenset((
    'DATA_ECHO', 'SPLICE',
))
