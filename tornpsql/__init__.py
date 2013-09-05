#!/usr/bin/env python

"""A lightweight wrapper around PostgreSQL.
Ported from http://github.com/bdarnell/torndb
"""

import itertools
import logging
import psycopg2
import re

version = "0.0.2"
version_info = (0, 0, 2)


class Connection(object):
    def __init__(self, host_or_url, database=None, user=None, password=None, port=5432):
        self.logging = False
        if host_or_url.startswith('postgres://'):
            args = re.search('postgres://(?P<user>[\w\-]+):(?P<password>[\w\-]*)@(?P<host>.*):(?P<port>\d+)/(?P<database>[\w\-]+)', host_or_url).groupdict()
            self.host = args.get('host')
            self.database = args.get('database')
        else:
            self.host = host_or_url
            self.database = database
            args = dict(host=host_or_url, database=database, port=port, 
                        user=user, password=password)

        self._db = None
        self._db_args = args
        try:
            self.reconnect()
        except Exception:
            logging.error("Cannot connect to PostgreSQL on postgresql://%s:<password>@%s/%s", 
                args['user'], self.host, self.database, exc_info=True)

    def __del__(self):
        self.close()

    def close(self):
        """Closes this database connection."""
        if getattr(self, "_db", None) is not None:
            self._db.close()
            self._db = None

    def reconnect(self):
        """Closes the existing database connection and re-opens it."""
        self.close()
        self._db = psycopg2.connect(**self._db_args)
        self._db.autocommit = True

    def mogrify(self, query, *parameters):
        """From http://initd.org/psycopg/docs/cursor.html?highlight=mogrify#cursor.mogrify
        Return a query string after arguments binding.
        The string returned is exactly the one that would be sent to the database running 
        the execute() method or similar.
        """
        cursor = self._cursor()
        try:
            return cursor.mogrify(query, parameters)
        except:
            cursor.close()
            raise

    def query(self, query, *parameters):
        """Returns a row list for the given query and parameters."""
        cursor = self._cursor()
        try:
            self._execute(cursor, query, parameters)    
            if cursor.description:
                column_names = [column.name for column in cursor.description]
                return [Row(itertools.izip(column_names, row)) for row in cursor.fetchall()]
        except:
            cursor.close()
            raise

    def execute(self, query, *parameters):
        """Alias for query"""
        return self.query(query, *parameters)

    def get(self, query, *parameters):
        """Returns the first row returned for the given query."""
        rows = self.query(query, *parameters)
        if not rows:
            return None
        elif len(rows) > 1:
            raise Exception("Multiple rows returned for Database.get() query")
        else:
            return rows[0]

    def executemany(self, query, *parameters):
        """Executes the given query against all the given param sequences.
        """
        cursor = self._cursor()
        try:
            self._executemany(cursor, query, parameters)
            return True
        except Exception:
            cursor.close()
            raise

    def execute_rowcount(self, query, *parameters):
        """Executes the given query, returning the rowcount from the query."""
        cursor = self._cursor()
        try:
            self._execute(cursor, query, parameters)
            return cursor.rowcount
        finally:
            cursor.close()

    def _ensure_connected(self):
        if self._db is None:
            self.reconnect()

    def _cursor(self):
        self._ensure_connected()
        return self._db.cursor()

    def _execute(self, cursor, query, parameters):
        try:
            if self.logging:
                logging.info(cursor.mogrify(query, parameters))
            cursor.execute(query, parameters)
        except psycopg2.OperationalError as e:
            logging.error("Error connecting to PostgreSQL on %s, %s", self.host, e)
            self.close()
            raise

    def _executemany(self, cursor, query, parameters):
        """The function is mostly useful for commands that update the database: any result set returned by the query is discarded."""
        try:
            if self.logging:
                logging.info(cursor.mogrify(query, parameters))
            cursor.executemany(query, parameters)
        except psycopg2.OperationalError as e:
            logging.error("Error connecting to PostgreSQL on %s, e", self.host, e)
            self.close()
            raise 


class Row(dict):
    """A dict that allows for object-like property access syntax."""
    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError:
            raise AttributeError(name)