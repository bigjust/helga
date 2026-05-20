import helga
from helga.plugins import command


@command("version", help="Responds in chat with the current version. Usage: helga version")
def version(*args, **kwargs):
    """
    Respond to a version request with the current version
    """
    return f"Helga version {helga.__version__}"
