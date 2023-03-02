# Copyright 2023-, Semiotic AI, Inc.
# SPDX-License-Identifier: Apache-2.0

from contextlib import contextmanager
from decimal import Context, Decimal, getcontext, setcontext

_GRT_DECIMAL_CONTEXT = Context(
    prec=78,  # Fits the whole 256bit number range
)
_GRT_DECIMALS = Decimal(18)
_GRT_DECIMAL_FACTOR = Decimal(10) ** _GRT_DECIMALS


@contextmanager
def _grt_decimal_context():
    """Context manager to temporarily set the GRT_DECIMAL_CONTEXT.

    The GRT_DECIMAL_CONTEXT is used to accomplish Decimal calculations with the
    correct number of digits of precision for GRT tokens.

    Yields:
        None
    """
    initial_context = getcontext()
    setcontext(_GRT_DECIMAL_CONTEXT)
    try:
        yield None
    finally:
        setcontext(initial_context)


def grt_wei_to_decimal(grt_wei: int) -> Decimal:
    """Convert an integer GRT wei value to a Decimal with 78 digits of precision.

    Args:
        grt_wei (int): GRT wei value.

    Returns:
        Decimal: GRT decimal value.
    """
    with _grt_decimal_context():
        grt_decimal = Decimal(grt_wei) / _GRT_DECIMAL_FACTOR
    return grt_decimal


def grt_decimal_to_wei(
    grt_decimal: Decimal | float, rounding: str | None = None
) -> int:
    """Converts a Decimal (preferred) or float GRT value to integer GRT wei.

    Args:
        grt_decimal (Decimal | float): GRT value.
        rounding (str | None, optional): Rounding, as defined in Decimal (Python
            stdlib). Defaults to the current Decimal context setting.

    Returns:
        int: GRT wei value.
    """
    with _grt_decimal_context():
        grt_wei = int(
            Decimal(grt_decimal).quantize(1 / _GRT_DECIMAL_FACTOR, rounding=rounding)
            * _GRT_DECIMAL_FACTOR
        )
    return grt_wei
