"""
Balanced Binary Search Tree (AVL Tree) for exact product ID lookup.
"""
from typing import Any, List, Optional, Tuple


class AVLNode:
    def __init__(self, key: str, value: Any):
        self.key = key
        self.value = value
        self.left: Optional[AVLNode] = None
        self.right: Optional[AVLNode] = None
        self.height: int = 1


class AVLTree:
    def __init__(self):
        self.root: Optional[AVLNode] = None
        self._size: int = 0

    def __len__(self) -> int:
        return self._size

    def _get_height(self, node: Optional[AVLNode]) -> int:
        if not node:
            return 0
        return node.height

    def _get_balance(self, node: Optional[AVLNode]) -> int:
        if not node:
            return 0
        return self._get_height(node.left) - self._get_height(node.right)

    def _rotate_right(self, y: AVLNode) -> AVLNode:
        x = y.left
        T2 = x.right

        # Perform rotation
        x.right = y
        y.left = T2

        # Update heights
        y.height = 1 + max(self._get_height(y.left), self._get_height(y.right))
        x.height = 1 + max(self._get_height(x.left), self._get_height(x.right))

        return x

    def _rotate_left(self, x: AVLNode) -> AVLNode:
        y = x.right
        T2 = y.left

        # Perform rotation
        y.left = x
        x.right = T2

        # Update heights
        x.height = 1 + max(self._get_height(x.left), self._get_height(x.right))
        y.height = 1 + max(self._get_height(y.left), self._get_height(y.right))

        return y

    def insert(self, key: str, value: Any) -> None:
        """Inserts or updates a key-value pair."""
        def _insert(node: Optional[AVLNode], k: str, v: Any) -> AVLNode:
            if not node:
                self._size += 1
                return AVLNode(k, v)

            if k == node.key:
                # Key already exists: update value
                node.value = v
                return node
            elif k < node.key:
                node.left = _insert(node.left, k, v)
            else:
                node.right = _insert(node.right, k, v)

            # Update height
            node.height = 1 + max(self._get_height(node.left), self._get_height(node.right))

            # Balance factor
            balance = self._get_balance(node)

            # Left Left
            if balance > 1 and k < node.left.key:
                return self._rotate_right(node)

            # Right Right
            if balance < -1 and k > node.right.key:
                return self._rotate_left(node)

            # Left Right
            if balance > 1 and k > node.left.key:
                node.left = self._rotate_left(node.left)
                return self._rotate_right(node)

            # Right Left
            if balance < -1 and k < node.right.key:
                node.right = self._rotate_right(node.right)
                return self._rotate_left(node)

            return node

        self.root = _insert(self.root, str(key), value)

    def search(self, key: str) -> Optional[Any]:
        """Searches for an exact key match in O(log N) time."""
        curr = self.root
        key = str(key)
        while curr:
            if key == curr.key:
                return curr.value
            elif key < curr.key:
                curr = curr.left
            else:
                curr = curr.right
        return None

    def contains(self, key: str) -> bool:
        return self.search(key) is not None

    def in_order_traversal(self) -> List[Tuple[str, Any]]:
        """Returns sorted list of (key, value) pairs."""
        result = []
        def _in_order(node: Optional[AVLNode]):
            if not node:
                return
            _in_order(node.left)
            result.append((node.key, node.value))
            _in_order(node.right)
        _in_order(self.root)
        return result

    def clear(self) -> None:
        self.root = None
        self._size = 0
