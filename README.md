# hi-sportdb

Converts the XML records of Dutch sports clubs (`vereniging`) into JSON and
indexes them into Elasticsearch, so they can be searched and browsed through the
Panoptes stack.

## What it does

`index_collections.py` recursively scans an input directory for `.xml` files and:

1. Converts each XML file to JSON, mirroring the input subdirectory structure
   under the output directory.
   - Empty/self-closing elements become `null`.
   - Nested structure is preserved as-is (no flattening of wrapper elements).
   - Repeated sibling tags become a JSON list.
   - A stable `id` (deterministic `uuid5` of the file's relative path) is added
     as the first key.
2. Imports the resulting JSON into an Elasticsearch index named `hi-sportdb`,
   using the field/facet mapping defined in `hi-sportdb-config.toml`
   (via [`procrustus-indexer`](https://pypi.org/project/procrustus-indexer/)).

## Requirements

- Python >= 3.14
- A reachable Elasticsearch instance (see `docker-compose.yml`)

Install dependencies with [uv](https://docs.astral.sh/uv/):

```bash
uv sync
```

## Usage

### Excel workbook export

Convert `Dataset_uit_csv.xlsx` to one JSON file per vereniging and bond:

```bash
uv run python index_collections_xls.py
```

Or supply another workbook and output directory:

```bash
uv run python index_collections_xls.py Dataset_uit_csv.xlsx -o json-workbook-new
```

The output directory must be new or empty, preventing accidental overwrites and
stale organization files from earlier exports. Output layout:

```text
json-workbook/
  organisaties/
    vereniging/1.json
    vereniging/2.json
    ...
    bond/1.json
    bond/2.json
    ...
  conversierapport.json
```

Documents use namespaced IDs (`vereniging:1`, `bond:1`) and the structure described
in [the workbook proposal](docs/dataset-analysis/proposal.md). They include owned
memberships, relationships, citations, source records, and location enrichment.
Bonden without source records are also exported. All original row columns are
preserved in `ruwe_waarden` payloads; Excel dates become ISO date strings.

Unresolved bond references remain unresolved. Historical dates retain their
precision and meaning; invalid dates or conflicts with source date components
retain the original value but have null derived date components. Coordinates
remain unvalidated raw values with `geo: null`. Place notes are attached to the
place using `plaats_id`, not the unrelated generic `object_id`.

`conversierapport.json` contains counts, per-organization quality findings, and
quarantined rows with their sheet, row number, reason, and original values.
Malformed rows without a valid owner are quarantined; duplicate primary keys
stop conversion. Multiple source records are retained, but bond enrichment is
only applied when exactly one source exists, avoiding an arbitrary choice.

This command only generates files. The existing XML import configuration does
not support this schema yet. A future importer should read only `organisaties/`
and use each document's `id` as Elasticsearch `_id`.

Run converter tests with:

```bash
uv run python -m unittest discover -s tests -v
```

### XML conversion and import

```bash
python index_collections.py [input_dir] [-o OUTPUT_DIR] [-k]
```

| Argument            | Description                                     | Default |
| ------------------- | ----------------------------------------------- | ------- |
| `input_dir`         | Directory scanned recursively for `.xml` files. | `data`  |
| `-o, --output-dir`  | Directory to write `.json` files to.            | `out`   |
| `-k, --skip-import` | Convert only; skip the Elasticsearch import.    | `False` |

Elasticsearch connection settings are read from the environment:

| Variable    | Default     |
| ----------- | ----------- |
| `ES_HOST`   | `localhost` |
| `ES_PORT`   | `9200`      |
| `ES_SCHEME` | `http`      |

Example — convert `data/sport/ingforms/data` and index it into a local
Elasticsearch:

```bash
python index_collections.py data/sport/ingforms/data
```

## Docker

The full stack (MongoDB, Elasticsearch, the Panoptes backend, the browser
frontend, and this indexer) is defined in `docker-compose.yml`:

```bash
docker compose up
```

The indexer image is built from `Dockerfile.indexer`.

## Configuration

`hi-sportdb-config.toml` defines the Elasticsearch index name, host, and the
facets exposed for searching (sport type, name, place, province, start/end
dates, etc.). Each facet maps a JMESPath into the source record to an indexed
field.
