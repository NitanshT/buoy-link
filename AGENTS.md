# Repository guidance

- Preserve the read-only nature of diagnostics: do not configure modems, change routes, or modify system settings.
- Do not assume fish or camera interfaces, protocols, or hardware; document decisions when requirements are known.
- Never commit credentials, tokens, private keys, or machine-specific secrets.
- Keep diagnostics usable when optional Linux or Raspberry Pi tools are missing. Avoid shell execution and bound subprocess runtimes.
- Run `python -m pytest` after changes, and add focused tests for parsing and failure cases.
