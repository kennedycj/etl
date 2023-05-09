import pandas as pd
import pytest

import schema

@pytest.fixture()
def setup():
    data = {'table1':
        pd.DataFrame({
            'col1' : ['Yes', 'No', 'No', 'Yes'],
            'col2' : [1, 2, 3, 4],
            'col3' : [0.1, 0.2, 0.3, 0.4],
            'col4' : ['United States', 'France', 'China', 'Mexico']
        }),

        'table2':
            pd.DataFrame({
            'col1' : ['No', 'Yes', 'No', 'Yes'],
            'col2' : [0, 1, 0, 1],
            'col3' : ['2019-01-25', '2020/06/25', '7/16/1984', '11/9/2020'],
            'col4' : ['Apple', 'Orange', 'Cherry', 'Banana']
            })
    }

    yield data

def test_create(setup):
    db = schema.Database(setup)
    db.create()
    assert db.getNumberOfTables() == 2
    assert list(db.tables.keys()) == ['table_1', 'table_2']

    table = db.tables['table_1']
    assert table.name == 'table_1'
    assert table.alias == 'table1'
    assert table.getColumnNames() == ['col1', 'col2', 'col3', 'col4']


def test_column(setup):
    col = schema.Column(setup['table2'].col1)
    assert col.name == 'col1'
    assert col.alias == 'col1'
    assert col.type == schema.Type.BOOL

    col = schema.Column(setup['table1'].col4)
    assert col.name == 'col4'
    assert col.alias == 'col4'
    assert col.type == schema.Type.CHAR
    assert col.capacity == 23
