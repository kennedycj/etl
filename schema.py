import re
import pandas as pd

from enum import Enum
from psycopg2 import sql

class Database:

    def __init__(self, data):
        self.tables = {}
        self.data = data

    def getNumberOfTables(self) -> int:
        return len(self.tables)

    """Iterate through each MS Excel sheet to create Table and Column objects"""
    def create(self):
        for key in self.data:

            table_name = Table.standardize(key)

            # Store cleaned and original table name in Table
            table = Table(table_name)
            table.alias = key
            for col in self.data[key].columns:

                df = self.data[key]
                new_column = Column(df[col])

                # Check if column is a candidate key (has unique values)
                if len(df[col].unique()) == len(df[col]):
                    table.keys[Key.CANDIDATE].append(col)
                # Check if column is a unique key
                elif df[col].is_unique:
                    table.keys[Key.UNIQUE].append(col)
                # Check if column is part of an alternate key
                elif any(df.groupby(col).size() > 1):
                    table.keys[Key.ALTERNATE].append(col)
                # Check if column is part of a composite key
                elif len(df.columns) > 1 and len(df.groupby(list(df.columns)).size()) == len(df):
                    table.keys[Key.COMPOSITE].append(col)
                # Check if column is part of the primary key
                elif col in df.index.names:
                    table.keys[Key.PRIMARY].append(col)

                table.columns.append(new_column)

            print("{}".format(table.keys))

            self.tables[table.name] = table

        self.findKeys()

        # find FOREIGN KEYS from key_types
    def findKeys(self):
        data_frames = self.data
        # Find the PRIMARY KEY for each table
        primary_keys = {}
        for table_name, df in data_frames.items():
            # Check for a single-column PRIMARY KEY
            for column in df.columns:
                if df[column].is_unique:
                    primary_keys[table_name] = column
                    break
            # Check for a multi-column PRIMARY KEY
            if table_name not in primary_keys:
                for i, row in df.iterrows():
                    if df.duplicated(subset=row.index.tolist()).any():
                        primary_keys[table_name] = row.index.tolist()
                        break

        # Find the FOREIGN KEYS that reference each PRIMARY KEY
        # along with their REFERENCE table
        foreign_keys = {}
        for primary_key_table, primary_key_column in primary_keys.items():
            for foreign_key_table, df in data_frames.items():
                if foreign_key_table == primary_key_table:
                    continue
                for column in df.columns:
                    if set(df[column]).issubset(set(data_frames[primary_key_table][primary_key_column])):
                        if foreign_key_table not in foreign_keys:
                            foreign_keys[foreign_key_table] = []
                        foreign_keys[foreign_key_table].append((primary_key_table, primary_key_column))

        # Print the results
        print('PRIMARY KEYS:')
        print(primary_keys)
        print('FOREIGN KEYS:')
        print(foreign_keys)

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
        self.keys = {
            Key.ALTERNATE : [],
            Key.CANDIDATE : [],
            Key.COMPOSITE : [],
            Key.FOREIGN : [],
            Key.PRIMARY : [],
            Key.UNIQUE : [],
            Key.SUPER : []
        }

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