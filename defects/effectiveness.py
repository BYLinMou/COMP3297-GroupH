def classify_developer(fixed: int, reopened: int) -> str:
    if fixed < 0 or reopened < 0:
        raise ValueError("fixed and reopened cannot be negative.")

    if fixed < 20:
        return "Insufficient data"

    ratio = reopened / fixed
    if ratio < (1 / 32):
        return "Good"
    if ratio < (1 / 8):
        return "Fair"
    return "Poor"
