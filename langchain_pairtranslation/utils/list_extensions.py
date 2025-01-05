
from typing import Iterator, TypeVar, Sequence

def same_sign(a: int, b: int) -> bool:
    return (a >= 0 and b >= 0) or (a < 0 and b < 0)

def center_enumerate[T](enumerable: Sequence[T], clockwise: bool = True) -> Iterator[tuple[int, T]]:
    """
    Enumerate a list from its center outward.
    """
    list_length = len(enumerable)
    center_idx = list_length // 2
    yield (center_idx, enumerable[center_idx])
    if not center_idx:
        return
    
    step = 1 if clockwise else -1
    offset = step
    for i in range(list_length - 1):
        yield (center_idx + offset, enumerable[center_idx + offset])
        offset = -offset
        if same_sign(offset, step):
            offset += step