# Core ↔ Backend Orchestration Scaffold (Claims / Stakes / Links)

These tests are intentionally scaffold-only: they define what to validate once you wire:

- CORE_RPC_URL (Avalanche / local anvil / foundry)
- CORE_* contract addresses
- ABI access (either vendored ABIs or a build step)

Why scaffold now?
- It makes the “integration contract” explicit.
- You can begin validating end-to-end flows as soon as you have:
  - a chain endpoint
  - deployed contracts
  - a thin indexer or event reader

Next steps to fully activate this layer:
1) Decide your chain runner:
   - local anvil, foundry (anvil), hardhat node, or Fuji
2) Provide ABIs for:
   - PostRegistry
   - StakeEngine
   - LinkGraph
   - ProtocolViews
3) Add a tiny Python or Node event reader that:
   - emits canonical derived “claim / stake / link” state
4) Integrate that output with backend endpoints:
   - semantic dedupe + decomposition before core submission
   - post-submission indexing checks (if/when indexer exists)

Until then, tests auto-skip.

