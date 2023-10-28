# IDE: PyCharm
# Project: cv
# Path: apps/cv
# File: db_patch.py
# Contact: Semyon Mamonov <semyon.mamonov@gmail.com>
# Created by ox23 at 2023-05-11 (y-m-d) 5:55 AM
import uuid
from functools import cached_property
from typing import Optional, Union, Type, Callable

from django.db.backends.base.base import BaseDatabaseWrapper
from django.db.backends.signals import connection_created


BACKEND_VENDOR_POSTGRESQL = 'postgresql'
BACKEND_VENDOR_MARIADB = 'mariadb'
BACKEND_VENDOR_MYSQL = 'mysql'
BACKEND_VENDOR_ORACLE = 'oracle'
BACKEND_VENDOR_SQLITE = 'sqlite'

BACKEND_VENDORS: set = {
    BACKEND_VENDOR_POSTGRESQL, BACKEND_VENDOR_MARIADB, BACKEND_VENDOR_MYSQL,
    BACKEND_VENDOR_ORACLE, BACKEND_VENDOR_SQLITE
}


class BasePatch:

    databases_require_patch_on_each_connection = (BACKEND_VENDOR_SQLITE,)

    def __init__(self, db_wrapper: BaseDatabaseWrapper = None):
        self._validated = []  # [connection.alias, .... ]
        self.db_wrapper: BaseDatabaseWrapper = db_wrapper

    @property
    def db_wrapper(self) -> BaseDatabaseWrapper:
        if self._db_wrapper is None:
            raise ValueError('`db_wrapper` still is None')
        return self._db_wrapper

    @db_wrapper.setter
    def db_wrapper(self, value: BaseDatabaseWrapper):
        if value is not None and not isinstance(value, BaseDatabaseWrapper):
            raise ValueError('`db_wrapper` must be instance of BaseDatabaseWrapper')

        self._db_wrapper = value

    def validate(self):
        """
        Default logic is:
            If the alias hasn't been processed yet, then it will check for availability in the database.
            Otherwise, if the check returned False, the database will be patched.
            In both cases
                self._validated[self.db_wrapper.alias] = id(self.connection)

        !!! We have implemented a different behaviour for the SQLite user-defined function.
        Every time the connection has changed, we must recreate (declare) the user-defined function.
        """
        # Why is it implemented this way?
        #
        # The next (old) logic
        #    if self.db_wrapper.alias not in self._validated:  # alias doesn't exist -> do check
        # can work for all databases, the one exception is SQLite when Django is started twice.
        # Thus, two groups of code will use same namespace.
        #
        # For example, It happens when you run a HTTP server that shares global variables with other code
        # that will be executed. A particular case, you run manage.py runserver
        # (or through an instance of LiveServerThread ) and right after that you run manage.py some_command
        # which the HTTP server uses.
        #
        # The old logic won't work for SQLite because SQLite requires
        # a user-defined function to be created (declared) every time a connection changes.

        a = self.db_wrapper.alias
        if a not in self._validated or self.db_wrapper.vendor in self.databases_require_patch_on_each_connection:
            # need full process
            if not self.check():  # database can satisfy already, for example - user-defined function in MySQL
                self.patch()
            self._validated.append(a)

    def _get_handler(self, type_handler) -> Callable[[BaseDatabaseWrapper, object], Optional[bool]]:
        hname = '_'.join((type_handler, self.db_wrapper.vendor))
        h = getattr(self, hname, None)
        if h is None:
            raise AttributeError('Handler `%s` does not exists' % hname)
        if not callable(h):
            raise ValueError('Handler `%s` is not callable' % hname)
        return h

    def get_check_handler(self) -> Callable[[], bool]:
        return self._get_handler('check')

    def get_patch_handler(self) -> Callable[[], None]:
        return self._get_handler('patch')

    def check(self) -> bool:
        """
            Check an availability of the necessary capabilities in the database
        """
        return self.get_check_handler()()

    def patch(self) -> None:
        """
            Patch a necessary capabilities in the database
        """
        self.get_patch_handler()()

    # Check stubs
    def check_sqlite(self):
        raise NotImplementedError

    def check_postgresql(self):
        raise NotImplementedError

    def check_mariadb(self):
        raise NotImplementedError

    def check_mysql(self):
        raise NotImplementedError

    def check_oracle(self):
        raise NotImplementedError

    # Patch stubs
    def patch_sqlite(self):
        raise NotImplementedError

    def patch_postgresql(self):
        raise NotImplementedError

    def patch_mariadb(self):
        raise NotImplementedError

    def patch_mysql(self):
        raise NotImplementedError

    def patch_oracle(self):
        raise NotImplementedError


class Patcher:

    patches: list[Union[BasePatch, Type[BasePatch]]] = []

    def __init__(self) -> None:
        self.patches: list[BasePatch] = self._instantiate_patches()

    def _instantiate_patches(self):
        """
            Create local copy (copy of instance) of BasePatcher.patches
            BasePatcher.patches contains Classes then it will instantiate their
        """
        result = []
        for p in self.patches:
            if type(p) is type:
                p = p()
            result.append(p)
        return result

    def get_patches(self) -> list[BasePatch]:
        return self.patches

    @cached_property
    def dispatch_uid(self):
        return '-'.join((type(self).__name__.lower(), str(uuid.uuid4())))

    def connection_created_handler(self, **kwargs):
        # # sender is <class 'django.db.backends.sqlite3.base.DatabaseWrapper'>
        # sender: Type[BaseDatabaseWrapper] = kwargs['sender']
        # # signal is <django.dispatch.dispatcher.Signal object>
        # signal:  = kwargs['signal']

        # connection is object <DatabaseWrapper vendor='sqlite' alias='default'>
        connection = kwargs['connection']
        for p in self.get_patches():
            p.db_wrapper = connection
            p.validate()

    def connect(self):
        connection_created.connect(self.connection_created_handler, dispatch_uid=self.dispatch_uid)
