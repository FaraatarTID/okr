# Markdown Documentation HQ Template

Use this pattern at the top of new markdown files so the Documentation HQ check passes:

```
Documentation HQ: [README](../README.md)
```

Examples:
- From repository root: `Documentation HQ: [README](README.md)`
- From `.github/` directory: `Documentation HQ: [README](../README.md)` or `Documentation HQ: [README](../../README.md)` for nested folders
- From `src/docs/` folder: `Documentation HQ: [README](../../README.md)`

Keep that exact format (including `Documentation HQ: [README](...)`) and set the link to this repo's root `README.md`.
