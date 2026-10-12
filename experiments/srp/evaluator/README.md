# Frozen independent evaluator

This evaluator runs outside the agent's workspace and imports the selected backend through BENCHMARK_SUBJECT. It reuses the pinned subject's Jest/ts-jest dependencies and a real PostgreSQL database with upstream migrations. No new application dependencies are introduced.

`RG` contains 13 immutable database/authorization/event regression scenarios. `T01`–`T05` contain task acceptance scenarios. Grade one task with `--testNamePattern '^(RG|T01) '` (substitute its ID), the unchanged 761 backend unit tests, and the backend build. Apply the manifest's external grading timeout. Protected-file/dependency hashes are checked separately by the preparation verifier; agent-authored test changes do not replace this oracle.

The full combined suite is only for preparation. Expected failures on both starting variants show unmet task requirements. They are not agent failures or benchmark results. Use JSON reports to compare exact passing/failing case identities and normalized regression observations. All source-specific upstream tests remain unchanged; the separately broken upstream e2e scaffold is disclosed in amendment 001.

The runtime.env values are public disposable test values; run these services only on an isolated local network. Never point the evaluator at a production database: it resets fixture teams/users and temporarily adds a test constraint. Its database is dedicated to this benchmark.
