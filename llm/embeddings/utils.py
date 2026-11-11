import math

def cosine(a: list[float], b: list[float]) -> float:
    if not a or len(a) != len(b): raise ValueError("Vector dimensions do not match")
    if not all(math.isfinite(x) for x in a + b): raise ValueError("Vectors must be finite")
    denominator = math.sqrt(sum(x*x for x in a)) * math.sqrt(sum(x*x for x in b))
    return sum(x*y for x,y in zip(a,b)) / denominator if denominator else 0.0
