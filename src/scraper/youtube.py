"""
Cliente para obtener contenido de YouTube.
Usa yt-dlp para extraer metadata y transcripciones.
"""

import logging
import os
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

import yaml
from dotenv import load_dotenv

from ..utils.backoff import with_retry, global_rate_limiter
from ..utils.cache import ContentCache

load_dotenv()
logger = logging.getLogger(__name__)


@dataclass
class YouTubeVideo:
    """Representa un video de YouTube."""
    title: str
    description: str
    url: str
    channel: str
    duration: int  # segundos
    view_count: int
    upload_date: Optional[datetime]
    transcript: Optional[str] = None
    
    def to_dict(self) -> dict:
        return {
            "title": self.title,
            "description": self.description,
            "url": self.url,
            "channel": self.channel,
            "duration": self.duration,
            "view_count": self.view_count,
            "upload_date": self.upload_date.isoformat() if self.upload_date else None,
            "transcript": self.transcript,
            "source_type": "youtube"
        }


class YouTubeClient:
    """Cliente para obtener contenido de YouTube."""
    
    def __init__(
        self,
        config_path: str = "./config/sources.yaml",
        cache: Optional[ContentCache] = None
    ):
        """
        Inicializa el cliente de YouTube.
        
        Args:
            config_path: Ruta al archivo de configuración
            cache: Instancia de cache
        """
        self.config = self._load_config(config_path)
        self.cache = cache or ContentCache()
        self.rate_limiter = global_rate_limiter
        self._ydl_opts = {
            "quiet": True,
            "no_warnings": True,
            "extract_flat": False,
            "writesubtitles": True,
            "writeautomaticsub": True,
            "subtitleslangs": ["es", "en"],
            "skip_download": True,
        }
    
    def _load_config(self, path: str) -> dict:
        """Carga la configuración desde YAML."""
        try:
            with open(path, "r", encoding="utf-8") as f:
                config = yaml.safe_load(f)
                return config.get("youtube", {})
        except FileNotFoundError:
            logger.warning(f"Archivo de configuración no encontrado: {path}")
            return {"channels": [], "searches": []}
    
    def _parse_duration(self, duration: Optional[int]) -> int:
        """Parsea la duración del video."""
        return duration if duration else 0
    
    def _parse_date(self, date_str: Optional[str]) -> Optional[datetime]:
        """Parsea la fecha de subida."""
        if not date_str:
            return None
        try:
            return datetime.strptime(date_str, "%Y%m%d")
        except ValueError:
            return None
    
    @with_retry(max_attempts=3, min_wait=2.0, max_wait=30.0)
    def _extract_info(self, url: str) -> Optional[dict]:
        """Extrae información de un video."""
        try:
            import yt_dlp
            
            self.rate_limiter.wait_if_needed("youtube")
            
            with yt_dlp.YoutubeDL(self._ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                return info
        except Exception as e:
            logger.error(f"Error extrayendo info de {url}: {e}")
            return None
    
    def _get_transcript(self, info: dict) -> Optional[str]:
        """Obtiene la transcripción del video si está disponible."""
        # Intentar obtener subtítulos automáticos o manuales
        subtitles = info.get("subtitles", {})
        automatic_captions = info.get("automatic_captions", {})
        
        # Preferir español, luego inglés
        for lang in ["es", "en"]:
            subs = subtitles.get(lang) or automatic_captions.get(lang)
            if subs:
                # Obtener la primera opción disponible
                for sub in subs:
                    if sub.get("ext") in ["vtt", "srt", "json3"]:
                        # Aquí se podría descargar y parsear el archivo
                        # Por ahora retornamos indicador de disponibilidad
                        return f"[Transcripción disponible en {lang}]"
        
        return None
    
    def fetch_video(self, url: str) -> Optional[YouTubeVideo]:
        """
        Obtiene información de un video específico.
        
        Args:
            url: URL del video
            
        Returns:
            YouTubeVideo o None si hay error
        """
        # Verificar cache
        if self.cache.is_content_seen(url):
            logger.debug(f"Video ya visto: {url}")
            return None
        
        info = self._extract_info(url)
        if not info:
            return None
        
        video = YouTubeVideo(
            title=info.get("title", ""),
            description=info.get("description", "")[:2000],
            url=url,
            channel=info.get("uploader", info.get("channel", "")),
            duration=self._parse_duration(info.get("duration")),
            view_count=info.get("view_count", 0),
            upload_date=self._parse_date(info.get("upload_date")),
            transcript=self._get_transcript(info)
        )
        
        return video
    
    def search_videos(self, query: str, max_results: int = 5) -> list[YouTubeVideo]:
        """
        Busca videos por query.
        
        Args:
            query: Término de búsqueda
            max_results: Número máximo de resultados
            
        Returns:
            Lista de YouTubeVideos
        """
        try:
            import yt_dlp
            
            self.rate_limiter.wait_if_needed("youtube")
            
            search_opts = {
                **self._ydl_opts,
                "extract_flat": True,
                "default_search": f"ytsearch{max_results}",
            }
            
            with yt_dlp.YoutubeDL(search_opts) as ydl:
                results = ydl.extract_info(query, download=False)
                
                videos = []
                entries = results.get("entries", [])
                
                for entry in entries:
                    if not entry:
                        continue
                    
                    url = entry.get("url") or f"https://youtube.com/watch?v={entry.get('id')}"
                    
                    # Verificar cache
                    if self.cache.is_content_seen(url):
                        continue
                    
                    video = YouTubeVideo(
                        title=entry.get("title", ""),
                        description=entry.get("description", "")[:2000] if entry.get("description") else "",
                        url=url,
                        channel=entry.get("uploader", entry.get("channel", "")),
                        duration=self._parse_duration(entry.get("duration")),
                        view_count=entry.get("view_count", 0),
                        upload_date=self._parse_date(entry.get("upload_date")),
                    )
                    videos.append(video)
                
                logger.info(f"Encontrados {len(videos)} videos para: {query}")
                return videos
                
        except Exception as e:
            logger.error(f"Error buscando videos: {e}")
            return []
    
    def fetch_all(self) -> list[YouTubeVideo]:
        """
        Obtiene videos de todas las búsquedas configuradas.
        
        Returns:
            Lista de YouTubeVideos
        """
        all_videos = []
        
        # Buscar por queries configuradas
        searches = self.config.get("searches", [])
        for search_config in searches:
            query = search_config.get("query")
            max_results = search_config.get("max_results", 5)
            
            if not query:
                continue
            
            videos = self.search_videos(query, max_results)
            all_videos.extend(videos)
        
        # Guardar en cache
        if all_videos:
            videos_dict = [video.to_dict() for video in all_videos]
            new_count = self.cache.store_scraped_content("youtube", videos_dict)
            logger.info(f"Total: {len(all_videos)} videos, {new_count} nuevos guardados")
        
        return all_videos
    
    def get_cached_items(self) -> list[dict]:
        """Obtiene videos desde el cache."""
        return self.cache.get_pending_content("youtube")


def main():
    """Función principal para testing."""
    import argparse
    from rich.console import Console
    from rich.table import Table
    
    parser = argparse.ArgumentParser(description="YouTube Scraper")
    parser.add_argument("--test", action="store_true", help="Modo de prueba")
    parser.add_argument("--search", type=str, help="Buscar videos")
    args = parser.parse_args()
    
    console = Console()
    client = YouTubeClient()
    
    if args.search:
        console.print(f"[cyan]Buscando: {args.search}[/cyan]")
        videos = client.search_videos(args.search, max_results=5)
    else:
        console.print("[cyan]Obteniendo videos de YouTube...[/cyan]")
        videos = client.fetch_all()
    
    if videos:
        table = Table(title="Videos de YouTube Obtenidos")
        table.add_column("Canal", style="magenta", max_width=20)
        table.add_column("Título", style="green", max_width=40)
        table.add_column("Duración", style="yellow", justify="right")
        table.add_column("Vistas", style="blue", justify="right")
        
        for video in videos[:10]:
            duration_str = f"{video.duration // 60}:{video.duration % 60:02d}"
            views_str = f"{video.view_count:,}" if video.view_count else "N/A"
            table.add_row(
                video.channel[:20],
                video.title[:40],
                duration_str,
                views_str
            )
        
        console.print(table)
        console.print(f"\n[green]Total: {len(videos)} videos obtenidos[/green]")
    else:
        console.print("[yellow]No se encontraron videos nuevos[/yellow]")


if __name__ == "__main__":
    main()
