"""Value filter — flags transactions above configurable ETH threshold."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ValueFilterResult:
    passed: bool
    value_eth: float
    is_whale: bool        # > 100 ETH
    is_large: bool        # > 10 ETH
    is_medium: bool       # > 1 ETH


class ValueFilter:
    def __init__(
        self,
        medium_threshold_eth: float = 1.0,
        large_threshold_eth: float = 10.0,
        whale_threshold_eth: float = 100.0,
    ) -> None:
        self._medium = medium_threshold_eth
        self._large = large_threshold_eth
        self._whale = whale_threshold_eth

    def check(self, value_hex: str) -> ValueFilterResult:
        try:
            value_eth = int(value_hex, 16) / 1e18
        except (ValueError, TypeError):
            value_eth = 0.0

        return ValueFilterResult(
            passed=value_eth >= self._medium,
            value_eth=value_eth,
            is_whale=value_eth >= self._whale,
            is_large=value_eth >= self._large,
            is_medium=value_eth >= self._medium,
        )
