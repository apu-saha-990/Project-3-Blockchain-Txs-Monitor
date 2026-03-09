"""Contract filter — tags transactions by type using input data signatures."""

from __future__ import annotations

from dataclasses import dataclass, field

# 4-byte function selectors for common contract interactions
# keccak256 of function signature, first 4 bytes
SIGNATURES: dict[str, str] = {
    # ERC-20
    "0xa9059cbb": "ERC20_TRANSFER",
    "0x23b872dd": "ERC20_TRANSFER_FROM",
    "0x095ea7b3": "ERC20_APPROVE",
    # ERC-721
    "0x42842e0e": "ERC721_SAFE_TRANSFER",
    "0xb88d4fde": "ERC721_SAFE_TRANSFER_DATA",
    # Uniswap V2
    "0x7ff36ab5": "UNI_SWAP_ETH_FOR_TOKENS",
    "0x18cbafe5": "UNI_SWAP_TOKENS_FOR_ETH",
    "0x38ed1739": "UNI_SWAP_TOKENS_FOR_TOKENS",
    # Uniswap V3
    "0x414bf389": "UNI_V3_EXACT_INPUT_SINGLE",
    "0xc04b8d59": "UNI_V3_EXACT_INPUT",
    "0xdb3e2198": "UNI_V3_EXACT_OUTPUT_SINGLE",
    # 1inch
    "0x7c025200": "ONEINCH_SWAP",
    "0x12aa3caf": "ONEINCH_FILL_ORDER",
    # WETH
    "0xd0e30db0": "WETH_DEPOSIT",
    "0x2e1a7d4d": "WETH_WITHDRAW",
    # OpenSea / NFT marketplaces
    "0xfb0f3ee1": "OPENSEA_MATCH_ORDER",
    "0xab834bab": "OPENSEA_ATOMIC_MATCH",
}

DEX_TYPES = {
    "UNI_SWAP_ETH_FOR_TOKENS", "UNI_SWAP_TOKENS_FOR_ETH",
    "UNI_SWAP_TOKENS_FOR_TOKENS", "UNI_V3_EXACT_INPUT_SINGLE",
    "UNI_V3_EXACT_INPUT", "UNI_V3_EXACT_OUTPUT_SINGLE",
    "ONEINCH_SWAP", "ONEINCH_FILL_ORDER",
}

ERC20_TYPES = {"ERC20_TRANSFER", "ERC20_TRANSFER_FROM", "ERC20_APPROVE"}
ERC721_TYPES = {"ERC721_SAFE_TRANSFER", "ERC721_SAFE_TRANSFER_DATA", "ERC721_TRANSFER_FROM"}
NFT_TYPES = {"OPENSEA_MATCH_ORDER", "OPENSEA_ATOMIC_MATCH"}


@dataclass
class ContractFilterResult:
    is_contract_call: bool
    contract_type: str | None       # 'DEX' | 'ERC20' | 'ERC721' | 'NFT' | 'WETH' | 'UNKNOWN'
    function_name: str | None
    selector: str | None
    tags: list[str] = field(default_factory=list)


class ContractFilter:
    def check(self, input_data: str, to_address: str | None) -> ContractFilterResult:
        # Pure ETH transfer — no input data
        if not input_data or input_data == "0x" or len(input_data) < 10:
            return ContractFilterResult(
                is_contract_call=False,
                contract_type=None,
                function_name=None,
                selector=None,
                tags=["ETH_TRANSFER"],
            )

        selector = input_data[:10].lower()
        function_name = SIGNATURES.get(selector)
        tags: list[str] = []

        if function_name is None:
            return ContractFilterResult(
                is_contract_call=True,
                contract_type="UNKNOWN",
                function_name=None,
                selector=selector,
                tags=["CONTRACT_UNKNOWN"],
            )

        # Classify by type
        if function_name in DEX_TYPES:
            contract_type = "DEX"
            tags.append("DEX_SWAP")
        elif function_name in ERC20_TYPES:
            contract_type = "ERC20"
            tags.append("TOKEN_TRANSFER")
        elif function_name in ERC721_TYPES:
            contract_type = "ERC721"
            tags.append("NFT_TRANSFER")
        elif function_name in NFT_TYPES:
            contract_type = "NFT"
            tags.append("NFT_SALE")
        elif "WETH" in function_name:
            contract_type = "WETH"
            tags.append("WETH_WRAP")
        else:
            contract_type = "UNKNOWN"

        return ContractFilterResult(
            is_contract_call=True,
            contract_type=contract_type,
            function_name=function_name,
            selector=selector,
            tags=tags,
        )
