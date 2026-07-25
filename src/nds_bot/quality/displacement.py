import math


def log_displacement(start_price: float, end_price: float) -> float:
    """
    Calculate the logarithmic displacement between two positive prices.

    Positive result:
        The price moved upward.

    Negative result:
        The price moved downward.

    Zero result:
        The price did not change.
    """
    if start_price <= 0:
        raise ValueError("Start price must be positive.")

    if end_price <= 0:
        raise ValueError("End price must be positive.")

    return math.log(end_price / start_price)