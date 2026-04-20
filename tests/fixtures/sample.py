"""Sample Python file for testing extraction."""

import os
from pathlib import Path


class DataProcessor:
    """Processes incoming data records."""

    def __init__(self, config: dict):
        self.config = config
        self._cache = {}

    def process(self, records: list[dict]) -> list[dict]:
        """Process a batch of records."""
        results = []
        for record in records:
            cleaned = self._clean(record)
            validated = self._validate(cleaned)
            if validated:
                results.append(validated)
        return results

    def _clean(self, record: dict) -> dict:
        return {k: v.strip() if isinstance(v, str) else v for k, v in record.items()}

    def _validate(self, record: dict) -> dict | None:
        if "id" not in record:
            return None
        return record


class FileExporter:
    """Exports processed data to files."""

    def __init__(self, output_dir: str):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def export_json(self, data: list[dict], filename: str):
        import json
        path = self.output_dir / filename
        path.write_text(json.dumps(data, indent=2))
        return path

    def export_csv(self, data: list[dict], filename: str):
        if not data:
            return None
        path = self.output_dir / filename
        keys = data[0].keys()
        lines = [",".join(keys)]
        for row in data:
            lines.append(",".join(str(row.get(k, "")) for k in keys))
        path.write_text("\n".join(lines))
        return path


def run_pipeline(config: dict) -> int:
    """Run the full data pipeline."""
    processor = DataProcessor(config)
    records = load_records(config.get("input", "data.json"))
    results = processor.process(records)
    exporter = FileExporter(config.get("output_dir", "output"))
    exporter.export_json(results, "results.json")
    return len(results)


def load_records(path: str) -> list[dict]:
    """Load records from a JSON file."""
    import json
    return json.loads(Path(path).read_text())
