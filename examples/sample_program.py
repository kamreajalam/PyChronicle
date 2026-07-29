"""A small self-contained program used to populate a realistic trace session.

Deliberately import-free and loop-heavy so the tracer produces a good number
of line/call/return events with plenty of variable changes for the UI to show.
"""


def fibonacci(n):
    """Iterative fibonacci so the timeline shows repeated variable updates."""
    a, b = 0, 1
    for _ in range(n):
        a, b = b, a + b
    return a


def bubble_sort(values):
    items = list(values)
    for i in range(len(items)):
        for j in range(len(items) - i - 1):
            if items[j] > items[j + 1]:
                items[j], items[j + 1] = items[j + 1], items[j]
    return items


def average(values):
    total = 0
    for v in values:
        total += v
    return total / len(values) if values else 0


def classify(score):
    if score >= 90:
        return "excellent"
    if score >= 70:
        return "good"
    if score >= 50:
        return "average"
    return "needs work"


def safe_divide(a, b):
    try:
        return a / b
    except ZeroDivisionError:
        return None


def main():
    scores = [72, 45, 91, 60, 88]

    sorted_scores = bubble_sort(scores)
    mean = average(sorted_scores)
    label = classify(mean)
    fib = fibonacci(10)
    ratio = safe_divide(mean, 0)

    print(f"sorted={sorted_scores}")
    print(f"mean={mean:.2f} label={label} fib(10)={fib} ratio={ratio}")
    return label


if __name__ == "__main__":
    main()
