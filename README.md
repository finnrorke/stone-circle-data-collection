# Dataset Collection

Stage 1 collects raw UK megalith-related heritage datasets without changing their contents. It validates a single source manifest, downloads enabled non-manual sources, stores each raw response locally, and writes basic download metadata next to each file.

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

## Not included yet

This stage intentionally does not include parsing, normalization, filtering, deduplication, merging, or reporting beyond basic download metadata.
