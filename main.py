import psycopg2
from psycopg2 import sql
import pandas as pd
import numpy as np
import argparse
import schema

parser = argparse.ArgumentParser()
parser.add_argument('-f', '--filename', type=str, required=True)
parser.add_argument('-p', '--filepath', type=str, required=False)
parser.add_argument('-D', '--dbname', type=str, required=True)
parser.add_argument('-U', '--username', type=str, required=True)
parser.add_argument('-W', '--password', type=str, required=True)
parser.add_argument('-H', '--host', type=str, required=False)
parser.add_argument('-P', '--port', type=str, required=False)
args = parser.parse_args()

raw = pd.read_excel(args.filename, sheet_name=None)

conn = psycopg2.connect(database=args.dbname, user=args.username, password=args.password, host=args.host, port=args.port)

print("Opened database successfully")

# Create tables
cur = conn.cursor()

# Create the database schema
# Iterate through each MS Excel sheet to create corresponding schema.Table and schema.Column objects
database = schema.Database()
for key in raw:

    table_name = schema.Table.standardize(key)

    # Store cleaned and original table name in Table
    table = schema.Table(table_name)
    table.alias = key
    columns = []
    column_names = []
    for column in raw[key].columns:

        candidate_keys = []

        dtype = raw[key].iloc[1:][column].dtypes
        s_column = schema.Column(schema.Column.standardize(raw[key].iloc[0][column]))

        if len(raw[key][column]) == len(raw[key][column].unique()):
            candidate_keys.append(s_column.name)

        if dtype == 'float64':
            s_column.data_type = "DOUBLE PRECISION"
        elif dtype == 'int64':
            s_column.data_type = "INT"
        else:
            s_column.capacity = raw[key].iloc[1:][column].str.len().max()
            if np.isnan(s_column.capacity):
                s_column.capacity = 40
            else:
                s_column.capacity = int(s_column.capacity)
            s_column.data_type = " CHAR(" + str(s_column.capacity) + ")"


        table.columns.append(s_column)

        #print(table_name + " has unique keys: " + str(candidate_keys))

    database.tables[table.name] = table

    # print("Table.name {} .alias {} .columns {}".format(table.name, table.alias, table.getColumnNames()))

# Create the database tables
# Iterate through the schema.Table and schema.Column objects to generate corresponding CREATE TABLE SQL commands
sql_commands = []
for name, table in database.tables.items():
    columns = []

    for column in table.columns:
        row = []
        row.append(column.name)
        dtype = column.data_type
        row.append(dtype)
        columns.append(row)

    inner_rows = [' '.join(row) for row in columns]
    #print("COLUMNS")
    #print(columns)


    sql_commands.append(sql)

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

    print("CREATE TABLE")
    print(query.as_string(conn))

    if name == "table_041":
        cur.execute(query)

# Insert data into tables
# Iterate through each MS Excel sheet (again) to insert data into corresponding tables
for key in raw:
    table = schema.Table.standardize(key)

    column_names = database.tables[table].getColumnNames()

    for index, row in raw[key].iterrows():
        if index == 0:
            continue

        query = psycopg2.sql.SQL("INSERT INTO {} ({}) VALUES ({})").format(
            psycopg2.sql.Identifier(table),
            psycopg2.sql.SQL(', ').join(map(psycopg2.sql.Identifier, column_names)),
            psycopg2.sql.SQL(', ').join(map(psycopg2.sql.Literal, row.tolist()))

        )

        print(query.as_string(conn))

        if table == "table_041":
            cur.execute(query)

conn.commit()
cur.close()
conn.close()
