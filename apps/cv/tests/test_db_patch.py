# IDE: PyCharm
# Project: cv
# Path: ${DIR_PATH}
# File: ${FILE_NAME}
# Contact: Semyon Mamonov <semyon.mamonov@gmail.com>
# Created by ox23 at 2023-05-11 (y-m-d) 4:08 PM
from django.db.backends.base.base import BaseDatabaseWrapper
from django.test import TestCase
from django.db import connections, DEFAULT_DB_ALIAS

from ..db_patch import Patcher, BasePatch
from ..patches import CountRangeIntersectionPatch
from ..sql import range_intersection_sql


class MockPatch(BasePatch):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.log = []
        self.check_retval = True

    def check_sqlite(self):
        self.log.append('check')
        return self.check_retval

    def patch_sqlite(self):
        self.log.append('patch')
        pass


class TestPatcher(TestCase):

    def setUp(self) -> None:
        self.db_wrapper = connections['default']

    def test_0__instantiate_patches(self):
        res = Patcher._instantiate_patches(
            type('DummyPatcher', (object,), {'patches': [MockPatch, MockPatch()]})()
        )
        for i, o in enumerate(res):
            with self.subTest(instance_i=i):
                self.assertIsInstance(o, MockPatch)

    def test_1_get_patches(self):
        patcher = type('DummyPatcher', (Patcher,), {'patches': [MockPatch, MockPatch()]})()

        patches = patcher.get_patches()
        self.assertEqual(2, len(patches))
        self.assertIsInstance(patches, list)

        for i, o in enumerate(patches):
            with self.subTest(instance_i=i):
                self.assertIsInstance(o, MockPatch)

    def test_2_dispatch_uid(self):
        tname = 'DummyPatcher'
        tpatcher = type(tname, (Patcher,), {'patches': [MockPatch, MockPatch()]})
        patcher1 = tpatcher()
        patcher2 = tpatcher()

        uid1 = patcher1.dispatch_uid
        self.assertTrue(uid1.startswith(tname.lower()+'-'))
        uid1_ = patcher1.dispatch_uid
        self.assertEqual(uid1, uid1_)

        uid2 = patcher2.dispatch_uid
        self.assertTrue(uid2.startswith(tname.lower()+'-'))
        self.assertNotEqual(uid1, uid2)

    def test_3_connection_created_handler(self):
        patcher = type('DummyPatcher', (Patcher,), {'patches': [MockPatch, MockPatch()]})()
        patcher.connection_created_handler(sender=type(self.db_wrapper), connection=self.db_wrapper)

        for i, o in enumerate(patcher.get_patches()):
            with self.subTest(all_patches_instantiated=i):
                self.assertIsInstance(o, MockPatch)

        for i, o in enumerate(patcher.get_patches()):
            with self.subTest(instance_has_db_wrapper=i):
                self.assertIs(o.db_wrapper, self.db_wrapper)

        for i, o in enumerate(patcher.get_patches()):
            with self.subTest(all_instances_validated=i):
                self.assertListEqual(o.log, ['check'])
                self.assertListEqual(o._validated, [self.db_wrapper.alias])

    def test_999_connect(self):
        patcher = type('DummyPatcher', (Patcher,), {'patches': [MockPatch, MockPatch()]})()
        patcher.connect()

        # simulate new connection to trigger 'connection_created' signal
        db_wrapper = connections.create_connection(DEFAULT_DB_ALIAS)
        db_wrapper.connect()

        for i, o in enumerate(patcher.get_patches()):
            with self.subTest(all_patches_instantiated=i):
                self.assertIsInstance(o, MockPatch)

        for i, o in enumerate(patcher.get_patches()):
            with self.subTest(instance_has_db_wrapper=i):
                self.assertIs(o.db_wrapper, db_wrapper)

        for i, o in enumerate(patcher.get_patches()):
            with self.subTest(all_instances_validated=i):
                self.assertListEqual(o.log, ['check'])
                self.assertListEqual(o._validated, [db_wrapper.alias])


