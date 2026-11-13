"""
Explicit Merge Sort implementation for ranking products by value-per-cost descending.
"""
from typing import Any, Callable, List, TypeVar

T = TypeVar("T")


def merge_sort(items: List[T], key: Callable[[T], Any] = lambda x: x, reverse: bool = False) -> List[T]:
    """
    Standard stable merge sort implementation.
    
    Args:
        items: List of elements to sort.
        key: Function to extract comparison key.
        reverse: If True, sorts descending; otherwise ascending.
    """
    if len(items) <= 1:
        return list(items)

    mid = len(items) // 2
    left = merge_sort(items[:mid], key=key, reverse=reverse)
    right = merge_sort(items[mid:], key=key, reverse=reverse)

    return _merge(left, right, key, reverse)


def _merge(left: List[T], right: List[T], key: Callable[[T], Any], reverse: bool) -> List[T]:
    result: List[T] = []
    i = j = 0

    while i < len(left) and j < len(right):
        key_l = key(left[i])
        key_r = key(right[j])

        # Stable sort comparison
        if reverse:
            # For descending order, left[i] goes first if key_l >= key_r
            if key_l >= key_r:
                result.append(left[i])
                i += 1
            else:
                result.append(right[j])
                j += 1
        else:
            # For ascending order, left[i] goes first if key_l <= key_r
            if key_l <= key_r:
                result.append(left[i])
                i += 1
            else:
                result.append(right[j])
                j += 1

    result.extend(left[i:])
    result.extend(right[j:])
    return result
