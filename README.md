# Dataset Collection

Stage 1 collects raw UK megalith-related heritage datasets without changing their contents. It validates a single source manifest, downloads enabled non-manual sources, stores each raw response locally, and writes basic download metadata next to each file.

Stage 2 normalises supported raw files into a single internal record schema. It reads the same manifest, discovers the latest successful raw file per source under `data/raw/`, parses supported source formats, and writes one JSON Lines output file per source under `data/normalized/`.

## `sources.json`

`config/sources.json` is a JSON list of source objects. Each source defines:

- `id`
- `name`
- `type`
- `format`
- `url`
- `enabled`

Optional fields:

- `method`
- `headers`
- `params`
- `filename`
- `timeout`
- `notes`

Enabled non-manual sources must have a non-empty URL. Manual sources may leave `url` empty.

## Validate the manifest

```bash
python -m dataset_collection.cli validate-manifest --sources config/sources.json
```

## Run collection

```bash
python -m dataset_collection.cli collect --sources config/sources.json
python -m dataset_collection.cli collect --sources config/sources.json --force
```

By default, the collector skips a source if its output file already exists under the current date directory. Use `--force` to re-download it.

## Output layout

Downloads are written unchanged under:

```text
data/raw/{source_id}/{YYYY-MM-DD}/
```

Each successful or failed download writes a metadata file next to the target file:

```text
data/raw/{source_id}/{YYYY-MM-DD}/{filename}
data/raw/{source_id}/{YYYY-MM-DD}/{filename stem}.metadata.json
```

## Metadata fields

Each metadata JSON file contains:

- `source_id`
- `source_name`
- `url`
- `request_method`
- `fetched_at`
- `http_status`
- `content_type`
- `output_file`
- `file_size`
- `sha256`
- `success`
- `error_message`

## Run normalization

```bash
python -m dataset_collection.cli normalise --sources config/sources.json
python -m dataset_collection.cli normalise --sources config/sources.json --source historic_england
```

By default, normalization processes enabled non-manual sources. It skips manual sources, sources with no raw file, and unsupported sources cleanly.

## Raw file discovery

For each source, the normalizer looks under:

```text
data/raw/{source_id}/{YYYY-MM-DD}/
```

It selects the most recent dated directory that contains a successful raw file. If a matching metadata file exists and reports `success: false`, that file is ignored and the search continues to older dated directories.

## Normalized output

Each processed source writes a separate JSON Lines file:

```text
data/normalized/{source_id}.jsonl
```

Each line is one canonical record. There is no combined all-sources file at this stage.

## Canonical schema

Each normalized record contains:

- source identifiers: `source_id`, `source_name`, `source_record_id`, `source_dataset`, `source_url`
- raw lineage: `raw_file_path`, `raw_record_index`
- naming and location: `canonical_name`, `alternate_names`, `nation`, `county_or_region`
- geometry: `latitude`, `longitude`, `geometry_type`, `geometry_wkt`
- site description: `site_types`, `primary_type`, `period`, `designation_status`, `grid_reference`, `description`, `tags`
- source-specific carry-through: `raw_name`, `raw_type`, `raw_subtype`, `raw_description`
- provenance: `fetched_at`, `source_metadata_file`, `parser_name`, `parser_version`, `normalization_timestamp`, `raw_source_fields`

`raw_source_fields` preserves the original parsed source values used to build each normalized record.

## Supported sources

Stage 2 currently includes working parsers for:

- `historic_england`
- `cadw`
- `nismr`
- `ni_scheduled`

`hes_scheduled` has parser support prepared, but the current manifest still marks it as a manual source so the CLI skips it by default.

## Provenance

Every normalized record preserves provenance back to its source record, including:

- the source id and source name
- the source record id when present
- the raw file path
- the raw record index inside the parsed file
- the metadata file path when present
- the original parsed source fields used during normalization

## Not included yet

This pipeline still intentionally does not include:

- deduplication or record merging
- megalith-specific classification beyond what a source already states
- centroid generation for polygon-only sources
- database storage
- combined reporting beyond per-source logs and summary counts
