# IDE: PyCharm
# Project: cv
# Path: apps/cv
# File: compare.py
# Contact: Semyon Mamonov <semyon.mamonov@gmail.com>
# Created by ox23 at 2023-10-23 (y-m-d) 9:25 PM

import difflib
import functools
import hashlib
import json
import string
from collections import namedtuple
from typing import Union, Optional
from django.conf import settings


ComparedItemInfoClass = namedtuple('ComparedItemInfo', ('ratio', 'idx', 'hash'))


class DictComparer:
    """

    Examples of the usage for dictionary comparison:
        d1 = {'one': "one", None: 'fffffff', 2:"two" }
        d = {'one': "one", '2':"two"}

        DictComparer(d, ['one', '2']) == DictComparer(d1, ['one', 2])
        => False

        d1 = {'one': "one", None: 'fffffff', '2':"two" }
        DictComparer(d) == d1
        => False
        DictComparer(d) == DictComparer(d1, DictComparer(d).keys)
        => True
        DictComparer(d) == DictComparer(d1)
        => False
        [*DictComparer(d1)]
        => [('2', 'two'), (None, 'fffffff'), ('one', 'one')]
        [*DictComparer(d1, False)]
        => [('one', 'one'), (None, 'fffffff'), ('2', 'two')]
        [*DictComparer(d1, [None])]
        => [(None, 'fffffff')]

        Hashes:

        hash(DictComparer(d1)) => -7114625023867469434
        DictComparer(d1).keys => ('2', None, 'one')
        hash(DictComparer(d)) => 135244955252348502
        DictComparer(d).keys => ('2', 'one')
        hash(DictComparer(d1, ['one', '2'])) => 2932402133618245007
        hash(DictComparer(d1, ['2', 'one'])) => 135244955252348502

        Note, during different sessions of the interpreter,
        the hashes will be different - not the same as in the example above

        Compare with:
            d = {'one': "one", '2':"two", 'three': 'three'}
            d1 = {'one': "one", None: 'fffffff', '2':"two" }
            d2 = {'one': "one", None: 'fffffff', '2':"two xvbxvcbxvcb" }
            d3= {'one': "onevc x xvb", '2':"two"}
            dc = DictComparer(d)

            dc._get_compare_info([d1, d2, d3])
            {
                0: {'2': 1.0, 'one': 1.0, 'three': 0.0},
                1: {'2': 0.45454545454545453, 'one': 1.0, 'three': 0.0},
                2: {'2': 1.0, 'one': 0.5555555555555556, 'three': 0.0}
            }
            dc.compare([d1, d2, d3])
            [
                ComparedItemInfo(ratio=0.6667, idx=0, hash=-4143811306588780073),
                ComparedItemInfo(ratio=0.4848, idx=1, hash=-7969702530700133796),
                ComparedItemInfo(ratio=0.5185, idx=2, hash=3253297673847101534)
            ]
            dc.keys = ['one', '2']
            dc._get_compare_info([d1, d2, d3])
            {
                0: {'one': 1.0, '2': 1.0},
                1: {'one': 1.0, '2': 0.45454545454545453},
                2: {'one': 0.5555555555555556, '2': 1.0}
            }
            dc.compare([d1, d2, d3])
            [
                ComparedItemInfo(ratio=1.0, idx=0, hash=-9080248071819053253),
                ComparedItemInfo(ratio=0.7273, idx=1, hash=-5528572130579073723),
                ComparedItemInfo(ratio=0.7778, idx=2, hash=-4576142372570496859)
            ]

            Notice that if you change the order of the keys, the hashes also change

            dc.keys = ['2', 'one']
            dc.compare([d1, d2, d3])
            [
                ComparedItemInfo(ratio=1.0, idx=0, hash=-4143811306588780073),
                ComparedItemInfo(ratio=0.7273, idx=1, hash=-7969702530700133796),
                ComparedItemInfo(ratio=0.7778, idx=2, hash=3253297673847101534)
            ]
            dc._get_compare_info([d1, d2, d3])
            {
                0: {'2': 1.0, 'one': 1.0},
                1: {'2': 0.45454545454545453, 'one': 1.0},
                2: {'2': 1.0, 'one': 0.5555555555555556}
            }
    """

    _empty = object()
    ratio_round_precision = 4

    def __init__(self, d: dict, keys: Union[list, tuple, None, bool] = None) -> None:
        self._d = {}
        self.set_d(d, keys)

    @property
    def keys(self):
        return self._keys

    @keys.setter
    def keys(self, keys: Union[list, tuple, None, bool]):
        """
        If `keys` is None then the keys of self._d will be sorted as list.sort() but if `keys` [] or tuple() ...
        or were evaluated as empty (bool) then the order will be determined by self._d.keys()
        """
        d_keys = list(self._d)
        if not keys:
            if keys is None:
                d_keys.sort(key=self._json_typed_val)
            self._keys = tuple(d_keys)
        else:
            extra = set(keys) - set(d_keys)
            if extra:
                raise ValueError(f'The parameter `keys` has extra keys {extra} that dict has no.'
                                 f' Allowed keys are {d_keys}')
            self._keys = tuple(keys)

    def set_d(self, d: dict, keys: Union[list, tuple, None] = None) -> None:
        self._d = d
        self.keys = keys

    @staticmethod
    def _json_typed_val(v):
        return v if isinstance(v, str) else (type(v).__name__ + ':' + str(v)).lower()

    def _get_dict_repr(self, d: dict) -> str:
        # Start from Python 3.7 - dictionary order is guaranteed to be insertion order.
        return json.dumps(
            {self._json_typed_val(k): v for k, v in self._iter_over_dict(d)},
            default=self._json_typed_val
        )

    def _get_hash(self, r: str) -> int:
        return hash(hashlib.md5(r.encode()).hexdigest())

    def __eq__(self, other):
        if not isinstance(other, DictComparer):
            other = DictComparer(other)
        return hash(self) == hash(other)

    def __hash__(self):
        return self._get_hash(self._get_dict_repr(self._d))

    def __iter__(self):
        return self._iter_over_dict()

    def _iter_over_dict(self, d: dict = None):
        """
        This applicable to any dictionary.
        If d is None then by default will use self._d
        It will calculate a difference between d.keys() and self.keys
        If they differ (order is taken into account) then the (k, v) pairs will be yielded in the order defined by self.keys.

        Notice, The default behaviour is initialization of keys by all keys from ._d with sorting
        """
        if d is None:
            d = self._d

        is_custom_keys = len(d) != len(self.keys)
        if not is_custom_keys:
            for k_, k in zip(self.keys, d):
                if k_ != k:
                    is_custom_keys = True
                    break

        keys = self.keys if is_custom_keys else d.keys()
        for k in keys:
            try:
                yield k, d[k]
            except KeyError:
                pass

    def _get_compare_info(self, others: list[dict], exclude_ids: list = None) -> dict[int, dict[str, float]]:
        """
            For optimisation we going through the keys in `self._d` and make resulting structure
            that will have a key that is index of `others` and value is result of comparison of each key.
            It means that, after the first outer pass it will contain the result of comparison `self._d['first_key']`
            along with all 'first_key' values of `others`

            For the purpose of optimization, `exclude_ids` can accept a list of indexes from `others`
             that should not be processed.

            Example of a comparison result:
            { idx_others: {key: ratio, key1: ratio, ....}, idx1_others: {key: ratio, key1: ratio, ....}, ... }
        """

        res: dict[int, dict[str, float]] = {}
        sm = difflib.SequenceMatcher(lambda c: c in string.whitespace)

        for ki, (k, v) in enumerate(self):
            sm.set_seq1(json.dumps(v, default=str))
            for oi, oitem in enumerate(others):
                if exclude_ids is not None and oi in exclude_ids:
                    continue

                ov, r = oitem.get(k, self._empty), .0
                if ov is not self._empty:
                    sm.set_seq2(json.dumps(ov, default=str))
                    r = sm.ratio()

                res.setdefault(oi, {})[k] = r
        return res

    def compare(self, others: list[dict], exclude_ids: list = None) -> list[ComparedItemInfoClass]:
        """
        `exclude_ids` can accept a list of indexes from `others` that should not be processed.
         For the purpose of optimization.

        It will return an array of named tuples of type ComparedItemInfoClass(ratio=..., idx=..., hash=...)
        as a result of comparing the current dictionary `self._d` with each element of `others`.

        If `others` or `self._d` are empty then result also be an empty array.
        """
        res = []
        for oi, ratios in self._get_compare_info(others, exclude_ids).items():
            ravg = sum(ratios.values()) / len(ratios)
            if self.ratio_round_precision is not None:
                ravg = round(ravg, self.ratio_round_precision)

            res.append(
                ComparedItemInfoClass(
                    ratio=ravg,
                    idx=oi,
                    hash=self._get_hash(self._get_dict_repr(dict(self._iter_over_dict(others[oi]))))
                )
            )

        return res


