"""
Cliente para Pexels API.
Obtiene videos e imágenes de fondo para los videos.
"""

import logging
import os
import random
from pathlib import Path
from typing import Optional, Literal

import httpx
from dotenv import load_dotenv

from ..utils.backoff import with_retry, global_rate_limiter

load_dotenv()
logger = logging.getLogger(__name__)


class PexelsClient:
    """Cliente para obtener media de Pexels."""
    
    BASE_URL = "https://api.pexels.com"
    
    def __init__(self, assets_dir: str = "./assets"):
        """
        Inicializa el cliente de Pexels.
        
        Args:
            assets_dir: Directorio para guardar assets descargados
        """
        self.assets_dir = Path(assets_dir)
        self.assets_dir.mkdir(parents=True, exist_ok=True)
        
        self.api_key = os.getenv("PEXELS_API_KEY")
        self.rate_limiter = global_rate_limiter
        
        if not self.api_key:
            logger.warning("PEXELS_API_KEY no configurada")
        
        self.client = httpx.Client(
            timeout=60.0,
            headers={"Authorization": self.api_key} if self.api_key else {}
        )
    
    @with_retry(max_attempts=3, min_wait=2.0, max_wait=30.0)
    def search_videos(
        self,
        query: str,
        orientation: Literal["landscape", "portrait", "square"] = "portrait",
        size: Literal["large", "medium", "small"] = "medium",
        per_page: int = 10
    ) -> list[dict]:
        """
        Busca videos en Pexels.
        
        Args:
            query: Término de búsqueda
            orientation: Orientación del video
            size: Tamaño del video
            per_page: Resultados por página
            
        Returns:
            Lista de videos encontrados
        """
        if not self.api_key:
            logger.error("API key de Pexels no configurada")
            return []
        
        self.rate_limiter.wait_if_needed("pexels")
        
        url = f"{self.BASE_URL}/videos/search"
        params = {
            "query": query,
            "orientation": orientation,
            "size": size,
            "per_page": per_page
        }
        
        try:
            response = self.client.get(url, params=params)
            response.raise_for_status()
            data = response.json()
            
            videos = data.get("videos", [])
            logger.info(f"Encontrados {len(videos)} videos para: {query}")
            return videos
            
        except Exception as e:
            logger.error(f"Error buscando videos: {e}")
            return []
    
    @with_retry(max_attempts=3, min_wait=2.0, max_wait=30.0)
    def search_photos(
        self,
        query: str,
        orientation: Literal["landscape", "portrait", "square"] = "portrait",
        size: Literal["large", "medium", "small"] = "large",
        per_page: int = 10
    ) -> list[dict]:
        """
        Busca fotos en Pexels.
        
        Args:
            query: Término de búsqueda
            orientation: Orientación de la foto
            size: Tamaño de la foto
            per_page: Resultados por página
            
        Returns:
            Lista de fotos encontradas
        """
        if not self.api_key:
            logger.error("API key de Pexels no configurada")
            return []
        
        self.rate_limiter.wait_if_needed("pexels")
        
        url = f"{self.BASE_URL}/v1/search"
        params = {
            "query": query,
            "orientation": orientation,
            "size": size,
            "per_page": per_page
        }
        
        try:
            response = self.client.get(url, params=params)
            response.raise_for_status()
            data = response.json()
            
            photos = data.get("photos", [])
            logger.info(f"Encontradas {len(photos)} fotos para: {query}")
            return photos
            
        except Exception as e:
            logger.error(f"Error buscando fotos: {e}")
            return []
    
    def download_video(
        self,
        video: dict,
        quality: Literal["hd", "sd", "hls"] = "hd"
    ) -> Optional[str]:
        """
        Descarga un video de Pexels.
        
        Args:
            video: Dict con información del video
            quality: Calidad deseada
            
        Returns:
            Ruta al archivo descargado o None
        """
        video_files = video.get("video_files", [])
        
        if not video_files:
            logger.error("Video sin archivos disponibles")
            return None
        
        # Buscar la calidad deseada
        target_file = None
        
        # Ordenar por calidad (mayor altura primero)
        sorted_files = sorted(
            video_files,
            key=lambda x: x.get("height", 0),
            reverse=True
        )
        
        # Para portrait, buscar aspect ratio vertical
        for vf in sorted_files:
            width = vf.get("width", 0)
            height = vf.get("height", 0)
            
            # Preferir videos verticales (9:16) o al menos más altos que anchos
            if height >= width:
                if quality == "hd" and height >= 1080:
                    target_file = vf
                    break
                elif quality == "sd" and height >= 720:
                    target_file = vf
                    break
                elif height >= 480:
                    target_file = vf
                    break
        
        # Fallback al primer archivo disponible
        if not target_file:
            target_file = sorted_files[0]
        
        download_url = target_file.get("link")
        if not download_url:
            logger.error("No se encontró URL de descarga")
            return None
        
        # Generar nombre de archivo
        video_id = video.get("id", "unknown")
        extension = download_url.split(".")[-1].split("?")[0]
        if extension not in ["mp4", "webm", "mov"]:
            extension = "mp4"
        
        output_path = self.assets_dir / f"pexels_video_{video_id}.{extension}"
        
        # Descargar si no existe
        if output_path.exists():
            logger.info(f"Video ya descargado: {output_path}")
            return str(output_path)
        
        try:
            logger.info(f"Descargando video: {download_url[:50]}...")
            
            with self.client.stream("GET", download_url) as response:
                response.raise_for_status()
                
                with open(output_path, "wb") as f:
                    for chunk in response.iter_bytes(chunk_size=8192):
                        f.write(chunk)
            
            logger.info(f"Video descargado: {output_path}")
            return str(output_path)
            
        except Exception as e:
            logger.error(f"Error descargando video: {e}")
            return None
    
    def download_photo(self, photo: dict) -> Optional[str]:
        """
        Descarga una foto de Pexels.
        
        Args:
            photo: Dict con información de la foto
            
        Returns:
            Ruta al archivo descargado o None
        """
        src = photo.get("src", {})
        
        # Preferir tamaño large o original
        download_url = src.get("large2x") or src.get("large") or src.get("original")
        
        if not download_url:
            logger.error("No se encontró URL de descarga")
            return None
        
        photo_id = photo.get("id", "unknown")
        output_path = self.assets_dir / f"pexels_photo_{photo_id}.jpg"
        
        if output_path.exists():
            logger.info(f"Foto ya descargada: {output_path}")
            return str(output_path)
        
        try:
            logger.info(f"Descargando foto...")
            
            response = self.client.get(download_url)
            response.raise_for_status()
            
            with open(output_path, "wb") as f:
                f.write(response.content)
            
            logger.info(f"Foto descargada: {output_path}")
            return str(output_path)
            
        except Exception as e:
            logger.error(f"Error descargando foto: {e}")
            return None
    
    def get_random_background(
        self,
        keywords: list[str],
        media_type: Literal["video", "photo"] = "video"
    ) -> Optional[str]:
        """
        Obtiene un fondo aleatorio basado en keywords.
        
        Args:
            keywords: Lista de palabras clave
            media_type: Tipo de media (video o photo)
            
        Returns:
            Ruta al archivo descargado o None
        """
        # Construir query
        query = " ".join(keywords[:3])  # Máximo 3 keywords
        
        # Agregar términos para fondos abstractos/neutros
        background_terms = ["abstract", "nature", "minimal", "calm", "wellness"]
        query = f"{query} {random.choice(background_terms)}"
        
        if media_type == "video":
            results = self.search_videos(query, orientation="portrait", per_page=5)
            if results:
                video = random.choice(results)
                return self.download_video(video)
        else:
            results = self.search_photos(query, orientation="portrait", per_page=5)
            if results:
                photo = random.choice(results)
                return self.download_photo(photo)
        
        return None
    
    def close(self):
        """Cierra el cliente HTTP."""
        self.client.close()


