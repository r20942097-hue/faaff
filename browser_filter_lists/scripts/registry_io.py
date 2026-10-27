"""Shared strict JSON and repository-path handling for filter validators."""
import json
from pathlib import Path


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f'duplicate JSON key: {key}')
        result[key] = value
    return result


def load_json_object(path):
    with path.open('r', encoding='utf-8') as handle:
        data = json.load(handle, object_pairs_hook=unique_object)
    if not isinstance(data, dict):
        raise ValueError('root must be an object')
    return data


def safe_path(root, relative):
    if (not isinstance(relative, str) or not relative or Path(relative).is_absolute()
            or '..' in Path(relative).parts or '\\' in relative):
        return None
    candidate = root / relative
    try:
        candidate.resolve().relative_to(root.resolve())
    except (ValueError, OSError, RuntimeError):
        return None
    current = candidate
    while current != root:
        if current.is_symlink():
            return None
        current = current.parent
        if current == current.parent:
            return None
    return candidate


def integer_in_range(value, minimum, maximum):
    return type(value) is int and minimum <= value <= maximum
