from __future__ import annotations

import pytest


@pytest.mark.skipif(True, reason="Scaffold only: enable once CORE_RPC_URL + ABIs + deployed contracts are wired.")
def test_core_claim_to_backend_roundtrip():
    """
    Target flow (future):
      1) user submits a compound claim
      2) backend decomposes -> atomic claims
      3) backend semantic-dedupes each atomic claim (reject duplicates)
      4) backend submits accepted claims to core (PostRegistry)
      5) backend/indexer derives state and verifies claim exists / IDs match
    """
    pass


@pytest.mark.skipif(True, reason="Scaffold only: enable once CORE_RPC_URL + ABIs + deployed contracts are wired.")
def test_core_stake_and_link_game_flow():
    """
    Target flow (future):
      1) create claim A and claim B
      2) stake support on A, challenge on B
      3) create link A supports B (or challenges)
      4) verify ProtocolViews aggregates expected read model outputs
      5) verify backend read endpoints reflect the same derived state
    """
    pass

