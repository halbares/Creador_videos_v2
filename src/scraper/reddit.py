"""
Cliente para obtener contenido de Reddit.
Usa PRAW para acceder a la API de Reddit.
"""

import logging
import os
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

import praw
import yaml
from dotenv import load_dotenv

from ..utils.backoff import with_retry, global_rate_limiter
from ..utils.cache import ContentCache

load_dotenv()
logger = logging.getLogger(__name__)


@dataclass
class RedditPost:
    """Representa un post de Reddit."""
    title: str
    content: str
    url: str
    subreddit: str
    score: int
    num_comments: int
    top_comments: list[str]
    created_utc: datetime
    
    def to_dict(self) -> dict:
        return {
            "title": self.title,
            "content": self.content,
            "url": self.url,
            "subreddit": self.subreddit,
            "score": self.score,
            "num_comments": self.num_comments,
            "top_comments": self.top_comments,
            "created_utc": self.created_utc.isoformat(),
            "source_type": "reddit"
        }


class RedditClient:
    """Cliente para obtener contenido de Reddit."""
    
    def __init__(
        self,
        config_path: str = "./config/sources.yaml",
        cache: Optional[ContentCache] = None
    ):
        """
        Inicializa el cliente de Reddit.
        
        Args:
            config_path: Ruta al archivo de configuración
            cache: Instancia de cache
        """
        self.config = self._load_config(config_path)
        self.cache = cache or ContentCache()
        self.rate_limiter = global_rate_limiter
        self.reddit = self._init_reddit()
    
    def _load_config(self, path: str) -> dict:
        """Carga la configuración desde YAML."""
        try:
            with open(path, "r", encoding="utf-8") as f:
                config = yaml.safe_load(f)
                return config.get("reddit", {})
        except FileNotFoundError:
            logger.warning(f"Archivo de configuración no encontrado: {path}")
            return {"subreddits": [], "sort": "hot", "time_filter": "week"}
    
    def _init_reddit(self) -> Optional[praw.Reddit]:
        """Inicializa la conexión con Reddit."""
        client_id = os.getenv("REDDIT_CLIENT_ID")
        client_secret = os.getenv("REDDIT_CLIENT_SECRET")
        user_agent = os.getenv("REDDIT_USER_AGENT", "CreadorVideos/1.0")
        
        if not client_id or not client_secret:
            logger.warning("Credenciales de Reddit no configuradas. "
                         "Configura REDDIT_CLIENT_ID y REDDIT_CLIENT_SECRET en .env")
            return None
        
        try:
            reddit = praw.Reddit(
                client_id=client_id,
                client_secret=client_secret,
                user_agent=user_agent
            )
            # Verificar conexión
            reddit.user.me()
            logger.info("Conexión con Reddit establecida (modo solo lectura)")
            return reddit
        except Exception as e:
            logger.error(f"Error conectando con Reddit: {e}")
            # Intentar modo solo lectura
            try:
                reddit = praw.Reddit(
                    client_id=client_id,
                    client_secret=client_secret,
                    user_agent=user_agent
                )
                return reddit
            except Exception as e2:
                logger.error(f"Error en modo solo lectura: {e2}")
                return None
    
    def _get_top_comments(self, submission, limit: int = 5) -> list[str]:
        """Obtiene los mejores comentarios de un post."""
        comments = []
        try:
            submission.comments.replace_more(limit=0)
            for comment in submission.comments[:limit]:
                if hasattr(comment, "body") and len(comment.body) > 20:
                    # Limpiar y limitar
                    body = comment.body.strip()[:500]
                    comments.append(body)
        except Exception as e:
            logger.debug(f"Error obteniendo comentarios: {e}")
        return comments
    
    @with_retry(max_attempts=3, min_wait=2.0, max_wait=30.0)
    def fetch_subreddit(
        self,
        subreddit_name: str,
        limit: int = 10,
        sort: str = "hot",
        time_filter: str = "week"
    ) -> list[RedditPost]:
        """
        Obtiene posts de un subreddit.
        
        Args:
            subreddit_name: Nombre del subreddit
            limit: Número máximo de posts
            sort: Tipo de ordenamiento (hot, new, top)
            time_filter: Filtro de tiempo para 'top' (hour, day, week, month, year, all)
            
        Returns:
            Lista de RedditPosts
        """
        if not self.reddit:
            logger.warning("Reddit no está configurado")
            return []
        
        self.rate_limiter.wait_if_needed("reddit")
        
        try:
            subreddit = self.reddit.subreddit(subreddit_name)
            
            if sort == "hot":
                submissions = subreddit.hot(limit=limit)
            elif sort == "new":
                submissions = subreddit.new(limit=limit)
            elif sort == "top":
                submissions = subreddit.top(time_filter=time_filter, limit=limit)
            else:
                submissions = subreddit.hot(limit=limit)
            
            posts = []
            for submission in submissions:
                # Saltar posts fijados y sin contenido útil
                if submission.stickied:
                    continue
                
                # Obtener contenido
                content = submission.selftext if submission.is_self else submission.title
                url = f"https://reddit.com{submission.permalink}"
                
                # Verificar si ya fue visto
                if self.cache.is_content_seen(url):
                    continue
                
                # Obtener comentarios destacados
                top_comments = self._get_top_comments(submission)
                
                post = RedditPost(
                    title=submission.title,
                    content=content[:2000],
                    url=url,
                    subreddit=subreddit_name,
                    score=submission.score,
                    num_comments=submission.num_comments,
                    top_comments=top_comments,
                    created_utc=datetime.fromtimestamp(submission.created_utc)
                )
                posts.append(post)
            
            logger.info(f"Obtenidos {len(posts)} posts de r/{subreddit_name}")
            return posts
            
        except Exception as e:
            logger.error(f"Error obteniendo posts de r/{subreddit_name}: {e}")
            return []
    
    def fetch_all(self) -> list[RedditPost]:
        """
        Obtiene contenido de todos los subreddits configurados.
        
        Returns:
            Lista de todos los RedditPosts
        """
        all_posts = []
        subreddits = self.config.get("subreddits", [])
        sort = self.config.get("sort", "hot")
        time_filter = self.config.get("time_filter", "week")
        
        for sub_config in subreddits:
            name = sub_config.get("name")
            limit = sub_config.get("limit", 10)
            
            if not name:
                continue
            
            posts = self.fetch_subreddit(
                name,
                limit=limit,
                sort=sort,
                time_filter=time_filter
            )
            all_posts.extend(posts)
        
        # Guardar en cache
        if all_posts:
            posts_dict = [post.to_dict() for post in all_posts]
            new_count = self.cache.store_scraped_content("reddit", posts_dict)
            logger.info(f"Total: {len(all_posts)} posts, {new_count} nuevos guardados")
        
        return all_posts
    
    def get_cached_items(self) -> list[dict]:
        """Obtiene posts desde el cache."""
        return self.cache.get_pending_content("reddit")


