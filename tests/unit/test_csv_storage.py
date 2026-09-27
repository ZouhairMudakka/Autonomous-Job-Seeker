"""Tests of the actual CSVStorage interface (no browser required)."""

import pandas as pd
from pydantic import BaseModel, Field
import pytest

from storage.csv_storage import CSVStorage


@pytest.fixture
def storage(tmp_path):
    return CSVStorage({'system': {'data_dir': str(tmp_path / 'nested' / 'data')}})


def test_missing_csv_and_empty_input(storage):
    assert storage.load_data('missing').empty
    assert not storage.is_file_exists('missing')
    storage.save_data([], 'empty')
    assert not storage.is_file_exists('empty')


def test_save_load_overwrite_and_file_id(storage):
    storage.save_data([{'job': 'Engineer', 'score': 0.5}], 'jobs', file_id='run1')
    storage.save_data(pd.DataFrame([{'job': 'Analyst', 'score': 0.9}]), 'jobs', file_id='run1')
    assert storage.is_file_exists('jobs', file_id='run1')
    assert len(storage.load_data('jobs', file_id='run1')) == 2
    storage.save_data([{'job': 'Manager', 'score': 1.0}], 'jobs', append=False, file_id='run1')
    assert storage.load_data('jobs', file_id='run1').to_dict('records') == [{'job': 'Manager', 'score': 1.0}]


def test_validation_separates_invalid_rows_without_mutating_input(storage):
    class Row(BaseModel):
        count: int = Field(ge=0)

    rows = [{'count': 2}, {'count': -1}]
    assert storage.validate_data(rows, schema=Row) == [{'count': 2}]
    assert rows == [{'count': 2}, {'count': -1}]
    invalid = storage.load_data('invalid_rows')
    assert invalid.iloc[0]['count'] == -1
    assert '_validation_error' in invalid


def test_timestamped_loading_is_explicitly_unsupported(storage):
    storage.save_data([{'job': 'Engineer'}], 'jobs', use_timestamp=True)
    assert len(list(storage.data_dir.glob('jobs_*.csv'))) == 1
    with pytest.raises(NotImplementedError):
        storage.load_data('jobs', use_timestamp=True)
