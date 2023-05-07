import pandas as pd
import pytest

import schema
def test_type():
    df = pd.DataFrame({
        'col1': ['Yes', 'No', 'Yes', 'Yes1'],
        'col2': [0, 1, 1, 0],
        'col3': ['Yes', 'No', 'Maybe', 'Yes'],
    })

    assert schema.Column.type(df['col1']) == schema.Type.BOOL
    assert schema.Column.type(df['col2']) == schema.Type.BOOL
    assert schema.Column.type(df['col3']) == schema.Type.CHAR
