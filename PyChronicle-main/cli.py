import typer

from src.tracer import Tracer

app = typer.Typer(
    name="pychronicle",
    help="PyChronicle - Python execution time-travel debugger."
)


@app.command()
def run(
    file: str = typer.Argument(..., help="Python file to trace.")
):
    """Trace and record the execution of a Python file."""

    typer.echo(f"PyChronicle: tracing {file}")

    tracer = Tracer(verbose=False)

    try:
        tracer.trace_file(file)
    finally:
        tracer.close()


@app.command()
def version():
    """Show PyChronicle version."""
    typer.echo("PyChronicle version 1.0.0")


if __name__ == "__main__":
    app()