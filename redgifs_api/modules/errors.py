"""Shared errors, re-exported for provider compatibility."""
from base_api import (BotDetection, DownloadFailed, NetworkError, NotFound,
                      ProxyError, ResourceGone, UnknownNetworkError, VideoUnavailable)

__all__ = ["BotDetection", "DownloadFailed", "NetworkError", "NotFound", "ProxyError",
           "ResourceGone", "UnknownNetworkError", "VideoUnavailable"]
