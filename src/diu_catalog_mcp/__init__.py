"""DIU Commercial Solutions Catalog MCP server."""

import os

# The standard Hub downloader is more portable than the optional Xet client and
# works reliably through enterprise TLS proxies. This must be set before Qdrant
# or FastEmbed imports Hugging Face libraries.
os.environ.setdefault("HF_HUB_DISABLE_XET", "1")

__version__ = "0.1.0"