class DataMatcher:
    """
    DataMatcher has a primary goal, which is to identify the most relevant match between
    a list of dictionaries with source/stored data and a list of dictionaries with update/up-to-date data.

    An example that demonstrates this:

        import difflib
        import string
        sm = difflib.SequenceMatcher(lambda x: x in string.whitespace)
        u_list = ['http', 'smtp', 'utp', 'django']
        s_list = ['django rest framework', 'smtp', 'django', 'openssl']

        max_u_len = len(max(u_list, key=lambda x: len(x)))
        ... print(" "*max_u_len,*(f'{s:^{6}}' for s in s_list), sep='|')
        ... for ui, u in enumerate(u_list):
        ...     sm.set_seq1(u)
        ...     print(f'{u:>{max_u_len}}|', sep='', end='')
        ...     for si, s in enumerate(s_list):
        ...         sm.set_seq2(s)
        ...         print(f'{str(round(sm.ratio(),4)):>{max(6,len(s))}}|', end='')
        ...     print('')

          u/s |django rest framework| smtp |django|openssl ---> s
          http|                 0.08|   0.5|   0.0| 0.1818|
          smtp|                 0.16|   1.0|   0.0| 0.1818|
           utp|               0.0833|0.5714|   0.0|    0.2|
        django|               0.4444|   0.0|   1.0| 0.1538|

    We can see that 'smtp' (u[1] == s[1]) and 'django' (u[3] == s[3]) are equal,
     but other similarities will be resolved according to the their relationship (ratio) -
     'utp' -> 'openssl', 'http' -> 'django rest framework'
    """

    ratio_round_precision = DictComparer.ratio_round_precision

    def __init__(self, s: list[dict], u: list[dict]):
        """
            - s is "source/stored data"
            - u is "update/up-to-date data"
        """
        self.s: list[dict] = s
        self.u: list[dict] = u

    def _prepare_stored_dict(self, s: dict) -> dict:
        """
        It prepares the `s` (source/stored data) to data that can be compared with `u` (update/up-to-date data) and,
        probably, can be used for updating.
        Default implementation just returns a copy of `s`
        """
        return s.copy()

    def _prepare_update_dict(self, u: dict) -> dict:
        """
        It prepares the `u` (update/up-to-date data) to data that can be compared with `s` (source/stored data)
        Default implementation just returns a copy of `u`
        """
        return u.copy()

    def _exclude(self, ui: Optional[int], si: Optional[int], excludes: dict[str, set[int]]):
        for k, v in (('u', ui), ('s', si)):
            if v is not None:
                excludes.setdefault(k, set()).add(v)

    def _get_ratios(self, excludes: dict[str, set[int]], maxes: list[tuple[tuple[int, int], float]],
                    prepare_u: Optional[bool] = True, prepare_s: Optional[bool] = True) -> dict[tuple[int,int], float]:
        """
            It will calculate all ratios with optimisation for only one case.
            This case only covers `ratio` == 1.0.
            If `ratio` == 1.0 it will skip a further calculations and
             will also add information into `excludes` and `maxes`
            If `excludes` has information it will also not calculate the ratio
             for these rows (u) or column (s) independently
        """
        ratios = {}  # { (ui, si): ratio, ..... }
        dc = DictComparer({})
        for ui, u in enumerate(self.u):
            if ui in excludes.get('u', set()):
                continue
            dc.set_d(self._prepare_update_dict(u) if prepare_u else u)
            dc.ratio_round_precision = self.ratio_round_precision

            for si, s in enumerate(self.s):
                if si in excludes.get('s', set()):
                    continue
                dc_infos = dc.compare([self._prepare_stored_dict(s) if prepare_s else s])
                ratio = dc_infos[0].ratio
                if ratio == 1:
                    self._exclude(ui, si, excludes)
                    # add to result
                    ratios[ui, si] = ratio
                    maxes.append(((ui, si), ratio))
                    break
                ratios[ui, si] = ratio
        return ratios

    def _get_maxed(self, ratios, excludes: dict[str, set[int]]) -> list[tuple[tuple[int, int], float]]:
        """
            Get information of the elements that have the max `ratio`-s.
            It takes into account the `excludes` information but does not modify it.
            Result, can have the ambiguous values, so you should apply _remove_ambiguity() after.
            These 2 method are not combined into one for testing and flexibility purposes.
        """
        result = []
        for (ui, si), r in ratios.items():
            if ui in excludes.get('u', set()) or si in excludes.get('s', set()):
                continue
            if not result:
                result.append(((ui, si), r))
            elif result[0][1] <= r:
                if result[0][1] < r:
                    result.clear()
                result.append(((ui, si), r))
        return result

    def _remove_ambiguity(self, maxes: list[tuple[tuple[int, int], float]]) -> list[tuple[tuple[int, int], float]]:
        res = []
        if maxes:
            cur = maxes.pop(0)
            res.append(cur)
            mlen = len(maxes)
            while maxes and mlen > 0:
                (ui, si), r = maxes[mlen-1]
                if cur[0][0] == ui or cur[0][1] == si:
                    cross = maxes.pop(mlen-1)
                    assert cross[1] == cur[1], f"Warning: ratios [{cross[1]}:{cur[1]}] must be equal"
                mlen -= 1
            res.extend(self._remove_ambiguity(maxes))
        return res

    def _get_matches(self, prepare_u: Optional[bool] = True, prepare_s: Optional[bool] = True) -> list[tuple[tuple[int, int], float]]:
        excludes: dict[str, set[int]] = {}  # {'u': {u_index1, u_index2, ...}, 's': {s_index1, s_index2, ...}}
        maxes: list[tuple[tuple[int, int], float]] = []  # [((ui, si), r), ... ]
        ratios = self._get_ratios(excludes, maxes, prepare_u, prepare_s)
        matches = []
        # if there isn't exist at least one item with `ratio` == 1.0 we need to re-retrieve `maxes`
        if ratios and not maxes:
            maxes = self._get_maxed(ratios, excludes)

        while maxes:
            maxes = self._remove_ambiguity(maxes)
            matches.extend(maxes)
            for (ui, si), r in maxes:
                excludes.setdefault('u', set()).add(ui)
                excludes.setdefault('s', set()).add(si)
            maxes = self._get_maxed(ratios, excludes)
        return matches

    def match(self, prepare_u: bool = True, prepare_s: bool = True) -> dict[str, list[tuple[int, int], float]]:
        """
        0- - ->x axis (si)
         |
         y axis (ui)

        It will compare all of self.u (update/up-to-date data) with self.u (source/stored data).
        Result is dictionary that haves next keys each value is list:
        'u' - to update,
        'i' - to insert/new,
        'd' - `s` contains extra,
        'n' - equal/nothing to update

        Each element of each list has the next signature -  2-tuple (`coordinates`, `ratio`).
        The `coordinates` is also 2-tuple (`u_index`, `s_index`).
        Only 'u' and 'n' are filled by real values of `u_index`, `s_index`.
        The other 'i' and 'd' are the result of emulating each element for uniformity,
         where only either `u_index` or `s_index` has real value.

        Internally, in worse case, it passes through self.u and compares each value of `u` to each value in self.s
         with some optimisation (see ._get_ratios(...) docstring)
        """
        # keys is 'u' - to update, 'i' - to insert/new, 'd' - `s` contains extra, 'n' - equal/nothing to do
        res: dict[str, list] = {k: [] for k in 'uidn'}
        if not (self.s and self.u):
            if self.s:
                res['d'].extend(((None, si), 1.0) for si, _ in enumerate(self.s))
            else:
                res['i'].extend(((ui, None), 1.0) for ui, _ in enumerate(self.u))
            return res

        matches = self._get_matches(prepare_u, prepare_s)
        u_set, s_set = set(), set()
        for (ui, si), r in matches:
            u_set.add(ui)
            s_set.add(si)
            if r == 1:
                res['n'].append(((ui, si), r))
            else:
                res['u'].append(((ui, si), r))

        # if result has no some indexes from self.u therefore this items are new => to insert
        res['i'].extend(((ui, None), 1.0) for ui in set(range(len(self.u))) - u_set)
        # if result has no some indexes from self.s therefore this items are not correlate to u items => to remove
        res['d'].extend(((None, si), 1.0) for si in set(range(len(self.s))) - s_set)

        return res


