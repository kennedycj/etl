import psycopg2
import pandas as pd
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
parser.add_argument('-F', '--force', action='store_true')
args = parser.parse_args()

data = pd.read_excel(args.filename, sheet_name=None)


conn = psycopg2.connect(database=args.dbname,
                        user=args.username,
                        password=args.password,
                        host=args.host,
                        port=args.port)

cur = conn.cursor()
print("Opened database {}".format(args.dbname))

# Create the database schema
database = schema.Database(data)
database.create()
print("Created schema")

# Create the database tables
n_tables = database.createTables(cur, args.force)
print("Created {} tables".format(n_tables))

# Insert data into tables
n_rows = database.insertData(cur, data)
print("Inserted {} rows".format(n_rows))

conn.commit()
cur.close()
conn.close()