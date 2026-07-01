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
