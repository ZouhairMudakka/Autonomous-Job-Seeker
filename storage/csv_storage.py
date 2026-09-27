"""
CSV Storage Module (MVP, Sync)

This module handles CSV file operations using pandas, focusing on:
- Append-only writing of new rows
- Basic data loading
- Optional data validation (skipping invalid rows, logging them separately)
- Synchronous approach (safe with pandas)
- Timestamp-based naming if desired
- Learning pipeline data storage and retrieval

Commented out backup/export logic for future use.
"""

import pandas as pd
from pathlib import Path
from datetime import datetime
from typing import Optional, Union, List, Dict
from storage.file_utils import atomic_text_writer, file_lock, safe_child

class CSVStorage:
    def __init__(self, settings):
        """
        Args:
            settings (dict): Must include 'data_dir' for CSV storage location.
        """
        self.data_dir = Path(settings.get('data_dir', settings.get('system', {}).get('data_dir', './data')))
        self.data_dir.mkdir(parents=True, exist_ok=True)

    def _path(self, base_filename, file_id=None, use_timestamp=False):
        safe_child(self.data_dir, base_filename)
        parts = [base_filename]
        if file_id is not None:
            safe_child(self.data_dir, file_id)
            parts.append(file_id)
        if use_timestamp:
            parts.append(datetime.now().strftime('%Y%m%d_%H%M'))
        return safe_child(self.data_dir, '_'.join(parts) + '.csv')

    def save_data(
        self,
        data: Union[pd.DataFrame, List[dict]],
        base_filename: str,
        append: bool = True,
        use_timestamp: bool = False,
        file_id: Optional[str] = None
    ) -> None:
        """
        Save data to a CSV file in append-only mode by default.

        Args:
            data: A pandas DataFrame or a list of dictionaries (rows).
            base_filename (str): The base name for the CSV file (e.g. "jobs", "tracker").
            append (bool): If True, we append rows. Otherwise overwrite the file.
            use_timestamp (bool): If True, we add a date/time suffix to the filename.
            file_id (str): If provided, appended to filename to differentiate runs (like "001").

        Resulting filename pattern:
            <base_filename>_[file_id]_YYYYMMDD_HHMM.csv   (if use_timestamp=True)
            <base_filename>_[file_id].csv                (otherwise)
            <base_filename>.csv                          (if no file_id, no timestamp)
        """
        if isinstance(data, list):
            # Convert list of dicts to DataFrame
            df = pd.DataFrame(data)
        else:
            df = data  # we assume it's already a DataFrame

        file_path = self._path(base_filename, file_id, use_timestamp)
        if df.empty:
            return
        if df.columns.has_duplicates:
            raise ValueError('CSV column names must be unique')
        with file_lock(file_path):
            has_data = file_path.exists() and file_path.stat().st_size > 0
            if append and has_data:
                columns = list(pd.read_csv(file_path, nrows=0).columns)
                if set(columns) != set(df.columns):
                    raise ValueError('Appended CSV data must match the existing columns')
                # Incoming dictionaries need not have the same insertion order.
                df = df.loc[:, columns]
                df.to_csv(file_path, mode='a', header=False, index=False, encoding='utf-8')
            else:
                with atomic_text_writer(file_path, newline='') as stream:
                    df.to_csv(stream, index=False)

    def load_data(
        self,
        base_filename: str,
        use_timestamp: bool = False,
        file_id: Optional[str] = None
    ) -> pd.DataFrame:
        """
        Load data from a CSV file. If using timestamp or file_id, we replicate the naming logic.
        If the file doesn't exist, returns an empty DataFrame.
        """
        # Rebuild filename just like in save_data (except no explicit timestamp param to load the "latest"?)
        # For MVP, assume we want the exact same naming scheme or we skip timestamp logic if not sure.
        filename_parts = [base_filename]
        if file_id:
            filename_parts.append(file_id)
        # For loading, let's skip searching for the "latest" timestamp and just load a direct name.
        # If needed, you can add logic to find the newest file in the directory.
        if use_timestamp:
            # This is tricky—do we load a specific timestamp or the newest?
            # MVP: skip this advanced logic, or raise NotImplementedError
            raise NotImplementedError("Loading timestamped files not implemented in MVP")

        file_path = self._path(base_filename, file_id)

        with file_lock(file_path):
            if not file_path.exists() or file_path.stat().st_size == 0:
                return pd.DataFrame()
            return pd.read_csv(file_path)

    def validate_data(
        self,
        data: Union[pd.DataFrame, List[dict]],
        schema=None,
        error_filename: str = "invalid_rows"
    ):
        """
        Validate data rows using an optional pydantic schema.
        - Skips invalid rows
        - Logs them to a separate CSV (error_filename.csv)

        Returns a list of validated objects (or dicts).
        """
        # Convert to list of dicts for easier iteration
        if isinstance(data, pd.DataFrame):
            records = data.to_dict("records")
        else:
            records = data

        if not schema:
            # If no schema provided, do no validation
            return records

        valid_rows = []
        invalid_rows = []
        for row in records:
            try:
                # parse with pydantic
                schema_obj = schema(**row)
                valid_rows.append(schema_obj.model_dump())
            except Exception as e:
                invalid_rows.append({**row, "_validation_error": str(e)})

        # If we have invalid rows, log them to a separate CSV for reference
        if invalid_rows:
            self.save_data(
                data=invalid_rows,
                base_filename=error_filename,
                append=True,
                use_timestamp=False
            )

        return valid_rows

    def is_file_exists(
        self,
        base_filename: str,
        file_id: Optional[str] = None,
        use_timestamp: bool = False
    ) -> bool:
        """
        Check if a file exists given the naming scheme in save_data/load_data.
        For MVP, if use_timestamp is True, we either skip or raise an error
        since we might not know which timestamp to check.
        """
        if use_timestamp:
            # Not fully implemented
            raise NotImplementedError("Checking timestamped file existence not in MVP.")

        filename_parts = [base_filename]
        if file_id:
            filename_parts.append(file_id)

        return self._path(base_filename, file_id).exists()

    # Commenting out backup/export for MVP unless you want them active
    """
    def backup_data(self, base_filename: str):
        # Create a backup of the CSV file with a timestamp
        source_path = self.data_dir / f"{base_filename}.csv"
        if not source_path.exists():
            return False
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = self.data_dir / f"{base_filename}_backup_{timestamp}.csv"
        backup_path.write_bytes(source_path.read_bytes())
        return True

    def export_data(self, base_filename: str, format='csv'):
        # Export data to a specified format (csv/json/excel)
        df = self.load_data(base_filename)
        export_path = self.data_dir / 'exports'
        export_path.mkdir(exist_ok=True)
        if format == 'csv':
            df.to_csv(export_path / f"{base_filename}_export.csv", index=False)
        elif format == 'json':
            df.to_json(export_path / f"{base_filename}_export.json")
        elif format == 'excel':
            df.to_excel(export_path / f"{base_filename}_export.xlsx", index=False)
        else:
            raise ValueError(f"Unsupported export format: {format}")
    """

