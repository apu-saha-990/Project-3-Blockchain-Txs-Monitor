"""Gas filter — detects gas price spikes against a rolling average."""

from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass


@dataclass
class GasFilterResult:
    gas_price_gwei: float
    gas_limit: int
    gas_cost_eth: float
    is_spike: bool
    spike_multiplier: float   # how many times above average
    rolling_avg_gwei: float | None


class GasFilter:
    def __init__(
        self,
        spike_multiplier: float = 3.0,
        window_seconds: int = 600,
    ) -> None:
        self._spike_multiplier = spike_multiplier
        self._window_seconds = window_seconds
        # deque of (timestamp, gas_price_gwei)
        self._samples: deque[tuple[float, float]] = deque()

    def check(self, gas_price_hex: str | None, gas_hex: str) -> GasFilterResult:
        now = time.time()

        gas_price_gwei = (int(gas_price_hex, 16) / 1e9) if gas_price_hex else 0.0
        gas_limit = int(gas_hex, 16) if gas_hex else 0
        gas_cost_eth = (gas_limit * gas_price_gwei) / 1e9

        # Prune old samples outside window
        while self._samples and now - self._samples[0][0] > self._window_seconds:
            self._samples.popleft()

        # Calculate rolling average
        rolling_avg: float | None = None
        is_spike = False
        spike_mult = 1.0

        if self._samples:
            rolling_avg = sum(g for _, g in self._samples) / len(self._samples)
            if rolling_avg > 0 and gas_price_gwei > 0:
                spike_mult = gas_price_gwei / rolling_avg
                is_spike = spike_mult >= self._spike_multiplier

        # Add current sample
        if gas_price_gwei > 0:
            self._samples.append((now, gas_price_gwei))

        return GasFilterResult(
            gas_price_gwei=gas_price_gwei,
            gas_limit=gas_limit,
            gas_cost_eth=gas_cost_eth,
            is_spike=is_spike,
            spike_multiplier=spike_mult,
            rolling_avg_gwei=rolling_avg,
        )
