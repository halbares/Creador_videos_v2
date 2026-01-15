"""Módulo de scraping para obtener contenido de múltiples fuentes."""

from .rss import RSSClient
from .reddit import RedditClient
from .youtube import YouTubeClient
from .blogs import BlogScraper

__all__ = ["RSSClient", "RedditClient", "YouTubeClient", "BlogScraper"]