def main():
    """Función principal para testing."""
    import argparse
    from rich.console import Console
    from rich.table import Table
    
    parser = argparse.ArgumentParser(description="Reddit Scraper")
    parser.add_argument("--test", action="store_true", help="Modo de prueba")
    args = parser.parse_args()
    
    console = Console()
    client = RedditClient()
    
    if not client.reddit:
        console.print("[red]Error: Reddit no está configurado.[/red]")
        console.print("Configura REDDIT_CLIENT_ID y REDDIT_CLIENT_SECRET en .env")
        return
    
    console.print("[cyan]Obteniendo posts de Reddit...[/cyan]")
    posts = client.fetch_all()
    
    if posts:
        table = Table(title="Posts de Reddit Obtenidos")
        table.add_column("Subreddit", style="magenta")
        table.add_column("Título", style="green", max_width=40)
        table.add_column("Score", style="yellow", justify="right")
        table.add_column("Comentarios", style="blue", justify="right")
        
        for post in posts[:10]:
            table.add_row(
                f"r/{post.subreddit}",
                post.title[:40],
                str(post.score),
                str(post.num_comments)
            )
        
        console.print(table)
        console.print(f"\n[green]Total: {len(posts)} posts obtenidos[/green]")
    else:
        console.print("[yellow]No se encontraron posts nuevos[/yellow]")


if __name__ == "__main__":
    main()
