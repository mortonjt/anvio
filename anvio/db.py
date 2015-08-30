# -*- coding: utf-8
"""
    Low-level db operations.
"""

import os
import sqlite3

import anvio
import anvio.filesnpaths as filesnpaths

from anvio.errors import ConfigError


__author__ = "A. Murat Eren"
__copyright__ = "Copyright 2015, The anvio Project"
__credits__ = []
__license__ = "GPL 3.0"
__version__ = anvio.__version__
__maintainer__ = "A. Murat Eren"
__email__ = "a.murat.eren@gmail.com"
__status__ = "Development"


class DB:
    def __init__(self, db_path, client_version, new_database=False, ignore_version=False):
        self.db_path = db_path
        self.version = None

        if new_database:
            filesnpaths.is_output_file_writable(db_path)
        else:
            filesnpaths.is_file_exists(db_path)

        if new_database and os.path.exists(self.db_path):
            os.remove(self.db_path)

        self.conn = sqlite3.connect(self.db_path)
        self.conn.text_factory = str

        self.cursor = self.conn.cursor()

        if new_database:
            self.create_self()
            self.set_version(client_version)
        else:
            
            self.version = self.get_version()
            if str(self.version) != str(client_version) and not ignore_version:
                raise ConfigError, "It seems the database '%s' was generated when your client was at version %s,\
                                    however, your client now is at version %s. Which means this database file\
                                    cannot be used with this client anymore and needs to be upgraded to the\
                                    version %s :/"\
                                            % (self.db_path, self.version, client_version, client_version)


    def get_version(self):
        try:
            return self.get_meta_value('version')
        except:
            raise ConfigError, "%s does not seem to be a database generated by anvio :/" % self.db_path


    def create_self(self):
        self._exec('''CREATE TABLE self (key text, value text)''')


    def create_table(self, table_name, fields, types):
        if len(fields) != len(types):
            raise ConfigError, "create_table: The number of fields and types has to match."

        db_fields = ', '.join(['%s %s' % (t[0], t[1]) for t in zip(fields, types)])
        self._exec('''CREATE TABLE %s (%s)''' % (table_name, db_fields))
        self.commit()


    def set_version(self, version):
        self.set_meta_value('version', version)
        self.commit()


    def set_meta_value(self, key, value):
        self._exec('''INSERT INTO self VALUES(?,?)''', (key, value,))
        self.commit()


    def remove_meta_key_value_pair(self, key):
        self._exec('''DELETE FROM self WHERE key="%s"''' % key)
        self.commit()


    def get_meta_value(self, key):
        response = self._exec("""SELECT value FROM self WHERE key='%s'""" % key)
        rows =  response.fetchall()

        if not rows:
            raise ConfigError, "A value for '%s' does not seem to be set in table 'self'." % key

        val = rows[0][0]

        if type(val) == type(None):
            return None

        try:
            val = int(val)
        except ValueError:
            pass

        return val


    def commit(self):
        self.conn.commit()


    def disconnect(self):
        self.conn.commit()
        self.conn.close()


    def _exec(self, sql_query, value=None):
        if value:
            ret_val = self.cursor.execute(sql_query, value)
        else:
            ret_val = self.cursor.execute(sql_query)

        self.commit()
        return ret_val


    def _exec_many(self, sql_query, values):
        return self.cursor.executemany(sql_query, values)


    def get_all_rows_from_table(self, table):
        response = self._exec('''SELECT * FROM %s''' % table)
        return response.fetchall()


    def get_single_column_from_table(self, table, column):
        response = self._exec('''SELECT %s FROM %s''' % (column, table))
        return [t[0] for t in response.fetchall()]


    def get_table_column_types(self, table):
        response = self._exec('PRAGMA TABLE_INFO(%s)' % table)
        return [t[2] for t in response.fetchall()]


    def get_table_structure(self, table):
        response = self._exec('''SELECT * FROM %s''' % table)
        return [t[0] for t in response.description]


    def get_table_as_list_of_tuples(self, table, table_structure = None):
        return self.get_all_rows_from_table(table)


    def get_table_as_dict(self, table, table_structure = None, string_the_key = False, columns_of_interest = None, keys_of_interest = None, omit_parent_column = False, error_if_no_data = True):
        if not table_structure:
            table_structure = self.get_table_structure(table)

        columns_to_return = range(0, len(table_structure))

        if omit_parent_column:
            if '__parent__' in table_structure:
                columns_to_return.remove(table_structure.index('__parent__'))
                table_structure.remove('__parent__')

        if columns_of_interest:
            for col in table_structure[1:]:
                if col not in columns_of_interest:
                    columns_to_return.remove(table_structure.index(col))

        if len(columns_to_return) == 1:
            if error_if_no_data:
                raise ConfigError, "get_table_as_dict :: after removing an column that was not mentioned in the columns\
                                    of interest by the client, nothing was left to return..."
            else:
                return {}

        if keys_of_interest:
            keys_of_interest = set(keys_of_interest)

        results_dict = {}

        rows = self.get_all_rows_from_table(table)

        for row in rows:
            entry = {}

            if keys_of_interest:
                if row[0] in keys_of_interest:
                    # so we are interested in keeping this, reduce the size of the
                    # hash size to improve the next inquiry, and keep going.
                    keys_of_interest.remove(row[0])
                else:
                    # we are not intersted in this one, continue:
                    continue

            for i in columns_to_return[1:]:
                entry[table_structure[i]] = row[i]

            if string_the_key:
                results_dict[str(row[0])] = entry
            else:
                results_dict[row[0]] = entry

        return results_dict


    def get_table_names(self):
        response = self._exec("""select name from sqlite_master where type='table'""")
        return [r[0] for r in response.fetchall()]
