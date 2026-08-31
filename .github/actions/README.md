# GitHub Action: Setup Python dependencies

Documentation HQ: [README](../../README.md)

> For new markdown files, copy the required backlink from:
> `.github/documentation-hq-template.md`

Reusable local composite action that installs Python dependencies from a requirements file.

## Location

- `.github/actions/setup-python-dependencies/action.yml`

## Inputs

- `requirements-path` (optional)
  - Default: `backend_app/requirements.txt`
  - Description: Path to the requirements file to install.

- `pip-command` (optional)
  - Default: `python -m pip`
  - Description: Command used to invoke pip (for example `python -m pip` or `pip`).

## Usage

### Default usage

```yaml
- name: Install Python dependencies
  uses: ./.github/actions/setup-python-dependencies
```

### Custom requirements path

```yaml
- name: Install Python dependencies
  uses: ./.github/actions/setup-python-dependencies
  with:
    requirements-path: backend_app/requirements.txt
```

### Override pip command

```yaml
- name: Install Python dependencies
  uses: ./.github/actions/setup-python-dependencies
  with:
    requirements-path: backend_app/requirements.txt
    pip-command: pip
```
