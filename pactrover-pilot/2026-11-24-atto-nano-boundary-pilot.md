# Atto vs. Nano First-Party Core Runtime Boundary Pilot (2026-11-24 UTC)

- **Author**: NovaCraft Studio (`z121245017-ai`), independently authored and verified
- **Date (UTC)**: `2026-11-24` (work started after written go-ahead at `2026-11-24T03:15:00Z` in [`pactrover/www#1#issuecomment-7120766319`](https://github.com/pactrover/www/issues/1#issuecomment-7120766319))
- **Pinned Commits Inspected (only)**:
  - **Atto**: [`attocash/node@471c73c9eeef911a2d43beaa4c776dd58affae47`](https://github.com/attocash/node/commit/471c73c9eeef911a2d43beaa4c776dd58affae47) (`2026-11-09T17:31:24Z`)
  - **Nano**: [`nanocurrency/nano-node@0d8eea4524b8da626cbab50c286c48eae25c76a9`](https://github.com/nanocurrency/nano-node/commit/0d8eea4524b8da626cbab50c286c48eae25c76a9) (`2025-08-20T11:27:03Z`)
- **Scope & Limits**: No candidate search, no line count, no build, and no benchmark were performed. **This pilot cannot establish which node is smaller.**
- **Rights**: Quotation, sharing, and reanalysis of this report are permitted with attribution to NovaCraft Studio (`z121245017-ai`).

## Six-Row Boundary Classification

| Node | Function | Representative Source Path | Commit-Pinned Evidence | Decision | One-Sentence Explanation |
| :--- | :--- | :--- | :--- | :--- | :--- |
| Atto | Persisting committed ledger state | `src/main/kotlin/cash/atto/node/account/AccountService.kt` | [`AccountService.kt#L160-L195`](https://github.com/attocash/node/blob/471c73c9eeef911a2d43beaa4c776dd58affae47/src/main/kotlin/cash/atto/node/account/AccountService.kt#L160-L195) | `include` | `AccountService.add` runs inside a `@Transactional` persistence boundary invoked after election consensus to durably save updated account states, transactions, and receivables, making it required first-party ledger-persistence runtime code. |
| Atto | Catching up with peers | `src/main/kotlin/cash/atto/node/bootstrap/discovery/GapDiscoverer.kt` | [`GapDiscoverer.kt#L70-L187`](https://github.com/attocash/node/blob/471c73c9eeef911a2d43beaa4c776dd58affae47/src/main/kotlin/cash/atto/node/bootstrap/discovery/GapDiscoverer.kt#L70-L187) | `include` | `GapDiscoverer.discover` and `startGapRequest` find missing account-height ranges, dispatch `AttoTransactionStreamRequest` messages to connected historical peers, and ingest `AttoTransactionStreamResponse` streams, which is essential first-party peer-to-peer state synchronization. |
| Atto | Serving a client's balance read | `src/main/kotlin/cash/atto/node/account/AccountController.kt` | [`AccountController.kt#L108-L117`](https://github.com/attocash/node/blob/471c73c9eeef911a2d43beaa4c776dd58affae47/src/main/kotlin/cash/atto/node/account/AccountController.kt#L108-L117) | `exclude` | `AccountController.get` (`GET /accounts/{publicKey}`) is an external HTTP REST query adapter returning `AttoAccount` (including balance) that `GlobalRequestInterceptor` blocks on port 8080 for voter-only nodes unless explicitly overridden, placing it outside the core P2P consensus and ledger-maintenance runtime. |
| Nano | Persisting committed ledger state | `nano/secure/ledger.cpp` | [`ledger.cpp#L991-L1066`](https://github.com/nanocurrency/nano-node/blob/0d8eea4524b8da626cbab50c286c48eae25c76a9/nano/secure/ledger.cpp#L991-L1066) | `include` | `ledger::confirm` and `ledger::confirm_one` (called by `cementing_set`) durably persist each cemented block's finality height and frontier via `store.confirmation_height.put` inside a write transaction, placing them directly inside the core committed-ledger persistence boundary. |
| Nano | Catching up with peers | `nano/node/bootstrap/bootstrap_service.cpp` | [`bootstrap_service.cpp#L532-L610`](https://github.com/nanocurrency/nano-node/blob/0d8eea4524b8da626cbab50c286c48eae25c76a9/nano/node/bootstrap/bootstrap_service.cpp#L532-L610) | `include` | `bootstrap_service::request` selects lagging accounts, builds ascending pull requests (`blocks_by_hash` or `blocks_by_account`), and sends `asc_pull_req` messages over peer channels, which is essential first-party peer-to-peer ledger synchronization. |
| Nano | Serving a client's balance read | `nano/node/json_handler.cpp` | [`json_handler.cpp#L515-L527`](https://github.com/nanocurrency/nano-node/blob/0d8eea4524b8da626cbab50c286c48eae25c76a9/nano/node/json_handler.cpp#L515-L527) | `exclude` | `json_handler::account_balance` is an external client JSON-RPC endpoint gated behind the off-by-default `rpc_enable` daemon switch rather than required P2P consensus or ledger-maintenance logic, even though it delegates balance lookup to internal ledger helpers. |

## First-Party Runtime Boundary Rule Used

**Include** handwritten first-party runtime code inside the node repository that is required for a standalone consensus/syncing node to validate blocks or transactions, reach finality, durably persist committed ledger state, or synchronize missing ledger state with peers (ledger state machine, validation, finality/consensus, P2P networking/bootstrap, persistence orchestration, and core runtime coordination).

**Exclude** external client-facing query/API adapters (such as HTTP REST controllers and JSON-RPC handlers exposed for external wallets or applications rather than peer-to-peer consensus or ledger maintenance), alongside tests, benchmarks, migrations/schemas, documentation, and third-party/external runtime engines.

**Use `uncertain`** when a repository does not visibly contain code for a function or couples a function across core runtime and external-client layers in a way that cannot be resolved from the pinned commit alone.

## One Boundary Decision the Full Study Must Resolve

**Whether external client-facing query/RPC interfaces belong inside or outside the standalone L1 runtime core—and where the cut falls when an external RPC adapter delegates to shared internal ledger-read primitives.**

The six rows expose this decision symmetrically across both repositories:

- Both nodes place client balance-read handlers in the main repository yet allow or enforce disabling them on headless/voting nodes: Atto's [`GlobalRequestInterceptor.kt#L21-L30`](https://github.com/attocash/node/blob/471c73c9eeef911a2d43beaa4c776dd58affae47/src/main/kotlin/cash/atto/node/GlobalRequestInterceptor.kt#L21-L30) rejects port 8080 requests with HTTP 403 on voter-only nodes unless `ATTO_NODE_FORCE_HISTORICAL` or `ATTO_NODE_FORCE_API` is set, while Nano's [`daemonconfig.hpp#L20`](https://github.com/nanocurrency/nano-node/blob/0d8eea4524b8da626cbab50c286c48eae25c76a9/nano/node/daemonconfig.hpp#L20) defaults `rpc_enable` to `false` and [`daemon.cpp#L138-L175`](https://github.com/nanocurrency/nano-node/blob/0d8eea4524b8da626cbab50c286c48eae25c76a9/nano/nano_node/daemon.cpp#L138-L175) only starts RPC (in-process or via a separate `nano_rpc` child process) when enabled.
- However, the internal boundary is not cleanly separated by directory: Nano's [`json_handler::account_balance`](https://github.com/nanocurrency/nano-node/blob/0d8eea4524b8da626cbab50c286c48eae25c76a9/nano/node/json_handler.cpp#L515-L527) lives under `nano/node/` alongside core node subsystems, mixes read-only client queries with wallet/admin control RPCs in the same handler file, and calls [`nano::node::balance_pending`](https://github.com/nanocurrency/nano-node/blob/0d8eea4524b8da626cbab50c286c48eae25c76a9/nano/node/node.cpp#L685-L692) → [`nano::ledger_set_confirmed::account_balance`](https://github.com/nanocurrency/nano-node/blob/0d8eea4524b8da626cbab50c286c48eae25c76a9/nano/secure/ledger_set_confirmed.cpp#L14-L22), which are shared internal ledger primitives also used by core runtime logic.

Before any line counting in a full study, the technical contract must explicitly settle whether a minimal external client-read API is required as part of a "standalone L1 core" (and if so, how to partition read-only query endpoints from co-located wallet/admin RPC surfaces) or excluded wholesale across all candidates while keeping internal ledger-read primitives included.

*(Note: This pilot evaluates boundary classification on six fixed rows only and cannot establish which node is smaller.)*
