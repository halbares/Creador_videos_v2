"""
Cliente para obtener contenido de feeds RSS.
Enfocado en fuentes de salud y bienestar.
"""

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

import feedparser
import yaml

from ..utils.backoff import with_retry, global_rate_limiter
from ..utils.cache import ContentCache

logger = logging.getLogger(__name__)


@dataclass
class RSSItem:
    """Representa un item de un feed RSS."""
    title: str
    summary: str
    url: str
    category: str
    published: Optional[datetime] = None
    source_feed: Optional[str] = None
    
    def to_dict(self) -> dict:
        return {
            "title": self.title,
            "summary": self.summary,
            "url": self.url,
            "category": self.category,
            "published": self.published.isoformat() if self.published else None,
            "source_feed": self.source_feed,
            "source_type": "rss"
        }


class RSSClient:
    """Cliente para obtener y procesar feeds RSS."""
    
    def __init__(
        self,
        config_path: str = "./config/sources.yaml",
        cache: Optional[ContentCache] = None
    ):
        """
        Inicializa el cliente RSS.
        
        Args:
            config_path: Ruta al archivo de configuración
            cache: Instancia de cache (crea una nueva si no se proporciona)
        """
        self.config = self._load_config(config_path)
        self.cache = cache or ContentCache()
        self.rate_limiter = global_rate_limiter
    
    def _load_config(self, path: str) -> dict:
        """Carga la configuración desde YAML."""
        try:
            with open(path, "r", encoding="utf-8") as f:
                config = yaml.safe_load(f)
                return config.get("rss", {})
        except FileNotFoundError:
            logger.warning(f"Archivo de configuración no encontrado: {path}")
            return {"feeds": [], "keywords": {"include": [], "exclude": []}}
    
    def _parse_date(self, entry: dict) -> Optional[datetime]:
        """Parsea la fecha de publicación de un entry."""
        if hasattr(entry, "published_parsed") and entry.published_parsed:
            try:
                return datetime(*entry.published_parsed[:6])
            except (TypeError, ValueError):
                pass
        return None
    
    def _matches_keywords(self, text: str) -> bool:
        """Verifica si el texto contiene keywords de inclusión y no de exclusión."""
        text_lower = text.lower()
        
        include_keywords = self.config.get("keywords", {}).get("include", [])
        exclude_keywords = self.config.get("keywords", {}).get("exclude", [])
        
        # Si no hay keywords de inclusión, todo pasa
        if not include_keywords:
            has_include = True
        else:
            has_include = any(kw.lower() in text_lower for kw in include_keywords)
        
        # Verificar exclusiones
        has_exclude = any(kw.lower() in text_lower for kw in exclude_keywords)
        
        return has_include and not has_exclude
    
    @with_retry(max_attempts=3, min_wait=2.0, max_wait=30.0)
    def _fetch_feed(self, url: str) -> feedparser.FeedParserDict:
        """
        Obtiene un feed RSS.
        
        Args:
            url: URL del feed
            
        Returns:
            Feed parseado
        """
        self.rate_limiter.wait_if_needed("rss")
        logger.info(f"Obteniendo feed: {url}")
        return feedparser.parse(url)
    
    def fetch_from_feed(self, feed_url: str, category: str = "general") -> list[RSSItem]:
        """
        Obtiene items de un feed específico.
        
        Args:
            feed_url: URL del feed RSS
            category: Categoría para etiquetar los items
            
        Returns:
            Lista de RSSItems
        """
        try:
            feed = self._fetch_feed(feed_url)
            items = []
            
            for entry in feed.entries:
                title = entry.get("title", "")
                summary = entry.get("summary", entry.get("description", ""))
                link = entry.get("link", "")
                
                # Limpiar HTML del summary
                if summary:
                    # Remover tags HTML básicos
                    import re
                    summary = re.sub(r"<[^>]+>", "", summary)
                    summary = summary.strip()
                
                # Verificar keywords
                full_text = f"{title} {summary}"
                if not self._matches_keywords(full_text):
                    continue
                
                # Verificar si ya fue visto
                if self.cache.is_content_seen(link):
                    continue
                
                item = RSSItem(
                    title=title,
                    summary=summary[:1000],  # Limitar longitud
                    url=link,
                    category=category,
                    published=self._parse_date(entry),
                    source_feed=feed_url
                )
                items.append(item)
            
            logger.info(f"Obtenidos {len(items)} items nuevos de {feed_url}")
            return items
            
        except Exception as e:
            logger.error(f"Error obteniendo feed {feed_url}: {e}")
            return []
    
    def fetch_all(self) -> list[RSSItem]:
        """
        Obtiene contenido de todos los feeds configurados.
        
        Returns:
            Lista de todos los RSSItems obtenidos
        """
        all_items = []
        feeds = self.config.get("feeds", [])
        
        for feed_config in feeds:
            url = feed_config.get("url")
            category = feed_config.get("category", "general")
            
            if not url:
                continue
            
            items = self.fetch_from_feed(url, category)
            all_items.extend(items)
        
        # Guardar en cache
        if all_items:
            items_dict = [item.to_dict() for item in all_items]
            new_count = self.cache.store_scraped_content("rss", items_dict)
            logger.info(f"Total: {len(all_items)} items, {new_count} nuevos guardados en cache")
        
        return all_items
    
    def get_cached_items(self) -> list[dict]:
        """Obtiene items de RSS desde el cache."""
        return self.cache.get_pending_content("rss")


def main():
    """Función principal para testing."""
    import argparse
    from rich.console import Console
    from rich.table import Table
    
    parser = argparse.ArgumentParser(description="RSS Scraper")
    parser.add_argument("--test", action="store_true", help="Modo de prueba")
    args = parser.parse_args()
    
    console = Console()
    client = RSSClient()
    
    console.print("[cyan]Obteniendo feeds RSS...[/cyan]")
    items = client.fetch_all()
    
    if items:
        table = Table(title="Items RSS Obtenidos")
        table.add_column("Título", style="green", max_width=40)
        table.add_column("Categoría", style="yellow")
        table.add_column("URL", style="blue", max_width=30)
        
        for item in items[:10]:  # Mostrar solo primeros 10
            table.add_row(
                item.title[:40],
                item.category,
                item.url[:30] + "..."
            )
        
        console.print(table)
        console.print(f"\n[green]Total: {len(items)} items obtenidos[/green]")
    else:
        console.print("[yellow]No se encontraron items nuevos[/yellow]")


if __name__ == "__main__":
    main()
