# claude-skills

A Claude Code plugin marketplace for Solace Platform + Feldera (Continuum) work.

| Plugin | Skill | What it does |
|---|---|---|
| `feldera` | `/feldera:audit <repo>` | Audits a Feldera SQL program against Feldera best practices and proves every state finding with the compiler's dataflow graph and the live circuit profile. Also records the compiler facts that are easy to get wrong (what bounds ROW_NUMBER state, what LATENESS does and does not do, how `SELECT *` leaks payloads into window state). |

## Install

```sh
claude plugin marketplace add jessemenning/claude-skills
claude plugin install feldera@jessemenning
```

Then, in a session inside a Feldera demo repo: `/feldera:audit ~/<repo>`.

## Update

```sh
claude plugin marketplace update jessemenning && claude plugin update feldera@jessemenning
```

## Validate before contributing

```sh
claude plugin validate plugins/feldera
```
