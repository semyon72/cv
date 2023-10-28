# IDE: PyCharm
# Project: cv
# Path: ${DIR_PATH}
# File: ${FILE_NAME}
# Contact: Semyon Mamonov <semyon.mamonov@gmail.com>
# Created by ox23 at 2023-10-23 (y-m-d) 9:32 PM
import random

from django.test import TestCase

from apps.cv.compare import DataMatcher


class TestFullDataComparer(TestCase):

    def setUp(self) -> None:
        ...

    def test__remove_ambiguity(self):
        """
        -------------------------> s
        | .3 | .6 | .7 | .7 | .2 |
        | .9 | .2 | .9 | .6 | .6 |
        | .5 | .8 | .4 | .7 | .5 |
        | .9 | .6 | .9 | .9 | .1 |
        u
        """
        dc = DataMatcher([], [])

        # test for .9
        with self.subTest('subtest maxes set #1'):
            maxes = [
                ((1, 0), .9), ((1, 2), .9),
                ((3, 0), .9), ((3, 2), .9), ((3, 3), .9)
            ]
            test_result = [((1, 0), .9), ((3, 2), .9)]
            res = dc._remove_ambiguity(maxes)
            self.assertListEqual(test_result, res)

        with self.subTest('subtest maxes set #2'):
            maxes = [
                ((3, 3), .9), ((3, 2), .9), ((1, 2), .9),
                ((3, 0), .9), ((1, 0), .9),
            ]
            test_result = [((3, 3), .9), ((1, 2), .9)]
            res = dc._remove_ambiguity(maxes)
            self.assertListEqual(test_result, res)

        with self.subTest('empty maxes'):
            self.assertListEqual(dc._remove_ambiguity([]), [])

        with self.subTest('maxes has different ratio'):
            maxes = [((3, 3), .9), ((3, 2), .8)]
            with self.assertRaises(AssertionError) as exc:
                res = dc._remove_ambiguity(maxes)
            texcstr = "Warning: ratios [0.8:0.9] must be equal"
            self.assertEqual(str(exc.exception), texcstr)

    def test__get_maxed(self):
        """
        -------------------------> s
        | .3 | .6 | .7 | .7 | .2 |
        | .9 | .2 | .9 | .6 | .6 |
        | .5 | .8 | .4 | .7 | .5 |
        | .9 | .6 | .9 | .9 | .1 |
        u
        """
        # ratios is { (ui, si): ratio, ..... }
        ratios_list = [
            ((0, 0), .3), ((0, 1), .6), ((0, 2), .7), ((0, 3), .7), ((0, 4), .2),
            ((1, 0), .9), ((1, 1), .2), ((1, 2), .9), ((1, 3), .6), ((1, 4), .6),
            ((2, 0), .5), ((2, 1), .8), ((2, 2), .4), ((2, 3), .7), ((2, 4), .5),
            ((3, 0), .9), ((3, 1), .6), ((3, 2), .9), ((3, 3), .9), ((3, 4), .1)
        ]
        ratios = dict(ratios_list)

        dc = DataMatcher([], [])
        maxes_09 = [((1, 0), .9), ((1, 2), .9), ((3, 0), .9), ((3, 2), .9), ((3, 3), .9)]
        with self.subTest('maxes for 0.9'):
            maxes = dc._get_maxed(ratios, {})
            self.assertListEqual(maxes_09, maxes)

        excludes: dict[str, set[int]] = {k: {ri[0][ki] for ri in maxes_09} for ki, k in enumerate('us')}
        maxes_08 = [((2, 1), .8)]
        with self.subTest('maxes for next after 0.9 -> ((2, 1), .8)'):
            maxes = dc._get_maxed(ratios, excludes)
            self.assertListEqual(maxes_08, maxes)

    def test__get_ratios(self):
        """
             | ltp | udp | smtp | tftp | sftp | umtp|
        https|  0.7|  0.5|   0.6|   0.8|   0.6| 0.6
          stp|  0.8|  0.6|   0.9|   0.7|   0.9| 0.7
          udp|  0.6|  1.0|   NA |   NA |   NA | NA
          utp|  0.8|  NA |   0.7|   0.7|   0.7| 0.9
        """

        s_list = [{'key': v} for v in ('ltp', 'udp', 'smtp', 'tftp', 'sftp', 'umtp')]
        u_list = [{'key': v} for v in ('https', 'stp', 'udp', 'utp')]
        dc = DataMatcher(s_list, u_list)
        dc.ratio_round_precision = 1
        excludes, maxes = {}, []
        ratios = dc._get_ratios(excludes, maxes, False, False)
        test_ratios = {
            (0, 0): 0.7, (0, 1): 0.5, (0, 2): 0.6, (0, 3): 0.8, (0, 4): 0.6, (0, 5): 0.6,
            (1, 0): 0.8, (1, 1): 0.6, (1, 2): 0.9, (1, 3): 0.7, (1, 4): 0.9, (1, 5): 0.7,
            (2, 0): 0.6, (2, 1): 1.0,
            (3, 0): 0.8,              (3, 2): 0.7, (3, 3): 0.7, (3, 4): 0.7, (3, 5): 0.9
        }
        with self.subTest('main subtest'):
            self.assertDictEqual(test_ratios, ratios)
            self.assertListEqual([((2, 1), 1.0)], maxes)
            self.assertDictEqual({'u': {2}, 's': {1}}, excludes)

        test_ratios = {
            (0, 0): 0.7,              (0, 2): 0.6, (0, 3): 0.8, (0, 4): 0.6, (0, 5): 0.6,
            (1, 0): 0.8,              (1, 2): 0.9, (1, 3): 0.7, (1, 4): 0.9, (1, 5): 0.7,

            (3, 0): 0.8,              (3, 2): 0.7, (3, 3): 0.7, (3, 4): 0.7, (3, 5): 0.9
        }
        maxes = []
        ratios = dc._get_ratios(excludes, maxes, False, False)
        with self.subTest('with `excludes` for ratio==1.0 subtest'):
            self.assertDictEqual(test_ratios, ratios)
            self.assertListEqual([], maxes)
            self.assertDictEqual({'u': {2}, 's': {1}}, excludes)

        test_ratios = {
            (0, 0): 0.7, (0, 1): 0.5, (0, 2): 0.6, (0, 3): 0.8, (0, 4): 0.6, (0, 5): 0.6,

            (2, 0): 0.6, (2, 1): 1.0,
            (3, 0): 0.8,              (3, 2): 0.7, (3, 3): 0.7, (3, 4): 0.7, (3, 5): 0.9
        }
        excludes, maxes = {'u': {1}}, []
        ratios = dc._get_ratios(excludes, maxes, False, False)
        with self.subTest('with `excludes` for `u`==1 subtest'):
            self.assertDictEqual(test_ratios, ratios)
            self.assertListEqual([((2, 1), 1.0)], maxes)
            self.assertDictEqual({'u': {1, 2}, 's': {1}}, excludes)

        test_ratios = {
            (0, 0): 0.7, (0, 1): 0.5,              (0, 3): 0.8, (0, 4): 0.6, (0, 5): 0.6,
            (1, 0): 0.8, (1, 1): 0.6,              (1, 3): 0.7, (1, 4): 0.9, (1, 5): 0.7,
            (2, 0): 0.6, (2, 1): 1.0,
            (3, 0): 0.8,                           (3, 3): 0.7, (3, 4): 0.7, (3, 5): 0.9
        }
        excludes, maxes = {'s': {2}}, []
        ratios = dc._get_ratios(excludes, maxes, False, False)
        with self.subTest('with `excludes` for `s`==2 subtest'):
            self.assertDictEqual(test_ratios, ratios)
            self.assertListEqual([((2, 1), 1.0)], maxes)
            self.assertDictEqual({'u': {2}, 's': {1, 2}}, excludes)

        dc.u = dc.s.copy()
        excludes, maxes = {}, []
        ratios = dc._get_ratios(excludes, maxes, False, False)
        test_ratios = {
            (0, 0): 1.0,
                         (1, 1): 1.0,
                                      (2, 2): 1.0,
                                                   (3, 3): 1.0,
                                                                (4, 4): 1.0,
                                                                             (5, 5): 1.0
        }

        test_maxes = [((0, 0), 1.0), ((1, 1), 1.0), ((2, 2), 1.0), ((3, 3), 1.0), ((4, 4), 1.0), ((5, 5), 1.0)]
        with self.subTest('equality subtest'):
            self.assertDictEqual(test_ratios, ratios)
            self.assertListEqual(test_maxes, maxes)
            self.assertDictEqual({'u': {0, 1, 2, 3, 4, 5}, 's': {0, 1, 2, 3, 4, 5}}, excludes)

        random.shuffle(dc.u)
        excludes, maxes = {}, []
        ratios = dc._get_ratios(excludes, maxes, False, False)
        with self.subTest('s == shuffle(u) subtest'):
            # indirect testing of appropriate work
            # optimisation has worked
            self.assertLess(len(ratios), len(dc.s)*len(dc.u))
            # all of matches were found and all of matches are unique
            exact_matches = {usi: r for usi, r in ratios.items() if r == 1.0}
            self.assertEqual(len(dc.u), sum(exact_matches.values()))
            # `exclude` embrace all `si` and `ui`
            self.assertDictEqual({'u': {0, 1, 2, 3, 4, 5}, 's': {0, 1, 2, 3, 4, 5}}, excludes)

        dc.u, dc.s = [], []
        excludes, maxes = {}, []
        ratios = dc._get_ratios(excludes, maxes, False, False)
        with self.subTest('empty subtest'):
            self.assertDictEqual({}, ratios)
            self.assertListEqual([], maxes)
            self.assertDictEqual({}, excludes)

    def test__get_matches(self):
        """
             | ltp | udp | smtp | tftp | sftp | umtp|
        https|  0.7|  0.5|   0.6|   0.8|   0.6| 0.6
          stp|  0.8|  0.6|   0.9|   0.7|   0.9| 0.7
          udp|  0.6|  1.0|   NA |   NA |   NA | NA
          utp|  0.8|  NA |   0.7|   0.7|   0.7| 0.9
        """

        s_list = [{'key': v} for v in ('ltp', 'udp', 'smtp', 'tftp', 'sftp', 'umtp')]
        u_list = [{'key': v} for v in ('https', 'stp', 'udp', 'utp')]
        dc = DataMatcher(s_list, u_list)
        dc.ratio_round_precision = 1
        matches = dc._get_matches()

        test_matches = [((2, 1), 1.0), ((1, 2), 0.9), ((3, 5), 0.9), ((0, 3), 0.8)]
        # u.'udp' -> u.'udp', u.'stp' -> u.'smtp', u.'utp' -> u.'umtp', u.'https' -> u.'tftp'
        with self.subTest('main subtest'):
            self.assertListEqual(test_matches, matches)

        test_matches = [((1, 2), 0.9), ((2, 1), 0.9), ((3, 5), 0.9), ((0, 3), 0.8)]
        # equal only is (2,1) -> 'udp'
        dc.s[1]['key'] = 'udp_'
        matches = dc._get_matches()
        with self.subTest('main - has no equal (max ratio < 1)'):
            self.assertListEqual(test_matches, matches)

        dc.s, dc.u = [], u_list
        matches = dc._get_matches()
        with self.subTest('`s` is empty subtest'):
            self.assertListEqual([], matches)

        dc.s, dc.u = s_list, []
        matches = dc._get_matches()
        with self.subTest('`u` is empty subtest'):
            self.assertListEqual([], matches)

        dc.s, dc.u = [], []
        matches = dc._get_matches()
        with self.subTest('both are empty subtest'):
            self.assertListEqual([], matches)


    def test_match(self):
        """
             | ltp | udp | smtp | tftp | sftp | umtp|
        https|  0.7|  0.5|   0.6|   0.8|   0.6| 0.6
          stp|  0.8|  0.6|   0.9|   0.7|   0.9| 0.7
          udp|  0.6|  1.0|   NA |   NA |   NA | NA
          utp|  0.8|  NA |   0.7|   0.7|   0.7| 0.9
        """

        s_list = [{'key': v} for v in ('ltp', 'udp', 'smtp', 'tftp', 'sftp', 'umtp')]
        u_list = [{'key': v} for v in ('https', 'stp', 'udp', 'utp')]
        dc = DataMatcher(s_list, u_list)
        dc.ratio_round_precision = 1

        test_matches = {
            'u': [((1, 2), 0.9), ((3, 5), 0.9), ((0, 3), 0.8)],
            'i': [],
            'd': [((None, 0), 1.0), ((None, 4), 1.0)],
            'n': [((2, 1), 1.0)]
        }
        # u.'udp' -> u.'udp', u.'stp' -> u.'smtp', u.'utp' -> u.'umtp', u.'https' -> u.'tftp'
        with self.subTest('main #1'):
            matches = dc.match()
            self.assertEqual(test_matches, matches)

        test_matches = {
            'u': [((2, 1), 0.9), ((5, 3), 0.9), ((3, 0), 0.8)],
            'i': [((0, None), 1.0), ((4, None), 1.0)],
            'd': [],
            'n': [((1, 2), 1.0)]
        }
        dc.s, dc.u = dc.u, dc.s
        with self.subTest('main #2 (s <-> u)'):
            matches = dc.match()
            self.assertEqual(test_matches, matches)

        dc.u, dc.s = u_list, []
        test_matches = {
            'i': [((0, None), 1.0), ((1, None), 1.0), ((2, None), 1.0), ((3, None), 1.0)],
            'u': [], 'd': [], 'n': []
        }
        with self.subTest('s is empty'):
            matches = dc.match()
            self.assertEqual(test_matches, matches)

        dc.u, dc.s = [], s_list
        test_matches = {
            'd': [((None, 0), 1.0), ((None, 1), 1.0), ((None, 2), 1.0), ((None, 3), 1.0),
                  ((None, 4), 1.0), ((None, 5), 1.0)],
            'u': [], 'i': [], 'n': []
        }
        with self.subTest('u is empty'):
            matches = dc.match()
            self.assertEqual(test_matches, matches)

        dc.u, dc.s = [], []
        test_matches = {'d': [], 'u': [], 'i': [], 'n': []}
        with self.subTest('both are empty'):
            matches = dc.match()
            self.assertEqual(test_matches, matches)

