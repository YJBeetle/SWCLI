"""Bounded traversal of the native tree for independent STEP readback."""


MAX_FEATURES = 10000
MAX_DEPTH = 64


def walk_features(document, value):
    """Yield every bounded tree occurrence with a structural parent index."""
    from .step_periodic_driver import require

    first = value(document, 'FirstFeature')
    pending = [(first, None, 0, 'GetNextFeature')] if first is not None else []
    index = 0
    while pending:
        feature, parent, depth, next_member = pending.pop()
        require(index < MAX_FEATURES and depth <= MAX_DEPTH,
                'inventory exceeded feature or depth limit (possibly a cycle)')
        yield feature, index, parent, depth
        sibling = value(feature, next_member)
        child = value(feature, 'GetFirstSubFeature')
        if sibling is not None:
            pending.append((sibling, parent, depth, next_member))
        if child is not None:
            pending.append((child, index, depth + 1, 'GetNextSubFeature'))
        index += 1
