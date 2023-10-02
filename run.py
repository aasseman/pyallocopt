from allocopt import allocopt

indexer_address = "0x6f8a032b4b1ee622ef2f0fc091bdbb98cfae81a3"
network_subgraph_endpoint = (
    "https://api.thegraph.com/subgraphs/name/graphprotocol/graph-network-arbitrum"
)

allocopt(indexer_address, 100, 28, network_subgraph_endpoint, 10, 100)
