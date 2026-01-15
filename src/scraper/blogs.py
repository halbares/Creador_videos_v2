"""
Scraper genérico para blogs y páginas web.
Usa BeautifulSoup para extraer contenido.
"""

import logging
import re
from dataclasses import dataclass
from typing import Optional

import httpx
import yaml
from bs4 import BeautifulSoup

from ..utils.backoff import with_retry, global_rate_limiter
from ..utils.cache import ContentCache

logger = logging.getLogger(__name__)


@dataclass
class BlogArticle:
    """Representa un artículo de blog."""
    title: str
    content: str
    url: str
    excerpt: str
    
    def to_dict(self) -> dict:
        return {
            "title": self.title,
            "content": self.content,
            "url": self.url,
            "excerpt": self.excerpt,
            "source_type": "blog"
        }


class BlogScraper:
    """Scraper genérico para blogs y páginas web."""
    
    def __init__(
        self,
        config_path: str = "./config/sources.yaml",
        cache: Optional[ContentCache] = None
    ):
        """
        Inicializa el scraper de blogs.
        
        Args:
            config_path: Ruta al archivo de configuración
            cache: Instancia de cache
        """
        self.config = self._load_config(config_path)
        self.cache = cache or ContentCache()
        self.rate_limiter = global_rate_limiter
        self.client = httpx.Client(
            timeout=30.0,
            follow_redirects=True,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            }
        )
    
    def _load_config(self, path: str) -> dict:
        """Carga la configuración desde YAML."""
        try:
            with open(path, "r", encoding="utf-8") as f:
                config = yaml.safe_load(f)
                return config.get("blogs", {})
        except FileNotFoundError:
            logger.warning(f"Archivo de configuración no encontrado: {path}")
            return {"urls": []}
    
    def _clean_text(self, text: str) -> str:
        """Limpia el texto extraído."""
        # Remover espacios múltiples
        text = re.sub(r"\s+", " ", text)
        # Remover líneas vacías múltiples
        text = re.sub(r"\n\s*\n", "\n\n", text)
        return text.strip()
    
    def _extract_article_content(
        self,
        soup: BeautifulSoup,
        selector: Optional[str] = None
    ) -> tuple[str, str]:
        """
        Extrae el contenido principal del artículo.
        
        Args:
            soup: BeautifulSoup parseado
            selector: Selector CSS opcional
            
        Returns:
            Tupla de (título, contenido)
        """
        # Extraer título
        title = ""
        title_tag = soup.find("h1") or soup.find("title")
        if title_tag:
            title = title_tag.get_text(strip=True)
        
        # Extraer contenido
        content = ""
        
        if selector:
            # Usar selector específico
            main_content = soup.select_one(selector)
            if main_content:
                content = main_content.get_text(separator=" ", strip=True)
        
        if not content:
            # Intentar selectores comunes
            selectors = [
                "article",
                "main",
                ".post-content",
                ".entry-content",
                ".article-content",
                ".content",
                "#content",
            ]
            
            for sel in selectors:
                element = soup.select_one(sel)
                if element:
                    content = element.get_text(separator=" ", strip=True)
                    if len(content) > 200:  # Contenido significativo
                        break
        
        if not content:
            # Fallback: todo el body
            body = soup.find("body")
            if body:
                # Remover scripts, styles, nav, footer
                for tag in body.find_all(["script", "style", "nav", "footer", "header", "aside"]):
                    tag.decompose()
                content = body.get_text(separator=" ", strip=True)
        
        content = self._clean_text(content)
        return title, content
    
    @with_retry(max_attempts=3, min_wait=2.0, max_wait=30.0)
    def _fetch_url(self, url: str) -> Optional[str]:
        """Obtiene el HTML de una URL."""
        self.rate_limiter.wait_if_needed("blogs")
        
        try:
            response = self.client.get(url)
            response.raise_for_status()
            return response.text
        except Exception as e:
            logger.error(f"Error obteniendo {url}: {e}")
            return None
    
    def scrape_url(
        self,
        url: str,
        selector: Optional[str] = None
    ) -> Optional[BlogArticle]:
        """
        Extrae contenido de una URL específica.
        
        Args:
            url: URL a scrapear
            selector: Selector CSS para el contenido principal
            
        Returns:
            BlogArticle o None si hay error
        """
        # Verificar cache
        if self.cache.is_content_seen(url):
            logger.debug(f"URL ya vista: {url}")
            return None
        
        html = self._fetch_url(url)
        if not html:
            return None
        
        soup = BeautifulSoup(html, "html.parser")
        title, content = self._extract_article_content(soup, selector)
        
        if not content or len(content) < 100:
            logger.warning(f"Contenido insuficiente en: {url}")
            return None
        
        # Crear excerpt
        excerpt = content[:300] + "..." if len(content) > 300 else content
        
        article = BlogArticle(
            title=title,
            content=content[:5000],  # Limitar longitud
            url=url,
            excerpt=excerpt
        )
        
        logger.info(f"Extraído: {title[:50]}...")
        return article
    
    def fetch_all(self) -> list[BlogArticle]:
        """
        Scrapea todas las URLs configuradas.
        
        Returns:
            Lista de BlogArticles
        """
        all_articles = []
        urls_config = self.config.get("urls", [])
        
        for url_config in urls_config:
            url = url_config.get("url")
            selector = url_config.get("selector")
            
            if not url:
                continue
            
            article = self.scrape_url(url, selector)
            if article:
                all_articles.append(article)
        
        # Guardar en cache
        if all_articles:
            articles_dict = [article.to_dict() for article in all_articles]
            new_count = self.cache.store_scraped_content("blogs", articles_dict)
            logger.info(f"Total: {len(all_articles)} artículos, {new_count} nuevos guardados")
        
        return all_articles
    
    def get_cached_items(self) -> list[dict]:
        """Obtiene artículos desde el cache."""
        return self.cache.get_pending_content("blogs")
    
    def close(self):
        """Cierra el cliente HTTP."""
        self.client.close()


def main():
    """Función principal para testing."""
    import argparse
    from rich.console import Console
    from rich.table import Table
    
    parser = argparse.ArgumentParser(description="Blog Scraper")
    parser.add_argument("--test", action="store_true", help="Modo de prueba")
    parser.add_argument("--url", type=str, help="Scrapear URL específica")
    args = parser.parse_args()
    
    console = Console()
    scraper = BlogScraper()
    
    try:
        if args.url:
            console.print(f"[cyan]Scrapeando: {args.url}[/cyan]")
            article = scraper.scrape_url(args.url)
            if article:
                console.print(f"\n[green]Título:[/green] {article.title}")
                console.print(f"\n[green]Excerpt:[/green] {article.excerpt}")
                console.print(f"\n[green]Contenido ({len(article.content)} chars)[/green]")
            else:
                console.print("[red]No se pudo extraer contenido[/red]")
        else:
            console.print("[cyan]Scrapeando blogs configurados...[/cyan]")
            articles = scraper.fetch_all()
            
            if articles:
                table = Table(title="Artículos Extraídos")
                table.add_column("Título", style="green", max_width=50)
                table.add_column("Longitud", style="yellow", justify="right")
                
                for article in articles:
                    table.add_row(
                        article.title[:50],
                        f"{len(article.content)} chars"
                    )
                
                console.print(table)
            else:
                console.print("[yellow]No se encontraron artículos nuevos[/yellow]")
    finally:
        scraper.close()


if __name__ == "__main__":
    main()
