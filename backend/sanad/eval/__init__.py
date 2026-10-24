"""The evaluation harness (SYSTEM_DESIGN §11): `python -m sanad.eval --set test|dev`.

It asks every question of a running stack over HTTP, exactly as a user would, and scores the
answers against eval/questions.yaml (the 15 headline questions) or eval/dev_questions.yaml
(the 30 tuning questions). It needs PyYAML, so it runs in the backend-dev image.

- `questions` loads and checks an eval set.
- `scoring` is pure: fact matching, citation matching and the failure category of each item.
- `client` talks to the API (login, health, documents, ask).
- `report` aggregates runs and writes the JSON and Markdown reports.
- `cli` wires them together.
"""
