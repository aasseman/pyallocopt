# PyAllocOpt

A python wrapper for [AllocationOpt.jl](https://github.com/graphprotocol/AllocationOpt.jl).

## Usage

It can use your current [Julia installation](https://julialang.org/downloads/) if it is available in your `$PATH`,
otherwise will install it automatically on first import.

Example:

```python
from allocopt import allocopt, grt_wei_to_decimal

allocations = allocopt(
    indexer_address="0xd75c4dbcb215a6cf9097cfbcc70aab2596b96a9c",
    grt_gas_per_allocation=100,
    allocation_lifetime=14,
    thegraph_network_subgraph_endpoint="http://indexer-service:7600/network",
    max_new_allocations=5,
    tau_factor=.2,
    blacklist=["QmTBxvMF6YnbT1eYeRx9XQpH4WvxTV53vdptCCZFiZSprg"]
)

# allocopt() returns allocation values in GRT wei, so that you can safely do math on
# them without the risk of floating point / rounding errors.

# Convert the GRT wei to decimal
allocations_decimal = {k: grt_wei_to_decimal(v) for k, v in allocations.items()}

print(allocations_decimal)
```
