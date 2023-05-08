import re
import pandas as pd

from enum import Enum
from psycopg2 import sql

class Database:

    def __init__(self):
        self.tables = {}

    def getNumberOfTables(self) -> int:
        return len(self.tables)

    """Iterate through each MS Excel sheet to create Table and Column objects"""
    def create(self, data):
        for key in data:

            table_name = Table.standardize(key)

            # Store cleaned and original table name in Table
            table = Table(table_name)
            table.alias = key
            for column in data[key].columns:

                candidate_keys = []
                s_column = Column(data[key][column])

                if len(data[key][column]) == len(data[key][column].unique()):
                    candidate_keys.append(s_column.name)

                table.columns.append(s_column)

            self.tables[table.name] = table

    """Generate CREATE TABLE SQL commands"""
    def createTables(self, cur, force : bool) -> int:
        n_tables = 0
        for name, table in self.tables.items():
            columns = []

            for column in table.columns:
                row = []
                row.append(column.name)

                if column.type == Type.CHAR:
                    type = "{} ({})".format(column.type.name, column.capacity)
                else:
                    type = column.type.name

                row.append(type)
                columns.append(row)

            if (force):
                query = sql.SQL("DROP TABLE IF EXISTS {}").format(
                    sql.Identifier(name)
                )
                cur.execute(query)

            column_defs = sql.SQL(', ').join([
                sql.SQL("{} {}").format(
                    sql.Identifier(col_name),
                    sql.SQL(col_type)
                ) for col_name, col_type in columns
            ])

            query = sql.SQL("CREATE TABLE {} ({})").format(
                sql.Identifier(name),
                column_defs
            )

            cur.execute(query)
            n_tables += 1

        return n_tables

    """Insert data into corresponding tables"""
    def insertData(self, cur, data) -> int:
        n_rows = 0
        for key in data:
            table = Table.standardize(key)

            column_names = self.tables[table].getColumnNames()

            for index, row in data[key].iterrows():
                query = sql.SQL("INSERT INTO {} ({}) VALUES ({})").format(
                    sql.Identifier(table),
                    sql.SQL(', ').join(map(sql.Identifier, column_names)),
                    sql.SQL(', ').join(map(sql.Literal, row.tolist()))

                )

                cur.execute(query)
                n_rows += 1

        return n_rows

class Table:

    def __init__(self, name):
        self.name = name
        self.alias = ""
        self.columns = []

    def standardize(name):
        # Remove everything after the first space character
        # Assumes default naming by MS Excel using import from PDF
        standard_name = name.lower().split(" ")[0]
        return standard_name[:5] + "_" + standard_name[5:]

    def getColumnNames(self):
        return [column.name for column in self.columns]

class Type(Enum):
    NULL = r'^\s*$'
    BOOL = r'^(Y(es)?|N(o)?|T(rue)?|F(alse)?)$'
    INT = r'^[0-9]+$'
    FLOAT = r'^[0-9]+\.[0-9]+$'
    CHAR = ''

class Key(Enum):
    ALTERNATE, CANDIDATE, COMPOSITE, FOREIGN, PRIMARY, UNIQUE, SUPER = range(1, 8)
class Column:

    def __init__(self, column : pd.Series):
        # Cleanup the column names
        self.name = re.sub(r'[\s+\/-]', '_', str(column.name).lower())
        self.alias = column.name
        self.capacity = 0
        self.buffer = 10

        max = 0
        self.type = Type.CHAR
        for member in Type:

            pattern = re.compile(member.value)

            matches = sum(pattern.match(str(value)) is not None for value in column)

            if(matches > max):
                max = matches
                self.type = member

        self.precision = max / len(column)

        if self.type == Type.CHAR:
            try:
                # This is a hack around char (x) cast to timestamp by psycopg2
                self.capacity = int(column.str.len().max()) + self.buffer

            except Exception:
                self.capacity = 40


        self.key_types = []