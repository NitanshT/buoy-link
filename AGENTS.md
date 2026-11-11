# Repository guidance

- Keep the standard diagnostics read-only. The separately invoked cellular probe may create only its narrowly scoped, temporary test rule and route, with cleanup and verification.
- Do not configure modems, APNs, default routes, or persistent network settings.
- Do not assume fish or camera interfaces, protocols, or hardware; document decisions when requirements are known.
- Never commit credentials, tokens, private keys, or machine-specific secrets. Do not log modem or SIM identifiers.
- Keep diagnostics usable when optional Linux or Raspberry Pi tools are missing. Avoid shell execution and bound subprocess runtimes.
- Run `python -m pytest` after changes, and add focused tests for parsing and failure cases.
