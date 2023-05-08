import re
import pandas as pd
from enum import Enum

import psycopg2

class Database:

    def __init__(self):
        self.tables = {}

    def getNumberOfTables(self) -> int:
        return len(self.tables)

    # Iterate through each MS Excel sheet, formatted as a dict of pandas dataframes to create corresponding Table and
    # Column objects
    def create(self, data):
        for key in data:

            table_name = Table.standardize(key)

            # Store cleaned and original table name in Table
            table = Table(table_name)
            table.alias = key
            columns = []
            column_names = []
            for column in data[key].columns:

                candidate_keys = []

                #type = data[key].iloc[0:][column].dtypes
                # print("Column(data[{}].iloc[1:][{}] = {}".format(key, column, data[key].iloc[0:][column]))
                s_column = Column(data[key][column])

                #print("s_column.name = ".format(s_column.name))

                if len(data[key][column]) == len(data[key][column].unique()):
                    candidate_keys.append(s_column.name)

                #type = Column.type(data[key].iloc[1:][column])
                #print("type = ".format(type))




                table.columns.append(s_column)

                # print(table_name + " has unique keys: " + str(candidate_keys))

            self.tables[table.name] = table

            #print("Table.name {} .alias {} .columns {}".format(table.name, table.alias, table.getColumnNames()))

    # Iterate through the schema.Table and schema.Column objects to generate corresponding CREATE TABLE SQL commands
    def createTables(self, cur, force : bool) -> None:
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

            inner_rows = [' '.join(row) for row in columns]

            if (force):
                query = psycopg2.sql.SQL("DROP TABLE IF EXISTS {}").format(psycopg2.sql.Identifier(name))
                cur.execute(query)

            column_defs = psycopg2.sql.SQL(', ').join([
                psycopg2.sql.SQL("{} {}").format(
                    psycopg2.sql.Identifier(col_name),
                    psycopg2.sql.SQL(col_type)
                ) for col_name, col_type in columns
            ])

            query = psycopg2.sql.SQL("CREATE TABLE {} ({})").format(
                psycopg2.sql.Identifier(name),
                column_defs
            )

            cur.execute(query)

    # Iterate through each MS Excel sheet (again) to insert data into corresponding tables
    def insertData(self, cur, data):

        for key in data:
            table = Table.standardize(key)

            column_names = self.tables[table].getColumnNames()

            for index, row in data[key].iterrows():
                query = psycopg2.sql.SQL("INSERT INTO {} ({}) VALUES ({})").format(
                    psycopg2.sql.Identifier(table),
                    psycopg2.sql.SQL(', ').join(map(psycopg2.sql.Identifier, column_names)),
                    psycopg2.sql.SQL(', ').join(map(psycopg2.sql.Literal, row.tolist()))

                )

                cur.execute(query)

class Table:

    def __init__(self, name):
        self.name = name
        self.alias = ""
        self.columns = []

    def standardize(name):
        # Remove everything after the first space character and insert an underscore between the table label and its number.
        # This assumes default naming by MS Excel using import from PDF
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
        # Cleanup the column names by replacing spaces and backslash characters with underscores and making all
        # characters lowercase. The regular expression used here should be replaced by a proper parser
        self.name = re.sub(r'[\s+\/-]', '_', str(column.name).lower())
        self.alias = column.name
        self.capacity = 0

        #type = column.dtypes
        #self.type = Column.type(column)

        max = 0
        self.type = Type.CHAR
        for member in Type:

            pattern = re.compile(member.value)

            matches = sum(pattern.match(str(value)) is not None for value in column)
            print("matches for {} = {}".format(member.name, matches))

            if(matches > max):
                max = matches
                self.type = member

        self.precision = max / len(column)
        #print("match_percentage = {}".format(self.precision))

        if self.type == Type.CHAR:
            try:
                self.capacity = int(column.str.len().max()) + 10 # this is a hack around char (x) cast to timestamp by psycopg2

            except:
                self.capacity = 40


        self.key_types = []