class DataComparer:
    """
    """

    pk_field_name = 'id'

    # From practice of testing, this range of ratios is sufficient
    # to recognize whether data should be updated or inserted.
    # Remember - this will work not perfectly in the next case:
    #   You had a row that has the 'Django' value and you want to add the row 'Django Framework'.
    #   Comparer can recognize this situation as a desire to modify the value.
    #   As a result, it will have 'Django Framework' instead of 'Django'. On the next run, value will be switched back.
    ratio_range_to_update = (.75, .999999)

    def __init__(self, s: list, u: list, pk_field_name: Optional[str] = None):
        """
            - s is "stored data"
            - u is "data to be updated"
        """
        if not pk_field_name:
            self.pk_field_name = type(self).pk_field_name
        self.s, self.u = s, u

    def _prepare_stored_dict(self, s: dict) -> dict:
        """
        It prepares the s (source/stored data) to data that can be compared with u (update data) and,
        probably, can be used for updating.
        """
        res = {}
        for k, v in s.items():
            if isinstance(v, list):
                # it means (usually) the v value is read_only (reverse side of ForeignKey)
                # need to skip
                pass
            elif isinstance(v, dict):
                # it means the v value is the expanded id for ForeignKey relation
                # we should extract id field from dict
                res[k] = v.get(self.pk_field_name)
            else:
                # regular value
                res[k] = v
        return res

    def _prepare_update_dict(self, u: dict) -> dict:
        """
        It prepares the u (update data) to data that can be compared with s (source/stored data)
        Default implementation just returns a copy of u
        """
        return u.copy()

    def compare(self, prep_s=True, prep_u=True) -> dict[tuple[int, ComparedItemInfoClass], list[ComparedItemInfoClass]]:
        """
        It will compare all of self.u (data to update) with self.u (already stored data).

        If either self.s or self.u is empty then will be returned the empty dictionary.
        Otherwise, it returns the dictionary, where
        key is 2-tuple (index in self.u, best ComparedItemInfoClass for self.s)
        and value is a list of ComparedItemInfoClass for each of self.s

        Internally, it passes through self.u and compares each value of `u` to each value in self.s
        """
        res = {}

        if not self.s:
            return res

        s = [self._prepare_stored_dict(s) if prep_s else s for s in self.s]
        for ui, uitem in enumerate(self.u):
            s_exclude_ids = []
            dc_item = DictComparer(self._prepare_update_dict(uitem) if prep_u else uitem)
            dc_infos = dc_item.compare(s, s_exclude_ids)
            max_ratio_info = functools.reduce(lambda m, n: m if m.ratio >= n.ratio else n, dc_infos)
            if max_ratio_info.ratio == 1:
                s_exclude_ids.append(max_ratio_info.idx)
            res[ui, max_ratio_info] = dc_infos

        return res

    def prepare_to_update(self) -> list[dict]:
        """
            return: tuple Ready to update dictionary and ratios for string values
        """
        if not self.u:
            # nothing to update
            return []

        if not self.s:
            # all of self.u to insert
            return [self._prepare_update_dict(u) for u in self.u]

        res, processed_u = [], []
        comparison_infos = self.compare()
        for (ui, s_best_item_info), s_items_info_list in comparison_infos.items():
            if ui in processed_u:
                # If we are in this place
                # Warning - this looks like bad logic (regarding ratio_range_to_update) or just duplication
                if settings.DEBUG:
                    assert False, "Warning - this looks like bad logic (regarding ratio_range_to_update) or just duplication"
                continue

            # TODO: Think of how to delete
            # ???? if self.u[ui] is None then where to get the ID of row or index in the self.s

            if s_best_item_info.ratio == 1.0:
                # nothing to update
                processed_u.append(ui)
                continue

            u = self._prepare_update_dict(self.u[ui])
            if self.ratio_range_to_update[1] < s_best_item_info.ratio or s_best_item_info.ratio < self.ratio_range_to_update[0]:
                # probably, insert
                uid = self.u[ui].get(self.pk_field_name)
                if uid is not None:
                    # still update
                    u[self.pk_field_name] = uid
            else:
                # update
                sid = self.s[s_best_item_info.idx].get(self.pk_field_name)
                assert sid is not None, "For an update action the ID must be not None"
                u[self.pk_field_name] = sid

            processed_u.append(ui)
            res.append(u)

        return res


class CompleteDataComparer(DataMatcher):

    pk_field_name = DataComparer.pk_field_name

    def _prepare_stored_dict(self, s: dict) -> dict:
        s = DataComparer._prepare_stored_dict(self, s)
        s.pop(self.pk_field_name, None)
        return s

    def _prepare_update_dict(self, u: dict) -> dict:
        u = super()._prepare_update_dict(u)
        u.pop(self.pk_field_name, None)
        return u

    def prepare_to_update(self) -> list[dict]:
        """
            return: tuple Ready to update dictionary and ratios for string values
            !!! Delete is disabled
        """
        res = []
        matches = self.match()

        # insert
        res.extend(self._prepare_update_dict(self.u[ui]) for (ui, _), r in matches.get('i', []))

        # update
        for (ui, si), r in matches.get('u', []):
            u = self._prepare_update_dict(self.u[ui])
            sid = self.s[si].get(self.pk_field_name)
            assert sid is not None, "For an update action the ID must be not None"
            u[self.pk_field_name] = sid
            res.append(u)

        # 'n' and 'd' are ignoring to be compatible with old implementation (DataComparer)
        return res
