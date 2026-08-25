from __future__ import annotations

import ssl
from functools import lru_cache

import truststore


@lru_cache(maxsize=1)
def system_ssl_context() -> ssl.SSLContext:
    """Return a TLS client context backed by the operating system trust store."""
    return truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)


def configure_system_trust() -> None:
    """Use the OS trust store in libraries that construct their own SSL contexts."""
    truststore.inject_into_ssl()

