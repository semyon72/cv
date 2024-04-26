# IDE: PyCharm
# Project: cv
# Path: ${DIR_PATH}
# File: ${FILE_NAME}
# Contact: Semyon Mamonov <semyon.mamonov@gmail.com>
# Created by ox23 at 2023-10-23 (y-m-d) 9:32 PM
import datetime
import functools
import random

from django.test import TestCase

from apps.cv.compare import DataMatcher, DateRangeCrossing, DateRangeMatcher, CrossingType


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
            (3, 0): 0.8, (3, 2): 0.7, (3, 3): 0.7, (3, 4): 0.7, (3, 5): 0.9
        }
        with self.subTest('main subtest'):
            self.assertDictEqual(test_ratios, ratios)
            self.assertListEqual([((2, 1), 1.0)], maxes)
            self.assertDictEqual({'u': {2}, 's': {1}}, excludes)

        test_ratios = {
            (0, 0): 0.7, (0, 2): 0.6, (0, 3): 0.8, (0, 4): 0.6, (0, 5): 0.6,
            (1, 0): 0.8, (1, 2): 0.9, (1, 3): 0.7, (1, 4): 0.9, (1, 5): 0.7,

            (3, 0): 0.8, (3, 2): 0.7, (3, 3): 0.7, (3, 4): 0.7, (3, 5): 0.9
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
            (3, 0): 0.8, (3, 2): 0.7, (3, 3): 0.7, (3, 4): 0.7, (3, 5): 0.9
        }
        excludes, maxes = {'u': {1}}, []
        ratios = dc._get_ratios(excludes, maxes, False, False)
        with self.subTest('with `excludes` for `u`==1 subtest'):
            self.assertDictEqual(test_ratios, ratios)
            self.assertListEqual([((2, 1), 1.0)], maxes)
            self.assertDictEqual({'u': {1, 2}, 's': {1}}, excludes)

        test_ratios = {
            (0, 0): 0.7, (0, 1): 0.5, (0, 3): 0.8, (0, 4): 0.6, (0, 5): 0.6,
            (1, 0): 0.8, (1, 1): 0.6, (1, 3): 0.7, (1, 4): 0.9, (1, 5): 0.7,
            (2, 0): 0.6, (2, 1): 1.0,
            (3, 0): 0.8, (3, 3): 0.7, (3, 4): 0.7, (3, 5): 0.9
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
            self.assertLess(len(ratios), len(dc.s) * len(dc.u))
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


class TestDateRangeCrossing(TestCase):

    def test_date_ranges(self):
        dates = [
            [datetime.date.today(), datetime.date.today()],
            [None, None],
            [None, datetime.date.today()],
            [datetime.date.today(), None],
            [str(datetime.date.today()), str(datetime.date.today())],
        ]
        drc = DateRangeCrossing(date_ranges=dates)

        for dr in drc.date_ranges:
            self.assertTrue(issubclass(type(dr[0]), (datetime.date, type(None))))
            self.assertTrue(issubclass(type(dr[1]), (datetime.date, type(None))))

    def test_date_ranges_db_greater_de(self):
        db, de = datetime.date.today(), datetime.date.today() - datetime.timedelta(days=1)

        dates = [
            [db, de],
        ]
        with self.assertRaises(ValueError) as exc:
            drc = DateRangeCrossing(date_ranges=dates)

        exps = f'Date begin "{db}" must be less or equal date end "{de}"'
        self.assertEqual(exps, str(exc.exception))

    def test__sort_dates(self):
        dates = [
            [datetime.date.fromisoformat('2022-01-01'), datetime.date.fromisoformat('2022-01-10')],
            [None, None],
            [None, datetime.date.fromisoformat('2021-10-30')],
            [datetime.date.fromisoformat('2021-11-30'), None],
            ['2021-12-10', '2021-12-31']
        ]
        drc = DateRangeCrossing(date_ranges=dates)
        drc._natural_sort(drc.date_ranges)
        exp = [
            (None, datetime.date(2021, 10, 30)),
            (None, None),
            (datetime.date(2021, 11, 30), None),
            (datetime.date(2021, 12, 10), datetime.date(2021, 12, 31)),
            (datetime.date(2022, 1, 1), datetime.date(2022, 1, 10))
        ]
        self.assertEqual(exp, drc.date_ranges)

    def test__sort_dates_1(self):
        dates = [
            ['2022-01-01', '2022-01-10'], ['2022-01-11', '2022-01-20'], ['2022-01-07', '2022-01-15'],
            ['2022-01-09', '2022-01-31'], ['2022-03-01', '2022-03-31'], ['2022-03-20', '2022-04-30'],
            ['2022-01-09', None],
        ]
        random.shuffle(dates)

        drc = DateRangeCrossing(date_ranges=dates)
        drc._natural_sort(drc.date_ranges)
        exp = [
            (datetime.date(2022, 1, 1), datetime.date(2022, 1, 10)),
            (datetime.date(2022, 1, 7), datetime.date(2022, 1, 15)),
            (datetime.date(2022, 1, 9), datetime.date(2022, 1, 31)),
            (datetime.date(2022, 1, 9), None),
            (datetime.date(2022, 1, 11), datetime.date(2022, 1, 20)),
            (datetime.date(2022, 3, 1), datetime.date(2022, 3, 31)),
            (datetime.date(2022, 3, 20), datetime.date(2022, 4, 30))
        ]
        self.assertEqual(exp, drc.date_ranges)

    def test__calc_crossings(self):
        dates = [
            ['2022-01-01', '2022-01-10'],  # 1.1 -> crosses 1.2
            ['2022-01-12', '2022-01-20'],  # 1.3 -> crosses 1.2, 4, 5
            ['2022-01-07', '2022-01-15'],  # 1.2 -> crosses 1.1, 1.3, 4, 5
            ['2022-01-11', '2022-01-31'],  # 4 -> crosses  1.2, 1.3, 5
            ['2022-03-01', '2022-03-31'],  # 3 -> crosses  2, 5
            ['2022-03-20', '2022-04-30'],  # 2 -> crosses  3, 5
            ['2022-01-11', None],  # 5 -> crosses 1.2, 1.3, 4, 3, 2
        ]

        drc = DateRangeCrossing(date_ranges=dates)
        res = drc._calc_crossings()
        exp = {
            (datetime.date(2022, 1, 1), datetime.date(2022, 1, 10)): [
                [(datetime.date(2022, 1, 7), datetime.date(2022, 1, 15))], 0],
            (datetime.date(2022, 1, 12), datetime.date(2022, 1, 20)): [
                [(datetime.date(2022, 1, 7), datetime.date(2022, 1, 15)),
                 (datetime.date(2022, 1, 11), datetime.date(2022, 1, 31)), (datetime.date(2022, 1, 11), None)], 1],
            (datetime.date(2022, 1, 7), datetime.date(2022, 1, 15)): [
                [(datetime.date(2022, 1, 1), datetime.date(2022, 1, 10)),
                 (datetime.date(2022, 1, 12), datetime.date(2022, 1, 20)),
                 (datetime.date(2022, 1, 11), datetime.date(2022, 1, 31)), (datetime.date(2022, 1, 11), None)], 2],
            (datetime.date(2022, 1, 11), datetime.date(2022, 1, 31)): [
                [(datetime.date(2022, 1, 12), datetime.date(2022, 1, 20)),
                 (datetime.date(2022, 1, 7), datetime.date(2022, 1, 15)), (datetime.date(2022, 1, 11), None)], 3],
            (datetime.date(2022, 3, 1), datetime.date(2022, 3, 31)): [
                [(datetime.date(2022, 3, 20), datetime.date(2022, 4, 30)), (datetime.date(2022, 1, 11), None)], 4],
            (datetime.date(2022, 3, 20), datetime.date(2022, 4, 30)): [
                [(datetime.date(2022, 3, 1), datetime.date(2022, 3, 31)), (datetime.date(2022, 1, 11), None)], 5],
            (datetime.date(2022, 1, 11), None): [[(datetime.date(2022, 1, 12), datetime.date(2022, 1, 20)),
                                                  (datetime.date(2022, 1, 7), datetime.date(2022, 1, 15)),
                                                  (datetime.date(2022, 1, 11), datetime.date(2022, 1, 31)),
                                                  (datetime.date(2022, 3, 1), datetime.date(2022, 3, 31)),
                                                  (datetime.date(2022, 3, 20), datetime.date(2022, 4, 30))], 6]
        }
        self.assertEqual(exp, res)

    def test__calc_crossings_sorted(self):
        dates = [
            ['2022-01-01', '2022-01-10'],  # 1.1 -> crosses 1.2
            ['2022-01-12', '2022-01-20'],  # 1.3 -> crosses 1.2, 4, 5
            ['2022-01-07', '2022-01-15'],  # 1.2 -> crosses 1.1, 1.3, 4, 5
            ['2022-01-11', '2022-01-31'],  # 4 -> crosses  1.2, 1.3, 5
            ['2022-03-01', '2022-03-31'],  # 3 -> crosses  2, 5
            ['2022-03-20', '2022-04-30'],  # 2 -> crosses  3, 5
            ['2022-01-11', None],  # 5 -> crosses 1.2, 1.3, 4, 3, 2
        ]

        drc = DateRangeCrossing(date_ranges=dates)
        res = drc._calc_crossings(True)
        exp = {
            (datetime.date(2022, 1, 1), datetime.date(2022, 1, 10)): [
                [(datetime.date(2022, 1, 7), datetime.date(2022, 1, 15))], 0],

            (datetime.date(2022, 3, 1), datetime.date(2022, 3, 31)): [
                [(datetime.date(2022, 3, 20), datetime.date(2022, 4, 30)), (datetime.date(2022, 1, 11), None)], 4],

            (datetime.date(2022, 3, 20), datetime.date(2022, 4, 30)): [
                [(datetime.date(2022, 3, 1), datetime.date(2022, 3, 31)), (datetime.date(2022, 1, 11), None)], 5],

            (datetime.date(2022, 1, 11), datetime.date(2022, 1, 31)): [
                [(datetime.date(2022, 1, 12), datetime.date(2022, 1, 20)),
                 (datetime.date(2022, 1, 7), datetime.date(2022, 1, 15)), (datetime.date(2022, 1, 11), None)], 3],

            (datetime.date(2022, 1, 12), datetime.date(2022, 1, 20)): [
                [(datetime.date(2022, 1, 7), datetime.date(2022, 1, 15)),
                 (datetime.date(2022, 1, 11), datetime.date(2022, 1, 31)), (datetime.date(2022, 1, 11), None)], 1],

            (datetime.date(2022, 1, 7), datetime.date(2022, 1, 15)): [
                [(datetime.date(2022, 1, 1), datetime.date(2022, 1, 10)),
                 (datetime.date(2022, 1, 12), datetime.date(2022, 1, 20)),
                 (datetime.date(2022, 1, 11), datetime.date(2022, 1, 31)), (datetime.date(2022, 1, 11), None)], 2],

            (datetime.date(2022, 1, 11), None): [[(datetime.date(2022, 1, 12), datetime.date(2022, 1, 20)),
                                                  (datetime.date(2022, 1, 7), datetime.date(2022, 1, 15)),
                                                  (datetime.date(2022, 1, 11), datetime.date(2022, 1, 31)),
                                                  (datetime.date(2022, 3, 1), datetime.date(2022, 3, 31)),
                                                  (datetime.date(2022, 3, 20), datetime.date(2022, 4, 30))], 6]
        }
        self.assertEqual(exp, res)

    def test_min_crossings(self):
        dates = [
            ['2022-01-01', '2022-01-10'],  # 1.1 -> crosses 1.2
            ['2022-01-12', '2022-01-20'],  # 1.3 -> crosses 1.2, 4, 5
            ['2022-01-07', '2022-01-15'],  # 1.2 -> crosses 1.1, 1.3, 4, 5
            ['2022-01-11', '2022-01-31'],  # 4 -> crosses  1.2, 1.3, 5
            ['2022-03-01', '2022-03-31'],  # 3 -> crosses  2, 5
            ['2022-03-20', '2022-04-30'],  # 2 -> crosses  3, 5
            ['2022-01-11', None],  # 5 -> crosses 1.2, 1.3, 4, 3, 2
        ]

        drc = DateRangeCrossing(date_ranges=dates)
        res = drc.min_crossings()
        exp = [(datetime.date(2022, 1, 1), datetime.date(2022, 1, 10)),
               (datetime.date(2022, 1, 12), datetime.date(2022, 1, 20)),
               (datetime.date(2022, 3, 1), datetime.date(2022, 3, 31))],\
              [(datetime.date(2022, 1, 7), datetime.date(2022, 1, 15)),
               (datetime.date(2022, 1, 11), datetime.date(2022, 1, 31)),
               (datetime.date(2022, 1, 11), None),
               (datetime.date(2022, 3, 20), datetime.date(2022, 4, 30))]
        self.assertEqual(exp, res)

    def test_crossings(self):
        dates = [
            ['2022-01-01', '2022-01-10'],
            ['2022-01-11', None],
            ['2022-01-12', '2022-01-20'],
            ['2022-01-07', '2022-01-15'],
            ['2022-01-11', '2022-01-31'],
        ]

        drc = DateRangeCrossing(date_ranges=dates)
        res = drc.crossings()
        exp = [(datetime.date(2022, 1, 1), datetime.date(2022, 1, 10)),
               (datetime.date(2022, 1, 11), None)],\
              [(datetime.date(2022, 1, 7), datetime.date(2022, 1, 15)),
               (datetime.date(2022, 1, 12), datetime.date(2022, 1, 20)),
               (datetime.date(2022, 1, 11), datetime.date(2022, 1, 31))]
        self.assertEqual(exp, res)


class TestDateRangeMatcher(TestCase):

    def test__calc_crossing_distances(self):
        haystack = [
            ['2022-01-10', '2022-01-20'],
            ['2022-01-25', '2022-01-27'],
            ['2022-01-26', '2022-01-31'],
            ['2022-02-01', None]]
        drm = DateRangeMatcher(haystack, [])

        # no crossings
        drm.needles.date_ranges = [['2022-01-21', '2022-01-24']]
        res = drm._calc_crossing_distances(drm.haystack.date_ranges, drm.needles.date_ranges[0])
        self.assertEqual([], res)

        # crossings two ranges, first is better
        drm.needles.date_ranges = [['2022-01-25', '2022-01-28']]
        res = drm._calc_crossing_distances(drm.haystack.date_ranges, drm.needles.date_ranges[0])
        exp = [(2, (datetime.date(2022, 1, 25), datetime.date(2022, 1, 27)), CrossingType.partial),
               (2, (datetime.date(2022, 1, 26), datetime.date(2022, 1, 31)), CrossingType.partial)]
        self.assertEqual(exp, res)

        # crossings two ranges, second is better
        drm.needles.date_ranges = [['2022-01-25', '2022-01-30']]
        res = drm._calc_crossing_distances(drm.haystack.date_ranges, drm.needles.date_ranges[0])
        exp = [(2, (datetime.date(2022, 1, 25), datetime.date(2022, 1, 27)), CrossingType.partial),
               (4, (datetime.date(2022, 1, 26), datetime.date(2022, 1, 31)), CrossingType.partial)]
        self.assertEqual(exp, res)

        # partial crossing range + second include
        drm.needles.date_ranges = [['2022-01-26', '2022-01-30']]
        res = drm._calc_crossing_distances(drm.haystack.date_ranges, drm.needles.date_ranges[0])
        exp = [(1, (datetime.date(2022, 1, 25), datetime.date(2022, 1, 27)), CrossingType.partial),
               (4, (datetime.date(2022, 1, 26), datetime.date(2022, 1, 31)), CrossingType.include)]
        self.assertEqual(exp, res)

        # exact is second
        drm.needles.date_ranges = [['2022-01-26', '2022-01-31']]
        res = drm._calc_crossing_distances(drm.haystack.date_ranges, drm.needles.date_ranges[0])
        exp = [(1, (datetime.date(2022, 1, 25), datetime.date(2022, 1, 27)), CrossingType.partial),
               (5, (datetime.date(2022, 1, 26), datetime.date(2022, 1, 31)), CrossingType.exact)]
        self.assertEqual(exp, res)

        # properly works with None
        drm.needles.date_ranges = [['2022-02-03', '2022-02-20']]
        res = drm._calc_crossing_distances(drm.haystack.date_ranges, drm.needles.date_ranges[0])
        exp = [(17, (datetime.date(2022, 2, 1), None), CrossingType.include)]
        self.assertEqual(exp, res)

        # properly works with None
        drm.needles.date_ranges = [['2022-01-01', None]]
        res = drm._calc_crossing_distances(drm.haystack.date_ranges, drm.needles.date_ranges[0])
        exp = [(10, (datetime.date(2022, 1, 10), datetime.date(2022, 1, 20)), CrossingType.partial),
               (2, (datetime.date(2022, 1, 25), datetime.date(2022, 1, 27)), CrossingType.partial),
               (5, (datetime.date(2022, 1, 26), datetime.date(2022, 1, 31)), CrossingType.partial),
               (2913872, (datetime.date(2022, 2, 1), None), CrossingType.partial)]
        self.assertEqual(exp, res)

    def test__calc_max_crossing_distance(self):
        haystack = [
            ['2022-01-10', '2022-01-20'],
            ['2022-01-25', '2022-01-27'],
            ['2022-01-26', '2022-01-31'],
            ['2022-02-01', None]]
        drm = DateRangeMatcher(haystack, [])

        # no crossings
        drm.needles.date_ranges = [['2022-01-21', '2022-01-24']]
        res = drm._calc_max_crossing_distance(drm.haystack.date_ranges, drm.needles.date_ranges[0])
        self.assertIsNone(res)

        # crossings two ranges, first is better
        drm.needles.date_ranges = [['2022-01-25', '2022-01-28']]
        res = drm._calc_max_crossing_distance(drm.haystack.date_ranges, drm.needles.date_ranges[0])
        self.assertIsNotNone(res)
        distance, haystack_item, crossing_type = res
        self.assertEqual(['2022-01-25', '2022-01-27'], [str(v) for v in haystack_item])
        self.assertEqual(CrossingType.partial, crossing_type)
        self.assertEqual(2, distance)

        # crossings two ranges, second is better
        drm.needles.date_ranges = [['2022-01-25', '2022-01-30']]
        res = drm._calc_max_crossing_distance(drm.haystack.date_ranges, drm.needles.date_ranges[0])
        self.assertEqual(
            (4, (datetime.date(2022, 1, 26), datetime.date(2022, 1, 31)), CrossingType.partial),
            res
         )

        # partial crossing range
        drm.needles.date_ranges = [['2022-01-25', '2022-01-30']]
        res = drm._calc_max_crossing_distance(drm.haystack.date_ranges, drm.needles.date_ranges[0])
        self.assertEqual((4, (datetime.date(2022, 1, 26), datetime.date(2022, 1, 31)), CrossingType.partial), res)

        # exact
        drm.needles.date_ranges = [['2022-01-26', '2022-01-31']]
        res = drm._calc_max_crossing_distance(drm.haystack.date_ranges, drm.needles.date_ranges[0])
        self.assertEqual((5, (datetime.date(2022, 1, 26), datetime.date(2022, 1, 31)), CrossingType.exact), res)

        # properly works with None
        drm.needles.date_ranges = [['2022-02-03', '2022-02-20']]
        res = drm._calc_max_crossing_distance(drm.haystack.date_ranges, drm.needles.date_ranges[0])
        self.assertEqual((17, (datetime.date(2022, 2, 1), None), CrossingType.include), res)

        # properly works with None
        drm.needles.date_ranges = [['2022-01-01', None]]
        res = drm._calc_max_crossing_distance(drm.haystack.date_ranges, drm.needles.date_ranges[0])
        self.assertEqual((2913872, (datetime.date(2022, 2, 1), None), CrossingType.partial), res)

    def test__calc_prioritized_crossing(self):
        haystack = [
            ['2022-01-10', '2022-01-31'],
            ['2022-01-17', '2022-01-24'],
            ['2022-01-20', '2022-01-24'],
            ['2022-01-17', None]]
        drm = DateRangeMatcher(haystack, [])

        func = drm._calc_prioritized_crossing

        # no crossings
        drm.needles.date_ranges = [['2022-01-01', '2022-01-09']]
        res = func(drm.haystack.date_ranges, drm.needles.date_ranges[0])
        self.assertIsNone(res)

        # exact
        drm.needles.date_ranges = [['2022-01-20', '2022-01-24']]
        res = func(drm.haystack.date_ranges, drm.needles.date_ranges[0])
        self.assertIsNotNone(res)
        self.assertEqual(
            ((datetime.date(2022, 1, 20), datetime.date(2022, 1, 24)), CrossingType.exact), res[1:]
        )

        # include, crossings all, narrowest better
        drm.needles.date_ranges = [['2022-01-18', '2022-01-24']]
        res = func(drm.haystack.date_ranges, drm.needles.date_ranges[0])
        self.assertIsNotNone(res)
        self.assertEqual(
            ((datetime.date(2022, 1, 17), datetime.date(2022, 1, 24)), CrossingType.include), res[1:]
        )

        # partial, crossings some ranges, than more that is better
        haystack[-1] = ['2022-01-17', '2022-02-20']
        drm.haystack.date_ranges = haystack
        drm.needles.date_ranges = [['2022-01-18', None]]
        res = func(drm.haystack.date_ranges, drm.needles.date_ranges[0])
        self.assertIsNotNone(res)
        self.assertEqual(
            ((datetime.date(2022, 1, 17), datetime.date(2022, 2, 20)), CrossingType.partial), res[1:]
        )

    def test_match(self):
        haystack = [
            ['2022-01-10', '2022-01-31'], ['2022-02-09', '2022-02-24'], ['2022-03-11', '2022-03-25'],  # 1, 2, 3
            ['2022-01-20', '2022-02-14'],  # 4
            ['2022-02-12', None],  # 5
            ['2022-02-01', '2022-02-12'],  # 6
        ]

        needles = [
            ['2022-01-10', '2022-01-17'], ['2022-01-18', '2022-01-31'],  # for 1
            ['2022-02-09', '2022-02-13'], ['2022-02-14', '2022-02-24'],  # for 2
            ['2022-03-11', '2022-03-25'],  # for 3
            ['2022-01-18', '2022-02-14'],  # for 4
            ['2022-02-11', None],   # for 5
            ['2022-02-03', '2022-02-07'],  # for 6
            ['2022-01-01', '2022-01-03'],  # for None haystack
        ]

        drm = DateRangeMatcher(haystack, needles)
        haystack_uncrossed, haystack_crossed = drm.haystack.min_crossings()
        exp = [
            (datetime.date(2022, 1, 10), datetime.date(2022, 1, 31)),
            (datetime.date(2022, 2, 9), datetime.date(2022, 2, 24)),
            (datetime.date(2022, 3, 11), datetime.date(2022, 3, 25))
        ]
        self.assertEqual(haystack_uncrossed, exp)
        exp = [
            (datetime.date(2022, 1, 20), datetime.date(2022, 2, 14)),
            (datetime.date(2022, 2, 1), datetime.date(2022, 2, 12)),
            (datetime.date(2022, 2, 12), None)
        ]
        self.assertEqual(haystack_crossed, exp)

        needle_uncrossed, needle_crossed = drm.needles.min_crossings()
        exp = [
            (datetime.date(2022, 1, 1), datetime.date(2022, 1, 3)),
            (datetime.date(2022, 1, 10), datetime.date(2022, 1, 17)),
            (datetime.date(2022, 1, 18), datetime.date(2022, 1, 31)),
            (datetime.date(2022, 2, 3), datetime.date(2022, 2, 7)),
            (datetime.date(2022, 2, 9), datetime.date(2022, 2, 13)),
            (datetime.date(2022, 2, 14), datetime.date(2022, 2, 24)),
            (datetime.date(2022, 3, 11), datetime.date(2022, 3, 25))
        ]
        self.assertEqual(needle_uncrossed, exp)
        exp = [
            (datetime.date(2022, 1, 18), datetime.date(2022, 2, 14)),
            (datetime.date(2022, 2, 11), None)
        ]
        self.assertEqual(needle_crossed, exp)

        res = drm.match()
        exp = {
            (datetime.date(2022, 1, 10), datetime.date(2022, 1, 17)):
                (7, (datetime.date(2022, 1, 10), datetime.date(2022, 1, 31)), CrossingType.include),
            (datetime.date(2022, 1, 18), datetime.date(2022, 1, 31)):
                (13, (datetime.date(2022, 1, 10), datetime.date(2022, 1, 31)), CrossingType.include),
            (datetime.date(2022, 2, 9), datetime.date(2022, 2, 13)):
                (4, (datetime.date(2022, 2, 9), datetime.date(2022, 2, 24)), CrossingType.include),
            (datetime.date(2022, 2, 14), datetime.date(2022, 2, 24)):
                (10, (datetime.date(2022, 2, 9), datetime.date(2022, 2, 24)), CrossingType.include),
            (datetime.date(2022, 3, 11), datetime.date(2022, 3, 25)):
                (14, (datetime.date(2022, 3, 11), datetime.date(2022, 3, 25)), CrossingType.exact),
            (datetime.date(2022, 1, 18), datetime.date(2022, 2, 14)):
                (25, (datetime.date(2022, 1, 20), datetime.date(2022, 2, 14)), CrossingType.partial),
            (datetime.date(2022, 2, 11), None):
                (2913861, (datetime.date(2022, 2, 12), None), CrossingType.partial),
            (datetime.date(2022, 2, 3), datetime.date(2022, 2, 7)):
                (4, (datetime.date(2022, 2, 1), datetime.date(2022, 2, 12)), CrossingType.include),
            (datetime.date(2022, 1, 1), datetime.date(2022, 1, 3)): None
        }

        self.assertEqual(exp, res)

    def test_match1(self):
        haystack = [
            ['2022-01-10', '2022-01-31'], ['2022-02-09', '2022-02-24'], ['2022-03-11', '2022-03-25'],  # 1, 2, 3
            ['2022-01-20', '2022-02-14'],  # 4
            ['2022-02-12', None],  # 5
            ['2022-02-01', '2022-02-12'],  # 6
        ]

        needles = [
            ['2022-01-10', '2022-01-17'], ['2022-01-18', '2022-01-31'],  # for 1
            ['2022-02-09', '2022-02-13'], ['2022-02-14', '2022-02-24'],  # for 2
            ['2022-03-11', '2022-03-25'],  # for 3
            ['2022-01-18', '2022-02-14'],  # for 4
            ['2022-02-11', None],   # for 5
            ['2022-02-03', '2022-02-07'],  # for 6
            ['2022-01-01', '2022-01-03'],  # for None haystack
        ]

        drm = DateRangeMatcher(haystack, needles)

        res = drm.match1()
        exp = {
            (datetime.date(2022, 1, 10), datetime.date(2022, 1, 17)):
                (7, (datetime.date(2022, 1, 10), datetime.date(2022, 1, 31)), CrossingType.include),
            (datetime.date(2022, 1, 18), datetime.date(2022, 1, 31)):
                (13, (datetime.date(2022, 1, 10), datetime.date(2022, 1, 31)), CrossingType.include),
            (datetime.date(2022, 2, 9), datetime.date(2022, 2, 13)):
                (4, (datetime.date(2022, 2, 9), datetime.date(2022, 2, 24)), CrossingType.include),
            (datetime.date(2022, 2, 14), datetime.date(2022, 2, 24)):
                (10, (datetime.date(2022, 2, 9), datetime.date(2022, 2, 24)), CrossingType.include),
            (datetime.date(2022, 3, 11), datetime.date(2022, 3, 25)):
                (14, (datetime.date(2022, 3, 11), datetime.date(2022, 3, 25)), CrossingType.exact),
            (datetime.date(2022, 1, 18), datetime.date(2022, 2, 14)):
                (25, (datetime.date(2022, 1, 20), datetime.date(2022, 2, 14)), CrossingType.partial),
            (datetime.date(2022, 2, 11), None):
                (2913861, (datetime.date(2022, 2, 12), None), CrossingType.partial),
            (datetime.date(2022, 2, 3), datetime.date(2022, 2, 7)):
                (4, (datetime.date(2022, 2, 1), datetime.date(2022, 2, 12)), CrossingType.include),
            (datetime.date(2022, 1, 1), datetime.date(2022, 1, 3)): None
        }

        self.assertEqual(exp, res)
