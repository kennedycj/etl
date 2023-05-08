import psycopg2
from psycopg2 import sql
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

# Create the database schema
database = schema.Database()
database.create(data)

# Create the database tables
database.createTables(cur, args.force)

# Insert data into tables
database.insertData(cur, data)

conn.commit()
cur.close()
conn.close()
