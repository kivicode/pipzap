# Documentation

## Prerequisites

Make sure to install the `dev` dependencies to build the docs:

```bash
poetry install --with dev
```

## Building the docs

> Note: the following commands should be run from this folder (`docs/`)

```bash
make html
```

```bash
make serve
```

### Update
> Only needed when the module structure is changed

```bash
make update-modules
```
