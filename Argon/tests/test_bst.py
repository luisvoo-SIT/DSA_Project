import unittest
from core.bst import AVLTree


class TestAVLTree(unittest.TestCase):

    def test_insert_and_exact_search(self):
        tree = AVLTree()
        items = [
            ("ITM-005", "Product 5"),
            ("ITM-002", "Product 2"),
            ("ITM-008", "Product 8"),
            ("ITM-001", "Product 1"),
            ("ITM-003", "Product 3"),
            ("ITM-007", "Product 7"),
        ]
        for k, v in items:
            tree.insert(k, v)

        self.assertEqual(len(tree), 6)
        for k, v in items:
            self.assertEqual(tree.search(k), v)
            self.assertTrue(tree.contains(k))

        self.assertIsNone(tree.search("NON-EXISTENT"))
        self.assertFalse(tree.contains("NON-EXISTENT"))

    def test_avl_balance_rotations(self):
        # Insert strictly increasing elements to trigger left rotations
        tree = AVLTree()
        for i in range(1, 32):
            tree.insert(f"ITM-{i:03d}", i)

        self.assertEqual(len(tree), 31)
        # In a balanced AVL tree with 31 nodes, maximum height is <= 6
        self.assertLessEqual(tree.root.height, 6)

        # In-order traversal must return strictly ascending sorted keys
        in_order = tree.in_order_traversal()
        keys = [k for k, _ in in_order]
        self.assertEqual(keys, sorted(keys))

    def test_update_existing_key(self):
        tree = AVLTree()
        tree.insert("ITM-100", "Initial")
        self.assertEqual(tree.search("ITM-100"), "Initial")
        self.assertEqual(len(tree), 1)

        tree.insert("ITM-100", "Updated")
        self.assertEqual(tree.search("ITM-100"), "Updated")
        self.assertEqual(len(tree), 1)


if __name__ == "__main__":
    unittest.main()
