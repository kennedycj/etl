import re
import numpy as np
import pandas as pd
from enum import Enum
class Database:

    def __init__(self):
        self.tables = {}
        precision = 1.0

    # Iterate through each MS Excel sheet, formatted as a dict of pandas dataframes to create corresponding Table and
    # Column objects
    def create(self, data : pd.DataFrame):
        for key in data:

            table_name = Table.standardize(key)

            # Store cleaned and original table name in Table
            table = Table(table_name)
            table.alias = key
            columns = []
            column_names = []
            for column in data[key].columns:

                candidate_keys = []

                dtype = data[key].iloc[1:][column].dtypes
                s_column = Column(Column.standardize(data[key].iloc[0][column]))

                if len(data[key][column]) == len(data[key][column].unique()):
                    candidate_keys.append(s_column.name)

                if dtype == 'float64':
                    s_column.data_type = "DOUBLE PRECISION"
                elif dtype == 'int64':
                    s_column.data_type = "INT"
                else:
                    s_column.capacity = data[key].iloc[1:][column].str.len().max()
                    if np.isnan(s_column.capacity):
                        s_column.capacity = 40
                    else:
                        s_column.capacity = int(s_column.capacity)
                    s_column.data_type = " CHAR(" + str(s_column.capacity) + ")"

                table.columns.append(s_column)

                # print(table_name + " has unique keys: " + str(candidate_keys))

            self.tables[table.name] = table

            # print("Table.name {} .alias {} .columns {}".format(table.name, table.alias, table.getColumnNames()))

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
    BOOL = r'^(Yes\d*|No\d*|0|1)$'
    INT = r'^[0-9]+$'
    FLOAT = r'^[0-9]+\.[0-9]+$'
    CHAR = ''

class Column:

    def __init__(self, name):
        self.name = name
        self.alias = ""
        self.Type = Type.CHAR
        self.capacity = 0
        self.key_types = []

    # Eventually, this should be moved into __init__ to couple a Column object with its data type. Then the number of
    # matches can be stored and used programmatically in another piece of code.
    def type(data : pd.Series) -> Type:

        max = 0
        type = Type.CHAR
        for member in Type:

            pattern = re.compile(member.value)

            matches = sum(pattern.match(str(value)) is not None for value in data)
            print("matches for {} = {}".format(member.name, matches))

            if(matches > max):
                max = matches
                type = member

        match_percentage = max / len(data)
        print("match_percentage = {}".format(match_percentage))

        return type

    def standardize(name):
        #Cleanup the column names by replacing spaces and backslash characters with underscores and making all
        #characters lowercase. The regular expression used here should be replaced by a proper parser
        return re.sub(r'[\s+\/-]', '_', str(name).lower())
