# Copyright 2023-, Semiotic AI, Inc.
# SPDX-License-Identifier: Apache-2.0

from typing import Dict, Mapping, Optional, Sequence

from juliacall import Main as jl
from juliacall import convert

from allocopt.grt_utils import grt_decimal_to_wei

# Make sure AllocationOpt.jl is installed
jl.Pkg.add(
    url="https://github.com/graphprotocol/AllocationOpt.jl",
    rev="acccd71493e8eae121e4470636e573c0245eaf04",
)


def allocopt(
    indexer_address: str,
    grt_gas_per_allocation: float,
    allocation_lifetime: int,
    thegraph_network_subgraph_endpoint: str,
    max_new_allocations: int,
    tau_factor: float,
    whitelist: Optional[Sequence[str]] = None,
    blacklist: Optional[Sequence[str]] = None,
    pinnedlist: Optional[Sequence[str]] = None,
    frozenlist: Optional[Sequence[str]] = None,
) -> Dict[str, int]:
    """Generate optimized allocations using AllocationOpt.jl

    Args:
        indexer_address (str): Address of the indexer to optimize.
        grt_gas_per_allocation (float): Estimated gas cost of opening an allocation, in
            GRT.
        allocation_lifetime (int): The number of epochs for which these allocations
            would be open. An allocation earns indexing rewards for up to 28 epochs.
        thegraph_network_subgraph_endpoint (str): URL to a Graph Network subgraph
            GraphQL endpoint.
        max_new_allocations (int): The maximum number of new allocations you would like
            optimize.
        tau_factor (float): Interval [0,1]. As `tau_factior` gets closer to 0, the
            optimizer selects greedy allocations that maximize your short-term, expected
            rewards, but network dynamics will affect you more. The opposite occurs as
            `tau_factor` approaches 1.
        whitelist (Optional[Sequence[str]], optional): List of subgraph IPFS hashes to
            whitelist. Defaults to None.
        blacklist (Optional[Sequence[str]], optional): List of subgraph IPFS hashes to
            blacklist. Defaults to None.
        pinnedlist (Optional[Sequence[str]], optional): List of subgraph IPFS hashes to
            pin. Defaults to None.
        frozenlist (Optional[Sequence[str]], optional): List of subgraph IPFS hashes to
            freeze. Defaults to None.

    Returns:
        Dict[str, int]: Dictionary of subgraph deployments and amount to allocate in
            GRT wei.
    """
    # Create empty arrays for the input lists if they are `None`
    if not whitelist:
        whitelist = []
    if not blacklist:
        blacklist = []
    if not pinnedlist:
        pinnedlist = []
    if not frozenlist:
        frozenlist = []

    # Load the AllocationOpt.jl
    jl.seval("using AllocationOpt")

    # Cast input params into the correct Julia types.
    whitelist = convert(jl.Array[jl.String], whitelist)
    blacklist = convert(jl.Array[jl.String], blacklist)
    pinnedlist = convert(jl.Array[jl.String], pinnedlist)
    frozenlist = convert(jl.Array[jl.String], frozenlist)
    grtgas = jl.Float64(grt_gas_per_allocation)
    allocation_lifetime = jl.Int64(allocation_lifetime)

    # Let AllcationOpt.jl retrieve the current Graph network state.
    repo, indexer, network = jl.network_state(
        indexer_address,
        1,
        whitelist,
        blacklist,
        pinnedlist,
        frozenlist,
        thegraph_network_subgraph_endpoint,
    )
    fullrepo, _, _ = jl.network_state(
        indexer_address,
        1,
        jl.Array[jl.String]([]),
        jl.Array[jl.String]([]),
        jl.Array[jl.String]([]),
        jl.Array[jl.String]([]),
        thegraph_network_subgraph_endpoint,
    )

    filter_fn = jl.seval(
        "(network, grtgas, allocation_lifetime)"
        " -> (ω, ψ, Ω)"
        " -> apply_preferences(network, grtgas, allocation_lifetime, ω, ψ, Ω)"
    )(network, grtgas, allocation_lifetime)

    # Optimize!
    omega: Mapping[str, float] = jl.optimize_indexer(
        indexer,
        repo,
        fullrepo,
        max_new_allocations,
        tau_factor,
        filter_fn,
        pinnedlist,
    )

    # Convert all the GRT values to int (wei) to avoid math errors.
    return {k: grt_decimal_to_wei(v) for k, v in omega.items()}