class TestBasePatch(TestCase):

    def setUp(self) -> None:
        self.db_wrapper: BaseDatabaseWrapper = connections['default']
        self.patch = BasePatch(self.db_wrapper)

    def test_0_db_wrapper(self):
        patch = BasePatch()
        with self.assertRaises(ValueError):
            # value error -> still is None
            patch.db_wrapper

        with self.assertRaises(ValueError):
            # value error -> inappropriate value
            patch.db_wrapper = 'fgdfg'

        patch.db_wrapper = self.db_wrapper
        self.assertIs(self.db_wrapper, patch.db_wrapper)

    def test_1__get_handler(self):
        # self.patch.check_sqlite or self.patch.check_oracle .... depends from self.db_wrapper.vendor
        self.assertEqual(self.patch.check_sqlite, self.patch._get_handler('check'))
        self.assertEqual(self.patch.patch_sqlite, self.patch._get_handler('patch'))
        with self.assertRaises(AttributeError):
            self.patch._get_handler('gggg')

        patch = BasePatch()
        patch.test_sqlite = 'dummy val'
        with self.assertRaises(ValueError):
            patch._get_handler('test')

    def test_2_get_check_patch_handler(self):
        self.assertEqual(self.patch.check_sqlite, self.patch.get_check_handler())
        self.assertEqual(self.patch.patch_sqlite, self.patch.get_patch_handler())

    def test_3_check_all_not_implemented_handlers(self):
        hs = [
            self.patch.check_sqlite,
            self.patch.check_postgresql,
            self.patch.check_mariadb,
            self.patch.check_mysql,
            self.patch.check_oracle,
            self.patch.patch_sqlite,
            self.patch.patch_postgresql,
            self.patch.patch_mariadb,
            self.patch.patch_mysql,
            self.patch.patch_oracle,
        ]
        for i, h in enumerate(hs):
            kw = {h.__name__: i}
            with self.subTest(**kw):
                with self.assertRaises(NotImplementedError):
                    h()

    def test_4_check_patch(self):
        with self.assertRaises(NotImplementedError):
            self.patch.check()
        with self.assertRaises(NotImplementedError):
            self.patch.patch()

    def test_9999_validate(self):
        patch = MockPatch(self.db_wrapper)
        patch.validate()
        self.assertListEqual([patch.db_wrapper.alias], patch._validated)
        self.assertListEqual(patch.log, ['check'])

        patch.log.clear()
        patch.validate()
        self.assertListEqual(
            patch.log, ['check'] if patch.db_wrapper.vendor in patch.databases_require_patch_on_each_connection else []
        )

        patch.log.clear()
        patch._validated.clear()
        patch.check_retval = False
        patch.validate()
        self.assertListEqual([patch.db_wrapper.alias], patch._validated)
        self.assertListEqual(patch.log, ['check', 'patch'])

        patch.log.clear()
        patch.validate()
        self.assertListEqual(
            patch.log,
            ['check', 'patch'] if patch.db_wrapper.vendor in patch.databases_require_patch_on_each_connection else []
        )


