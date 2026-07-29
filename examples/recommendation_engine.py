"""Recommendation engine — co-occurrence, cosine similarity, top-N ranking.

Exercises a class-based code path (so the AST summary has classes, not just
functions) and produces tight numeric loops for the trace timeline.
"""

import os
import random

CATALOGUE = {
    "SKU-40119": "Thermal receipt printer",
    "SKU-40277": "Barcode scanner ring",
    "SKU-51302": "Cold-chain sensor tag",
    "SKU-51884": "Pallet label roll 4x6",
    "SKU-62015": "Forklift telemetry unit",
    "SKU-62119": "Dock door controller",
    "SKU-70441": "RF handheld cradle",
    "SKU-70882": "Yard camera mount",
}

ACCOUNTS = [
    "meridian-logistics",
    "halberstadt-werke",
    "trent-fielding",
    "kavery-freight",
    "straits-cold-storage",
    "rio-grande-distributors",
    "pacific-crest-grocers",
    "gulf-marine-supply",
]


class InteractionMatrix:
    """Sparse account/SKU interaction counts."""

    def __init__(self):
        self.rows = {}

    def record(self, account, sku, weight):
        row = self.rows.setdefault(account, {})
        row[sku] = round(row.get(sku, 0.0) + weight, 3)
        return row[sku]

    def vector(self, account):
        return self.rows.get(account, {})

    def accounts(self):
        return sorted(self.rows)


class Recommender:
    """Item-to-item recommender over an InteractionMatrix."""

    def __init__(self, matrix):
        self.matrix = matrix

    def dot_product(self, left, right):
        shared = set(left) & set(right)
        total = 0.0
        for key in sorted(shared):
            total = round(total + left[key] * right[key], 4)
        return total

    def magnitude(self, vector):
        squared = sum(value * value for value in vector.values())
        return round(squared ** 0.5, 4)

    def cosine_similarity(self, left, right):
        denominator = self.magnitude(left) * self.magnitude(right)
        if denominator == 0:
            return 0.0
        return round(self.dot_product(left, right) / denominator, 4)

    def neighbours(self, account, limit=3):
        target = self.matrix.vector(account)
        scored = []
        for other in self.matrix.accounts():
            if other == account:
                continue
            score = self.cosine_similarity(target, self.matrix.vector(other))
            if score > 0:
                scored.append((other, score))
        scored.sort(key=lambda item: item[1], reverse=True)
        return scored[:limit]

    def recommend(self, account, limit=3):
        owned = set(self.matrix.vector(account))
        candidates = {}
        for neighbour, similarity in self.neighbours(account):
            for sku, weight in self.matrix.vector(neighbour).items():
                if sku in owned:
                    continue
                candidates[sku] = round(
                    candidates.get(sku, 0.0) + similarity * weight, 4
                )
        ranked = sorted(candidates.items(), key=lambda item: item[1], reverse=True)
        return [
            {"sku": sku, "name": CATALOGUE[sku], "score": score}
            for sku, score in ranked[:limit]
        ]


def build_interactions(rng, accounts, events_per_account):
    """Fills the matrix with view / cart / purchase signals."""
    matrix = InteractionMatrix()
    weights = {"view": 0.4, "cart": 1.2, "purchase": 3.0}
    skus = sorted(CATALOGUE)

    for account in accounts:
        for _ in range(events_per_account):
            sku = rng.choice(skus)
            action = rng.choice(list(weights))
            matrix.record(account, sku, weights[action])
    return matrix


def coverage(recommendations):
    """How much of the catalogue the engine actually surfaces."""
    surfaced = set()
    for entries in recommendations.values():
        for entry in entries:
            surfaced.add(entry["sku"])
    return round(len(surfaced) / len(CATALOGUE), 3)


def main():
    scale = int(os.environ.get("PYCHRONICLE_SCALE", "4"))
    seed = int(os.environ.get("PYCHRONICLE_SEED", "29"))
    rng = random.Random(seed)

    accounts = ACCOUNTS[:max(2, min(len(ACCOUNTS), scale + 1))]
    matrix = build_interactions(rng, accounts, events_per_account=scale + 2)
    engine = Recommender(matrix)

    recommendations = {}
    for account in accounts:
        recommendations[account] = engine.recommend(account)

    print(f"accounts={len(accounts)} catalogue={len(CATALOGUE)} "
          f"coverage={coverage(recommendations)}")
    for account, entries in list(recommendations.items())[:3]:
        top = ", ".join(f"{e['sku']}({e['score']})" for e in entries)
        print(f"  {account}: {top or 'no recommendations'}")
    return recommendations


if __name__ == "__main__":
    main()
