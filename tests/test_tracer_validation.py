import os
import sys

# Add project root to Python path
sys.path.insert(
    0,
    os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
)

from src.tracer import Tracer


def test_tracer_records_complex_loop():
    """
    Validate that the tracer records execution of a complex loop
    without dropping execution events.
    """

    def complex_loop(n):
        total = 0

        for i in range(n):
            if i % 2 == 0:
                total += i
            else:
                total -= i

        return total

    tracer = Tracer(verbose=False)

    try:
        session_id, event_count = tracer.trace_callable(
            complex_loop,
            10,
            session_name="complex_loop_validation"
        )
    finally:
        tracer.close()

    # A valid tracing session must be created
    assert session_id is not None

    # The tracer must record execution events
    assert event_count > 0

    # The loop executes 10 iterations, so multiple events
    # must have been captured.
    assert event_count >= 10