# Project selection and verified evidence

Source/configuration review performed on **2026-10-12** using public GitHub repository metadata, commit-pinned trees, and file contents. Counts below describe repository files, not passing tests or measured coverage. No project was installed or executed during that foundation review. Subsequent local setup/build/test evidence is recorded separately in the [preparation report](../experiments/srp/preparation/README.md).

## Candidate comparison

| Candidate | Inspected commit | Verified characteristics | Selection judgment |
| --- | --- | --- | --- |
| [Hoppscotch](https://github.com/hoppscotch/hoppscotch) | `63273f8e599e73f0fb38c0739314e8d46b6bc83d` | API development application; TypeScript/NestJS backend, Prisma/PostgreSQL, Jest, self-host configuration, root MIT declaration. | Selected: a bounded backend and concrete responsibility groups provide a manageable first experimental surface. |
| [Docmost](https://github.com/docmost/docmost) | `c1305f002e47ece4d40f0aebba75d8d0f762d8ea` | Collaborative wiki; TypeScript/NestJS server with Jest, PostgreSQL and Redis configuration; AGPL core and separately licensed enterprise directories. | Viable; collaboration infrastructure and mixed licensing boundaries add preparation complexity. |
| [Vendure](https://github.com/vendurehq/vendure) | `5234fbf598d1e89a049abb781bc6f7fc45d944b9` | TypeScript/NestJS commerce platform; Vitest unit and end-to-end configuration; GPLv3 default with commercial alternative. | Viable, especially for later studies; broader commerce domain and monorepo increase initial preparation complexity. |

These judgments concern suitability for this study, not overall project quality. Copyleft licenses are not inherently incompatible with research; choosing Hoppscotch reduces the initial study's distribution and setup complexity. The selection does not infer SRP violations from line count alone.

Candidate evidence:

- Docmost: [pinned README, including license exclusions](https://github.com/docmost/docmost/blob/c1305f002e47ece4d40f0aebba75d8d0f762d8ea/README.md), [server manifest](https://github.com/docmost/docmost/blob/c1305f002e47ece4d40f0aebba75d8d0f762d8ea/apps/server/package.json), [Compose configuration](https://github.com/docmost/docmost/blob/c1305f002e47ece4d40f0aebba75d8d0f762d8ea/docker-compose.yml), and [root license](https://github.com/docmost/docmost/blob/c1305f002e47ece4d40f0aebba75d8d0f762d8ea/LICENSE). Its README excludes `apps/server/src/ee`, `apps/client/src/ee`, and `packages/ee` from the core license.
- Vendure: [license](https://github.com/vendurehq/vendure/blob/5234fbf598d1e89a049abb781bc6f7fc45d944b9/LICENSE.md), [core manifest](https://github.com/vendurehq/vendure/blob/5234fbf598d1e89a049abb781bc6f7fc45d944b9/packages/core/package.json), and [Vitest configuration](https://github.com/vendurehq/vendure/blob/5234fbf598d1e89a049abb781bc6f7fc45d944b9/packages/core/vitest.config.mts). The core manifest specifies `GPL-3.0-or-later`; the root license describes the commercial alternative and plugin exception.

## Selected subject and architecture

Repository: https://github.com/hoppscotch/hoppscotch

Pinned upstream SHA: `63273f8e599e73f0fb38c0739314e8d46b6bc83d`.

The selected tree is a real API development ecosystem, not a tutorial. The full monorepo has 2,495 tracked file entries; the `packages/hoppscotch-backend/` boundary has 250. The backend tree contains 19 `.spec.ts` files and a separate application end-to-end scaffold. These are file counts, not numbers of test cases.

The [backend manifest](https://github.com/hoppscotch/hoppscotch/blob/63273f8e599e73f0fb38c0739314e8d46b6bc83d/packages/hoppscotch-backend/package.json) identifies NestJS, TypeScript, Prisma, GraphQL/Apollo, Express, Jest, and Supertest dependencies. The [application module](https://github.com/hoppscotch/hoppscotch/blob/63273f8e599e73f0fb38c0739314e8d46b6bc83d/packages/hoppscotch-backend/src/app.module.ts) wires authentication, users, teams, collections, requests, configuration, mail, and other application capabilities.

Relevant components are:

- Team collections: the service, GraphQL resolver, REST search controller, models, module, and guards.
- Team requests and team membership: collaborating domain services and authorization boundaries.
- Prisma: database access, transaction coordination, and collection locking.
- PubSub: subscription notifications. The inspected implementation initializes a local in-process PubSub, despite a comment mentioning Redis for production; do not infer a Redis runtime requirement from the comment or dependency list.
- Shared collection folder and sort types: interchange shape and sorting contract.

The [team-collection service](https://github.com/hoppscotch/hoppscotch/blob/63273f8e599e73f0fb38c0739314e8d46b6bc83d/packages/hoppscotch-backend/src/team-collection/team-collection.service.ts) has 1,576 lines and implements recursive import/export, CRUD, moves, deletion/reordering with transaction retries, SQL-based search/ancestry, CLI retrieval, duplication, and sorting. These distinct behavior groups motivate the proposed decomposition; the size is supporting context rather than proof of an SRP violation.

## Existing tests and setup evidence

The [collection tests](https://github.com/hoppscotch/hoppscotch/blob/63273f8e599e73f0fb38c0739314e8d46b6bc83d/packages/hoppscotch-backend/src/team-collection/team-collection.service.spec.ts) instantiate the service directly with mocked Prisma, PubSub, and TeamService. They cover CRUD, hierarchy/order operations, imports, sorting, team isolation, and CLI retrieval. Some tests spy on private helpers and assert exact Prisma query shapes. This constrains treatment compatibility and does not establish real database correctness.

The [end-to-end scaffold](https://github.com/hoppscotch/hoppscotch/blob/63273f8e599e73f0fb38c0739314e8d46b6bc83d/packages/hoppscotch-backend/test/app.e2e-spec.ts) checks a root HTTP response; it is not comprehensive collection integration coverage and has not been verified to pass.

The [root manifest](https://github.com/hoppscotch/hoppscotch/blob/63273f8e599e73f0fb38c0739314e8d46b6bc83d/package.json) specifies `pnpm@10.34.5`, and the [test workflow](https://github.com/hoppscotch/hoppscotch/blob/63273f8e599e73f0fb38c0739314e8d46b6bc83d/.github/workflows/tests.yml) uses Node 22 with a comment documenting test failures on Node 24. The backend manifest contains install-time Prisma/schema-generation scripts and disables TypeScript diagnostics in its Jest transform. Setup must account for those scripts, and acceptance must include a separate build.

The [Compose configuration](https://github.com/hoppscotch/hoppscotch/blob/63273f8e599e73f0fb38c0739314e8d46b6bc83d/docker-compose.yml) provides PostgreSQL 15 and migration commands. Search relies on the [migration enabling `pg_trgm`](https://github.com/hoppscotch/hoppscotch/blob/63273f8e599e73f0fb38c0739314e8d46b6bc83d/packages/hoppscotch-backend/prisma/migrations/20240226053141_full_text_search_additions/migration.sql). This is a documented setup path, not a reproduced environment. Freeze exact runtime versions and image digests in the next phase; moving major-version tags alone are insufficient.

## License and provenance

The [root LICENSE](https://github.com/hoppscotch/hoppscotch/blob/63273f8e599e73f0fb38c0739314e8d46b6bc83d/LICENSE) is MIT, and the [pinned README](https://github.com/hoppscotch/hoppscotch/blob/63273f8e599e73f0fb38c0739314e8d46b6bc83d/README.md) explicitly describes the project as MIT licensed. The private backend manifest also contains `"license": "UNLICENSED"`. Both facts must remain visible; this review does not invent an explanation for the discrepancy. No separate backend LICENSE was found in the inspected tree.

The selection relies on the explicit repository-level license and README. No subject source is redistributed by this foundation. Before distributing later variant source, review the conflicting metadata and applicable notices and record the distribution basis; do not silently replace upstream notices with the benchmark's own MIT license.

## Suitability and limitations

The bounded backend has multiple meaningful collaborators and an existing test suite, while the collection service offers distinct reasons for change. The proposed tasks exercise interchange, validation, sorting, and search without requiring external OAuth or mail services. Both variants will retain the same complete upstream source context; the backend is the explicit grading boundary.

Manageable scope and reproducible setup are selection judgments supported by configuration inspection, not completed runtime validation. The full monorepo, dependency lifecycle scripts, mocked tests, SQL/search requirements, and license metadata discrepancy remain preparation risks. See [limitations](limitations.md) and [methodology](methodology.md) for controls and gates.
