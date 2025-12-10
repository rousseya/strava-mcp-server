from .main import mcp

__all__ = ["mcp"]


def __getattr__(name: str):
    if name == "__main__":
        mcp.run()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")