"""Alchemy WebSocket client — Ethereum pending transactions and new blocks."""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import websockets

logger = logging.getLogger(__name__)


@dataclass
class RawTransaction:
    tx_hash: str
    from_address: str | None
    to_address: str | None
    value_hex: str
    gas_price_hex: str | None
    gas_hex: str
    input_data: str
    raw: dict[str, Any]


@dataclass
class RawBlock:
    block_number: int
    block_hash: str
    parent_hash: str
    tx_count: int
    gas_used: int
    gas_limit: int
    base_fee_hex: str | None
    miner: str
    raw: dict[str, Any]


TransactionCallback = Callable[[RawTransaction], None]
BlockCallback = Callable[[RawBlock], None]


def hex_to_int(val: str | None) -> int:
    if not val:
        return 0
    try:
        return int(val, 16)
    except (ValueError, TypeError):
        return 0


class AlchemyWebSocket:
    def __init__(
        self,
        ws_url: str,
        on_transaction: TransactionCallback | None = None,
        on_block: BlockCallback | None = None,
        reconnect_delay: float = 5.0,
        max_reconnects: int = 0,
    ) -> None:
        self._url = ws_url
        self._on_transaction = on_transaction
        self._on_block = on_block
        self._reconnect_delay = reconnect_delay
        self._max_reconnects = max_reconnects
        self._reconnect_count = 0
        self._running = False

        # req_id -> subscription type mapping
        self._pending_tx_req_id: int | None = None
        self._block_req_id: int | None = None
        self._pending_sub_id: str | None = None
        self._block_sub_id: str | None = None
        self._req_id = 0

    async def start(self) -> None:
        self._running = True
        while self._running:
            try:
                await self._connect_and_stream()
            except Exception as exc:
                if not self._running:
                    break
                self._reconnect_count += 1
                if self._max_reconnects and self._reconnect_count > self._max_reconnects:
                    logger.error("Max reconnects reached, stopping stream")
                    break
                logger.warning(
                    "WebSocket disconnected (%s), reconnecting in %.1fs (attempt %d)",
                    exc, self._reconnect_delay, self._reconnect_count,
                )
                await asyncio.sleep(self._reconnect_delay)

    async def stop(self) -> None:
        self._running = False

    async def _connect_and_stream(self) -> None:
        logger.info("Connecting to Alchemy WebSocket: %s", self._url[:50] + "…")
        async with websockets.connect(
            self._url,
            ping_interval=30,
            ping_timeout=10,
            max_size=10 * 1024 * 1024,
        ) as ws:
            self._reconnect_count = 0
            # Reset sub IDs on reconnect
            self._pending_sub_id = None
            self._block_sub_id = None

            logger.info("WebSocket connected")

            # Subscribe pending txs — req_id 1
            self._req_id += 1
            self._pending_tx_req_id = self._req_id
            await ws.send(json.dumps({
                "jsonrpc": "2.0",
                "id": self._pending_tx_req_id,
                "method": "eth_subscribe",
                "params": ["alchemy_pendingTransactions", {
                    "includeRemoved": False,
                    "hashesOnly": False
                }],
            }))

            # Subscribe new blocks — req_id 2
            self._req_id += 1
            self._block_req_id = self._req_id
            await ws.send(json.dumps({
                "jsonrpc": "2.0",
                "id": self._block_req_id,
                "method": "eth_subscribe",
                "params": ["newHeads"],
            }))

            async for raw_msg in ws:
                if not self._running:
                    break
                try:
                    msg = json.loads(raw_msg)
                    await self._dispatch(msg)
                except json.JSONDecodeError:
                    pass
                except Exception:
                    logger.exception("Error dispatching message")

    async def _dispatch(self, msg: dict[str, Any]) -> None:
        # Subscription confirmations — map req_id to sub_id
        if "result" in msg and isinstance(msg["result"], str) and "id" in msg:
            req_id = msg["id"]
            sub_id = msg["result"]
            if req_id == self._pending_tx_req_id:
                self._pending_sub_id = sub_id
                logger.info("Pending tx subscription confirmed: %s", sub_id)
            elif req_id == self._block_req_id:
                self._block_sub_id = sub_id
                logger.info("Block subscription confirmed: %s", sub_id)
            return

        if msg.get("method") != "eth_subscription":
            return

        params = msg.get("params", {})
        sub_id = params.get("subscription")
        result = params.get("result", {})

        if sub_id == self._pending_sub_id:
            self._handle_pending_tx(result)
        elif sub_id == self._block_sub_id:
            self._handle_new_block(result)

    def _handle_pending_tx(self, data: dict[str, Any]) -> None:
        if not data or not self._on_transaction:
            return
        tx = RawTransaction(
            tx_hash=data.get("hash", ""),
            from_address=data.get("from"),
            to_address=data.get("to"),
            value_hex=data.get("value", "0x0"),
            gas_price_hex=data.get("gasPrice"),
            gas_hex=data.get("gas", "0x0"),
            input_data=data.get("input", "0x"),
            raw=data,
        )
        self._on_transaction(tx)

    def _handle_new_block(self, data: dict[str, Any]) -> None:
        if not data or not self._on_block:
            return
        block = RawBlock(
            block_number=hex_to_int(data.get("number")),
            block_hash=data.get("hash", ""),
            parent_hash=data.get("parentHash", ""),
            tx_count=len(data.get("transactions", [])),
            gas_used=hex_to_int(data.get("gasUsed")),
            gas_limit=hex_to_int(data.get("gasLimit")),
            base_fee_hex=data.get("baseFeePerGas"),
            miner=data.get("miner", ""),
            raw=data,
        )
        self._on_block(block)
