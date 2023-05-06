import re
class Database:

    def __init__(self):
        self.tables = {}

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

class Column:

    def __init__(self, name):
        self.name = name
        self.alias = ""
        self.data_type = ""
        self.capacity = 0
        self.key_types = []

    def standardize(name):
        #Cleanup the column names by replacing spaces and backslash characters with underscores and making all
        #characters lowercase. The regular expression used here should be replaced by a proper parser
        return re.sub(r'[\s+\/-]', '_', str(name).lower())
