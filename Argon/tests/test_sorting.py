import unittest
from core.sorting import merge_sort


class TestMergeSort(unittest.TestCase):

    def test_sort_ascending(self):
        data = [5, 2, 9, 1, 5, 6]
        sorted_data = merge_sort(data)
        self.assertEqual(sorted_data, [1, 2, 5, 5, 6, 9])

    def test_sort_descending(self):
        data = [5, 2, 9, 1, 5, 6]
        sorted_data = merge_sort(data, reverse=True)
        self.assertEqual(sorted_data, [9, 6, 5, 5, 2, 1])

    def test_sort_with_key_and_stability(self):
        items = [
            ("A", 10),
            ("B", 30),
            ("C", 20),
            ("D", 30),
        ]
        sorted_items = merge_sort(items, key=lambda x: x[1], reverse=True)
        # B and D have same key 30; B must precede D (stable sort)
        self.assertEqual(sorted_items[0], ("B", 30))
        self.assertEqual(sorted_items[1], ("D", 30))
        self.assertEqual(sorted_items[2], ("C", 20))
        self.assertEqual(sorted_items[3], ("A", 10))

    def test_empty_and_single(self):
        self.assertEqual(merge_sort([]), [])
        self.assertEqual(merge_sort([42]), [42])


if __name__ == "__main__":
    unittest.main()
