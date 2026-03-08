"""Main entrypoint — Phase 1: verify live stream from Alchemy."""

from __future__ import annotations

import asyncio
import logging
import os
from dotenv import load_dotenv

from src.ingestion.alchemy_ws import AlchemyWebSocket, RawTransaction, RawBlock

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

TX_COUNT = 0
BLOCK_COUNT = 0


def on_transaction(tx: RawTransaction) -> None:
    global TX_COUNT
    TX_COUNT += 1
    value_eth = int(tx.value_hex, 16) / 1e18
    if value_eth > 0:
        print(f"[TX #{TX_COUNT}] {tx.tx_hash[:12]}… | {value_eth:.4f} ETH | from {str(tx.from_address)[:12]}…")


def on_block(block: RawBlock) -> None:
    global BLOCK_COUNT
    BLOCK_COUNT += 1
    if BLOCK_COUNT == 1:
        print(f"[DEBUG RAW BLOCK] {block.raw}")
    print(f"[BLOCK #{block.block_number}] {block.tx_count} txs | gas used {block.gas_used:,}")


async def main() -> None:
    ws_url = os.getenv("ALCHEMY_WS_URL")
    if not ws_url:
        raise ValueError("ALCHEMY_WS_URL not set in .env")

    logger.info("Connecting to Alchemy — Ethereum Mainnet")
    logger.info("Watching for live transactions...\n")

    client = AlchemyWebSocket(
        ws_url=ws_url,
        on_transaction=on_transaction,
        on_block=on_block,
    )

    try:
        await client.start()
    except KeyboardInterrupt:
        await client.stop()
        logger.info("Stopped. Transactions seen: %d | Blocks seen: %d", TX_COUNT, BLOCK_COUNT)


if __name__ == "__main__":
    asyncio.run(main())
