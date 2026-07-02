"""Convert the XML files in data/ to JSON in out and index the collections in Elasticsearch.

- Empty/self-closing elements become null.
- Nested structure is preserved as-is (no flattening of wrapper elements).
- Repeated sibling tags become a JSON list.
"""

import argparse
import json
import os
import uuid
import xml.etree.ElementTree as Et
from pathlib import Path
from elasticsearch import Elasticsearch
from procrustus_indexer import build_indexer

DATA_DIR = Path(__file__).parent / "data"
OUT_DIR = Path(__file__).parent / "json-data"
INDEX_NAME = "hi-sportdb"
CONFIG = "hi-sportdb-config.toml"

# Fixed namespace so the same file always yields the same id (uuid5 is deterministic).
ID_NAMESPACE = uuid.uuid5(uuid.NAMESPACE_URL, "hi-sportdb")

_es_host = os.environ.get("ES_HOST", "localhost")
_es_port = os.environ.get("ES_PORT", "9200")
_es_scheme = os.environ.get("ES_SCHEME", "http")
es = Elasticsearch(hosts=[f"{_es_scheme}://{_es_host}:{_es_port}"])

def element_to_obj(element: Et.Element):
    """Recursively convert an XML element to a JSON-compatible value."""
    children = list(element)
    if not children:
        text = (element.text or "").strip()
        return text if text else None

    obj: dict = {}
    for child in children:
        value = element_to_obj(child)
        if child.tag in obj:
            # Repeated tag -> collect into a list.
            existing = obj[child.tag]
            if isinstance(existing, list):
                existing.append(value)
            else:
                obj[child.tag] = [existing, value]
        else:
            obj[child.tag] = value
    return obj


def convert_file(xml_path: Path, out_path: Path, id_key: str) -> None:
    root = Et.parse(xml_path).getroot()
    obj = element_to_obj(root)

    # Stable id derived from the file's relative path; prepend so it is the first key.
    file_id = str(uuid.uuid5(ID_NAMESPACE, id_key))
    if isinstance(obj, dict):
        obj = {"id": file_id, **obj}
    else:
        obj = {"id": file_id, "value": obj}

    data = {root.tag: obj}

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def import_into_es(
    index_name: str, cfg: str, es_client: Elasticsearch, input_dir: Path
) -> None:
    inputs = [str(p) for p in sorted(input_dir.rglob("*.json"))]
    if not inputs:
        print(f"Skipping ES import: no input files found under {input_dir}")
        return

    if not Path(cfg).exists():
        print(f"Skipping ES import: config not found: {cfg}")
        return

    indexer = build_indexer(cfg, index_name, es_client)
    indexer.create_mapping(overwrite=True)
    indexer.import_files(inputs)
    print(f"Imported {len(inputs)} files into Elasticsearch index '{index_name}'")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "input_dir",
        nargs="?",
        type=Path,
        default=DATA_DIR,
        help=f"Directory to scan recursively for files to be indexed (default: {DATA_DIR}).",
    )
    parser.add_argument(
        "-o",
        "--output-dir",
        type=Path,
        default=OUT_DIR,
        help=f"Directory to write .json files to (default: {OUT_DIR}).",
    )
    parser.add_argument(
        "-k",
        "--skip-import",
        type=bool,
        default=False,
        help=f"Skip importing XML files into ElasticSearch (default: {False}).",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    input_dir: Path = args.input_dir
    output_dir: Path = args.output_dir
    skip_import: bool = args.skip_import

    if not input_dir.is_dir():
        raise SystemExit(f"Input directory not found: {input_dir}")

    xml_files = sorted(input_dir.rglob("*.xml"))
    if not xml_files:
        print(f"No XML files found in {input_dir}")
        return

    current_dir: Path | None = None
    for xml_path in xml_files:
        # Mirror the input subdirectory structure under the output dir.
        relative = xml_path.relative_to(input_dir).with_suffix(".json")
        out_path = output_dir / relative
        convert_file(xml_path, out_path, relative.as_posix())
        if relative.parent != current_dir:
            current_dir = relative.parent
            print(f"Converting {current_dir}")

    if not skip_import:
        import_into_es(INDEX_NAME, CONFIG, es, output_dir)

    print(f"Done.")

if __name__ == "__main__":
    main()
