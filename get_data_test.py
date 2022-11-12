"""Testing the get_data functions."""

import json
import asyncio
import unittest
import numpy as np
# local
import get_data


with open('data/test/test_in.json', 'r', encoding='utf-8') as f:
    test_data = json.load(f)

class TestGetData(unittest.TestCase):
    """Test the get_data module."""

    def test_get_app_ids(self):
        """Test get_app_id."""
        appids, _ = asyncio.run(get_data.get_app_ids(test_data['game_names']))
        np.testing.assert_array_equal(appids, test_data['appids'])

    def test_get_game_sizes(self):
        """Test get_game_size."""
        sizes = asyncio.run(get_data.get_game_sizes(test_data['appids']))
        np.testing.assert_array_almost_equal(sizes, test_data['sizes'], decimal=2)

    def test_get_game_review_ratios(self):
        """Test get_game_review_ratios."""
        review_ratios = asyncio.run(get_data.get_game_review_ratios(test_data['appids']))
        np.testing.assert_array_almost_equal(review_ratios, test_data['review_ratios'], decimal=2)

    def test_size_regex(self):
        """Test get_game_size_regex."""
        for size, regex in test_data['regex'].items():
            self.assertEqual(get_data.size_regex(size).group(2), regex)

if __name__ == '__main__':
    unittest.main()
