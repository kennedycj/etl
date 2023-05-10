import re
import pandas as pd

from enum import Enum
from psycopg2 import sql

class Database:

    def __init__(self, data):
        self.tables = {}
        self.data = data
        self.primary_keys = {}
        self.foreign_keys = {}
    def getNumberOfTables(self) -> int:
        return len(self.tables)

    """Iterate through each MS Excel sheet to create Table and Column objects"""
    def create(self) -> None:
        for table_name in self.data:
            # Store cleaned and original table name in Table
            table = Table(table_name)
            for col in self.data[table_name].columns:
                df = self.data[table_name]
                new_column = Column(df[col])
                table.columns.append(new_column)

            self.tables[table.name] = table

    """Find PRIMARY and FOREIGN keys"""
    def findKeys(self) -> int:
        data_frames = self.data
        # Find the PRIMARY KEY for each table
        for table_name, df in data_frames.items():
            # Check for a single-column PRIMARY KEY
            for column in df.columns:
                if df[column].is_unique:
                    self.primary_keys[table_name] = column
                    break
            # Check for a multi-column PRIMARY KEY
            if table_name not in self.primary_keys:
                for i, row in df.iterrows():
                    if df.duplicated(subset=row.index.tolist()).any():
                        self.primary_keys[table_name] = row.index.tolist()
                        break

        # Find the FOREIGN KEYS that reference each PRIMARY KEY along with their REFERENCE table
        for primary_key_table, primary_key_column in self.primary_keys.items():
            for foreign_key_table, df in data_frames.items():
                if foreign_key_table == primary_key_table:
                    continue
                for column in df.columns:
                    if set(df[column]).issubset(set(data_frames[primary_key_table][primary_key_column])):
                        if foreign_key_table not in self.foreign_keys:
                            self.foreign_keys[foreign_key_table] = []
                        self.foreign_keys[foreign_key_table].append((column, primary_key_table, primary_key_column))

        print("PRIMARY KEYS")
        print(self.primary_keys)

        print("FOREIGN KEYS")
        print(self.foreign_keys)

        return len(self.primary_keys)

    """Generate CREATE TABLE SQL commands"""
    def createTables(self, cur, conn, force : bool) -> int:
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

            if name in self.primary_keys:
                (table_name, column_name), *rest = self.primary_keys.items()
                column_defs = sql.SQL(', ').join([
                    column_defs,
                    sql.SQL("PRIMARY KEY({})").format(
                        sql.Identifier(column_name)
                    )
                ])

            if name in self.foreign_keys:

                foreign_key_defs = sql.SQL(', ').join([
                    sql.SQL('FOREIGN KEY ({}) REFERENCES {}({})').format(
                        sql.Identifier(tup[0]),
                        sql.Identifier(tup[1]),
                        sql.Identifier(tup[2])
                    ) for tup in self.foreign_keys[name]
                ])

                column_defs = sql.SQL(', ').join([
                    column_defs,
                    foreign_key_defs
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
        for table in data:
            column_names = self.tables[table].getColumnNames()

            for index, row in data[table].iterrows():
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

    def getColumnNames(self):
        return [column.name for column in self.columns]

class Type(Enum):
    NULL = r'^\s*$'
    BOOL = r'^(Y(es)?|N(o)?|T(rue)?|F(alse)?)$'
    INT = r'^[0-9]+$'
    FLOAT = r'^[0-9]+\.[0-9]+$'
    CHAR = ''

class Key(Enum):
    ALTERNATE = "ALTERNATE"
    CANDIDATE = "CANDIDATE"
    COMPOSITE = "COMPOSITE"
    FOREIGN = "FOREIGN"
    PRIMARY = "PRIMARY"
    UNIQUE = "UNIQUE"
    SUPER = "SUPER"
class Column:

    def __init__(self, column : pd.Series):
        # Cleanup the column names
        self.name = column.name
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