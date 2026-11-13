"""
Priority queue implementation for batch expiry inspection (earliest remaining shelf life first).
"""
import heapq
from typing import Any, List, Optional
from core.models import BatchRecord


class BatchPriorityQueue:
    """
    Min-heap priority queue ordering batches by remaining shelf life (earliest first).
    Ties broken by delivery date, item_id, and batch_no.
    """

    def __init__(self):
        self._heap = []
        self._counter = 0

    def push(self, batch: BatchRecord) -> None:
        """Pushes a BatchRecord onto the priority queue."""
        # Priority tuple: (remaining_shelf_life, delivery_date, item_id, counter, batch)
        # Using counter ensures stable ordering if dates and item_id match.
        priority = (batch.remaining_shelf_life, batch.delivery_date, batch.item_id, self._counter)
        self._counter += 1
        heapq.heappush(self._heap, (priority, batch))

    def pop(self) -> BatchRecord:
        """Pops and returns the batch with earliest remaining shelf life."""
        if not self._heap:
            raise IndexError("pop from empty BatchPriorityQueue")
        _, batch = heapq.heappop(self._heap)
        return batch

    def peek(self) -> Optional[BatchRecord]:
        """Peeks at the batch with earliest remaining shelf life without removing it."""
        if not self._heap:
            return None
        return self._heap[0][1]

    def to_sorted_list(self) -> List[BatchRecord]:
        """Returns all batches sorted by priority (earliest expiry first) without destroying the queue."""
        # Copy heap and pop all
        temp_heap = list(self._heap)
        result = []
        while temp_heap:
            _, batch = heapq.heappop(temp_heap)
            result.append(batch)
        return result

    def __len__(self) -> int:
        return len(self._heap)

    def is_empty(self) -> bool:
        return len(self._heap) == 0

    def clear(self) -> None:
        self._heap.clear()
        self._counter = 0