class TestCountRangeIntersectionPatch(TestCase):

    def setUp(self) -> None:
        db_wrapper = connections['default']
        self.patch = CountRangeIntersectionPatch(db_wrapper)

    def test_0_check_sqlite(self):
        self.assertFalse(self.patch.check_sqlite())

    def _real_check_in_db_sqlite(self):
        # User-defined functions immediately when they were created can be viewed through
        # 'SELECT * FROM pragma_function_list WHERE name="md5"' ("md5" for example),
        # however, when function was deleted in the current session using con.create_function("md5", 1, None)
        # it still remains in 'pragma_function_list', but in the case of its call,
        # it will generated error 'sqlite3.OperationalError: user-defined function raised exception'.
        # !!! Also, this exception appears if the user-defined function, really, has problem.
        # But, the function was never created will raise the error 'sqlite3.OperationalError: no such function: md5'
        # Thus, the not worse way to test for existence is to catch sqlite3.OperationalError

        sql = 'SELECT * FROM pragma_function_list WHERE name=?'
        cursor = self.patch.db_wrapper.create_cursor()
        try:
            cursor.execute(sql, [self.patch.name])
            r = cursor.fetchone()
        finally:
            cursor.close()

        return r

    def _create_fixtures(self):
        # CREATE TABLE test (
        # "begin" INTEGER DEFAULT null,
        # "end" INTEGER DEFAULT null,
        # "start" INTEGER DEFAULT null,
        # "finish" INTEGER DEFAULT null
        # );
        #
        # INSERT INTO test ("begin", "end", "start", "finish") VALUES (1, 7, 4, 10);
        # INSERT INTO test ("begin", "end", "start", "finish") VALUES (7, null, 11, null);
        #
        sqls = ('CREATE TABLE test ("id" integer not null primary key autoincrement,'
                ' "begin" INTEGER DEFAULT null, "end" INTEGER DEFAULT null,'
                ' "start" INTEGER DEFAULT null, "finish" INTEGER DEFAULT null)',
                'INSERT INTO test ("begin", "end", "start", "finish") VALUES (1, 7, 4, 10)',
                'INSERT INTO test ("begin", "end", "start", "finish") VALUES (7, null, 11, null)'
                )

        cursor = self.patch.db_wrapper.create_cursor()
        try:
            for i, sql in enumerate(sqls):
                cursor.execute(sql)
                tres = 1
                if i == 0:
                    tres = -1
                with self.subTest(create_step=i):
                    self.assertEqual(tres, cursor.rowcount)
        finally:
            cursor.close()

    def test_1_patch_sqlite(self):
        # If Patcher already connected to connection_created then function is exist already.
        # For example, used in AppConfig.ready.
        # Thus, we need to work out this case for further testing purposes

        # main test
        res = self._real_check_in_db_sqlite()
        if res is None:
            self.patch.patch_sqlite()

        # function created successfully
        res = self._real_check_in_db_sqlite()
        self.assertIsNotNone(res)

        # TEST OF RIGHT LOGIC
        self._create_fixtures()

        cursor = self.patch.db_wrapper.create_cursor()
        # -- partial intersection with null
        # SELECT * FROM test WHERE 8 < ifnull("end", max(8,15)+1) and 15 > ifnull("begin", min(8,15)-1); -- 1
        # -- 7,,11,
        cursor.execute('SELECT %s(null, 8, 15, "test")' % self.patch.name)
        r = cursor.fetchone()
        self.assertIsNotNone(r)
        self.assertEqual(1, r[0])

        # -- partial intersection and with null too
        # SELECT * FROM test WHERE 5 < ifnull("end", max(5,15)+1) and 15 > ifnull("begin", min(5,15)-1); -- 2
        # -- 1,7,4,10
        # -- 7,,11,
        cursor.execute('SELECT %s(null, 5, 15, "test")' % self.patch.name)
        r = cursor.fetchone()
        self.assertIsNotNone(r)
        self.assertEqual(2, r[0])

        # -- no intersection exclude nulled row
        # SELECT * FROM test WHERE 7 < ifnull("end", max(7,9)+1) and 9 > ifnull("begin", min(7,9)-1); -- 1
        # -- 7,,11,
        cursor.execute('SELECT %s(null, 7, 9, "test")' % self.patch.name)
        r = cursor.fetchone()
        self.assertIsNotNone(r)
        self.assertEqual(1, r[0])

        # -- surrounded intersection (with field that no standard name)
        # SELECT * FROM test WHERE 3 < ifnull("finish", max(3,15)+1) and 15 > ifnull("start", min(3,15)-1); -- 2
        # -- 1,7,4,10
        # -- 7,,11,
        cursor.execute('SELECT %s(null, 3, 15, "test", "start", "finish")' % self.patch.name)
        r = cursor.fetchone()
        self.assertIsNotNone(r)
        self.assertEqual(2, r[0])

        # -- Not intersected (with field that no standard name)
        # SELECT * FROM test WHERE 1 < ifnull("finish", max(1,4)+1) and 4 > ifnull("start", min(1,4)-1); -- 0
        cursor.execute('SELECT %s(null, 1, 4, "test", "start", "finish")' % self.patch.name)
        r = cursor.fetchone()
        self.assertIsNotNone(r)
        self.assertEqual(0, r[0])

    def _create_date_fixtures(self, data: list[dict]):
        csql = 'CREATE TABLE test ("id" integer not null primary key autoincrement, "begin" date, "end" date)'
        isql = 'INSERT INTO test ("begin", "end") VALUES (:begin, :end)'

        cursor = self.patch.db_wrapper.create_cursor()
        try:
            with self.subTest(create_test_table=''):
                cursor.execute(csql)
                self.assertEqual(-1, cursor.rowcount)
            for i, item in enumerate(data):
                with self.subTest(insert_test_data=i):
                    cursor.execute(isql, item)
                    self.assertEqual(1, cursor.rowcount)
        finally:
            cursor.close()

    def test_2_patch_sqlite(self):
        # If Patcher already connected to connection_created then function is exist already.
        # For example, used in AppConfig.ready.
        # Thus, we need to work out this case for further testing purposes

        # main test
        res = self._real_check_in_db_sqlite()
        if res is None:
            self.patch.patch_sqlite()

        # function created successfully
        res = self._real_check_in_db_sqlite()
        self.assertIsNotNone(res)

        # TEST LOGIC
        # like test_1_patch_sqlite but more full and with dates

        # Source data
        data = [
            {'begin': '2023-05-05', 'end': '2023-05-10'},
            {'begin': '2023-05-15', 'end': None},
        ]

        # Test cases
        tcases = [
            {'bv': '2023-05-01', 'ev': '2023-05-05', 'result': []},
            {'bv': '2023-05-10', 'ev': '2023-05-13', 'result': []},
            {'bv': '2023-05-10', 'ev': '2023-05-15', 'result': []},
            {'bv': '2023-05-03', 'ev': '2023-05-07', 'result': [['2023-05-05', '2023-05-10']]},
            {'bv': '2023-05-05', 'ev': '2023-05-10', 'result': [['2023-05-05', '2023-05-10']]},
            {'bv': '2023-05-03', 'ev': '2023-05-11', 'result': [['2023-05-05', '2023-05-10']]},
            {'bv': '2023-05-07', 'ev': '2023-05-11', 'result': [['2023-05-05', '2023-05-10']]},
            {'bv': '2023-05-13', 'ev': '2023-05-16', 'result': [['2023-05-15', None]]},
            {'bv': '2023-05-16', 'ev': '2023-05-20', 'result': [['2023-05-15', None]]},
            {'bv': '2023-05-03', 'ev': None, 'result': [['2023-05-05', '2023-05-10'], ['2023-05-15', None]]},
            {'bv': '2023-05-09', 'ev': None, 'result': [['2023-05-05', '2023-05-10'], ['2023-05-15', None]]},
            {'bv': '2023-05-10', 'ev': None, 'result': [['2023-05-15', None]]},
            {'bv': '2023-05-13', 'ev': None, 'result': [['2023-05-15', None]]},
            {'bv': '2023-05-15', 'ev': None, 'result': [['2023-05-15', None]]},
            {'bv': '2023-05-17', 'ev': None, 'result': [['2023-05-15', None]]},
        ]

        self._create_date_fixtures(data)
        ri_sql, ri_sql_prms = range_intersection_sql('test')
        cursor = self.patch.db_wrapper.create_cursor()
        try:
            for case in tcases:
                bv, ev, result = case['bv'], case['ev'], case['result']
                caption = str(bv)+'...'+str(ev)
                with self.subTest(test_sql=caption):
                    cursor.execute(ri_sql, ri_sql_prms | {'bv': bv, 'ev': ev})
                    for i, r in enumerate(cursor):
                        self.assertEqual([str(f) for f in result[i]], [str(f) for f in r][1:])

                with self.subTest(test_sql_function=caption):
                    cursor.execute('SELECT %s(null, :bv, :ev, "test")' % self.patch.name, case)
                    self.assertEqual(len(result), cursor.fetchone()[0])
        finally:
            cursor.close()
