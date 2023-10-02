# Copyright 2023-, Semiotic AI, Inc.
# SPDX-License-Identifier: Apache-2.0

from enum import Enum
from typing import Dict, Optional, Sequence

from allocopt.grt_utils import grt_decimal_to_wei


class OptMode(Enum):
    """allocation-optimizer optimizer mode.

    Note that `OptMode.FAST` is not recommended for production use, as it easily gets
    stuck in local optima.
    Note that `OptMode.OPTIMAL`, while the recommended mode, can sometimes randomly fail
    to converge on a solution and crash. In that case run it again.

    Args:
        Enum (Literal): allocation-optimizer optimizer mode
    """

    FAST = "fast"
    OPTIMAL = "optimal"


def allocopt(
    indexer_address: str,
    grt_gas_per_allocation: float,
    allocation_lifetime: int,
    thegraph_network_subgraph_endpoint: str,
    max_new_allocations: int,
    min_signal: int,
    opt_mode: OptMode = OptMode.OPTIMAL,
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
        min_signal (int): The minimum amount of signal you would like to allocate to
            each subgraph.
        opt_mode (OptMode, optional): allocation-optimizer optimizer mode. Defaults to
            `OptMode.OPTIMAL`.
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

    # Import Julia modules at the last moment to not make importing pyallocopt slow.
    from juliacall import Main as jl
    from juliacall import convert

    # Make sure AllocationOpt.jl is installed
    jl.Pkg.add(
        url="https://github.com/semiotic-ai/SemioticOpt.jl",
        rev="8b3b127270a15402427883c577425d5a96c0fe98",  # v2.4.2
    )
    jl.Pkg.add(
        url="https://github.com/semiotic-ai/TheGraphData.jl",
        rev="2d674d72a541fae838c60417c92fb56fe1d92602",
    )
    jl.Pkg.add(
        url="https://github.com/graphprotocol/allocation-optimizer.git",
        rev="ba26e3734d77fcf120b7f080469226896e44fd09",
    )

    # Load the AllocationOpt.jl
    jl.seval("using AllocationOpt")

    # Cast input params into the correct Julia types.
    whitelist = convert(jl.Array[jl.String], whitelist)
    blacklist = convert(jl.Array[jl.String], blacklist)
    pinnedlist = convert(jl.Array[jl.String], pinnedlist)
    frozenlist = convert(jl.Array[jl.String], frozenlist)

    # Create a config dictionary
    config = convert(
        jl.Dict[jl.String, jl.Any],
        {
            "id": indexer_address,
            "network_subgraph_endpoint": thegraph_network_subgraph_endpoint,
            "whitelist": whitelist,
            "blacklist": blacklist,
            "frozenlist": frozenlist,
            "pinnedlist": pinnedlist,
            "allocation_lifetime": allocation_lifetime,
            "gas": grt_gas_per_allocation,
            "min_signal": min_signal,
            "max_allocations": max_new_allocations,
            "num_reported_options": 1,
            "indexer_url": indexer_address,
            "verbose": True,
            "opt_mode": opt_mode.value,
            "readdir": None,
        },
    )

    jl.seval(
        """
        begin
        using AllocationOpt: read, allocatablesubgraphs, pinned, availablestake, frozen, stake, signal, newtokenissuance, deniedzeroixs, optimize, bestprofitpernz, sortprofits!, strategydict, writejson, execute, groupunique, fudgefactor
        function opt_fun(config::Dict)
            # Read data
            i, a, s, n = read(config)
             
            # Get the subgraphs on which we can allocate
            fs = allocatablesubgraphs(s, config)
             
            # Get the indexer stake
            pinnedvec = pinned(fs, config)
            σpinned = pinnedvec |> sum
            σ = availablestake(Val(:indexer), i) - frozen(a, config) - σpinned
            @assert σ > 0 "No stake available to allocate with the configured frozenlist and pinnedlist"

            # Allocated tokens on filtered subgraphs
            Ω = stake(Val(:subgraph), fs) .+ fudgefactor

            # Signal on filtered subgraphs
            ψ = signal(Val(:subgraph), fs)

            # Signal on all subgraphs
            Ψ = signal(Val(:network), n)

            # New tokens issued over allocation lifetime
            Φ = newtokenissuance(n, config)

            # Get indices of subgraphs that can get indexing rewards
            rixs = deniedzeroixs(fs)

            # Get max number of allocations
            K = min(config["max_allocations"], length(rixs))

            # Get gas cost in GRT
            g = config["gas"]

            # Get optimal values
            config["verbose"] && @info "Optimizing"
            xs, nonzeros, profitmatrix = optimize(Ω, ψ, σ, K, Φ, Ψ, g, rixs, config)

            # Add the pinned stake back in
            xs .= xs .+ pinnedvec

            # Ensure that the indexer stake is not exceeded
            σmax = σ + σpinned
            for x in sum(xs; dims=1)
                isnan(x) ||
                    x ≤ σmax ||
                    error("Tried to allocate more stake than is available by $(x - σmax)")
            end

            # Write the result values
            # Group by unique number of nonzeros
            groupixs = groupunique(nonzeros)
            groupixs = Dict(keys(groupixs) .=> values(groupixs))

            config["verbose"] && @info "Writing results report"
            # For each set of nonzeros, find max profit (should be the same other than rounding)
            popts = bestprofitpernz.(values(groupixs), Ref(profitmatrix)) |> sortprofits!
            nreport = min(config["num_reported_options"], length(popts))

            # Create JSON string
            strategies =
                strategydict.(popts[1:nreport], Ref(xs), Ref(nonzeros), Ref(fs), Ref(profitmatrix))

            return strategies
        end
        end
    """.strip()
    )

    res = jl.opt_fun(config)

    assert len(res) == 1, "Expected only one strategy to be returned"

    res = res[0]["allocations"]

    return {e["deploymentID"]: grt_decimal_to_wei(e["allocationAmount"]) for e in res}