def main():
    """Función principal para testing."""
    import argparse
    from rich.console import Console
    from rich.table import Table
    
    parser = argparse.ArgumentParser(description="Pexels Client")
    parser.add_argument("--search", type=str, help="Buscar videos")
    parser.add_argument("--photos", action="store_true", help="Buscar fotos en lugar de videos")
    parser.add_argument("--download", action="store_true", help="Descargar primer resultado")
    parser.add_argument("--random", type=str, help="Obtener fondo aleatorio con keywords")
    args = parser.parse_args()
    
    console = Console()
    client = PexelsClient()
    
    if not client.api_key:
        console.print("[red]Error: PEXELS_API_KEY no configurada[/red]")
        console.print("Configura la variable en tu archivo .env")
        return
    
    try:
        if args.random:
            console.print(f"[cyan]Obteniendo fondo aleatorio para: {args.random}[/cyan]")
            keywords = args.random.split()
            media_type = "photo" if args.photos else "video"
            
            path = client.get_random_background(keywords, media_type)
            
            if path:
                console.print(f"[green]✓ Descargado: {path}[/green]")
            else:
                console.print("[red]✗ No se pudo obtener fondo[/red]")
            return
        
        if args.search:
            console.print(f"[cyan]Buscando: {args.search}[/cyan]")
            
            if args.photos:
                results = client.search_photos(args.search)
            else:
                results = client.search_videos(args.search)
            
            if results:
                table = Table(title="Resultados")
                table.add_column("ID", style="cyan")
                table.add_column("Dimensiones", style="yellow")
                table.add_column("URL", style="blue", max_width=40)
                
                for item in results[:5]:
                    if args.photos:
                        dims = f"{item.get('width', 0)}x{item.get('height', 0)}"
                        url = item.get("url", "")[:40]
                    else:
                        dims = f"{item.get('width', 0)}x{item.get('height', 0)}"
                        url = item.get("url", "")[:40]
                    
                    table.add_row(str(item.get("id")), dims, url)
                
                console.print(table)
                
                if args.download and results:
                    console.print("\n[cyan]Descargando primer resultado...[/cyan]")
                    if args.photos:
                        path = client.download_photo(results[0])
                    else:
                        path = client.download_video(results[0])
                    
                    if path:
                        console.print(f"[green]✓ Descargado: {path}[/green]")
            else:
                console.print("[yellow]No se encontraron resultados[/yellow]")
    finally:
        client.close()


if __name__ == "__main__":
    main()
