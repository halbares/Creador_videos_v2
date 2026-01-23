"""
Buscador y descargador de stickers desde Pexels.
Incluye remoción de fondo con rembg.
"""

import logging
import os
from pathlib import Path
from typing import Optional
import httpx
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)


class StickerFetcher:
    """Descarga imágenes de Pexels y las convierte en stickers."""
    
    def __init__(self, cache_dir: str = "./cache/stickers"):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.api_key = os.getenv("PEXELS_API_KEY")
        self.base_url = "https://api.pexels.com/v1"
        
    def fetch_sticker(
        self, 
        keyword: str, 
        prefer_icon: bool = True
    ) -> Optional[str]:
        """
        Busca y descarga una imagen, luego le quita el fondo.
        
        Args:
            keyword: Término de búsqueda
            prefer_icon: Si preferir resultados más iconográficos
            
        Returns:
            Ruta al PNG con fondo transparente o None
        """
        # Modificar búsqueda para preferir iconos
        search_term = keyword
        if prefer_icon:
            search_term = f"{keyword} icon minimal"
        
        # Buscar imagen
        image_path = self._search_and_download(search_term)
        
        # Si no encuentra con icon, buscar sin modificador
        if not image_path and prefer_icon:
            image_path = self._search_and_download(keyword)
        
        if not image_path:
            logger.warning(f"No se encontró imagen para: {keyword}")
            return None
        
        # Quitar fondo
        sticker_path = self._remove_background(image_path)
        return sticker_path
    
    def _search_and_download(self, query: str) -> Optional[str]:
        """Busca en Pexels y descarga la primera imagen."""
        if not self.api_key:
            logger.error("PEXELS_API_KEY no configurada")
            return None
        
        try:
            headers = {"Authorization": self.api_key}
            params = {
                "query": query,
                "per_page": 5,
                "size": "medium",
            }
            
            with httpx.Client(timeout=30) as client:
                response = client.get(
                    f"{self.base_url}/search",
                    headers=headers,
                    params=params
                )
                response.raise_for_status()
                data = response.json()
            
            photos = data.get("photos", [])
            if not photos:
                return None
            
            # Tomar la primera foto
            photo = photos[0]
            photo_url = photo["src"]["medium"]
            photo_id = photo["id"]
            
            # Descargar
            output_path = self.cache_dir / f"raw_{photo_id}.jpg"
            
            if output_path.exists():
                return str(output_path)
            
            with httpx.Client(timeout=60) as client:
                img_response = client.get(photo_url)
                img_response.raise_for_status()
                
                with open(output_path, "wb") as f:
                    f.write(img_response.content)
            
            logger.info(f"Imagen descargada: {output_path}")
            return str(output_path)
            
        except Exception as e:
            logger.error(f"Error buscando imagen: {e}")
            return None
    
    def _remove_background(self, image_path: str) -> Optional[str]:
        """Quita el fondo de una imagen usando rembg."""
        try:
            from rembg import remove
            from PIL import Image
            
            input_path = Path(image_path)
            output_path = self.cache_dir / f"sticker_{input_path.stem}.png"
            
            if output_path.exists():
                return str(output_path)
            
            with Image.open(input_path) as img:
                output = remove(img)
                output.save(output_path, "PNG")
            
            logger.info(f"Fondo removido: {output_path}")
            return str(output_path)
            
        except ImportError:
            logger.error("rembg no instalado. Ejecuta: pip install rembg")
            # Retornar imagen original si no hay rembg
            return image_path
        except Exception as e:
            logger.error(f"Error removiendo fondo: {e}")
            return image_path
    
    def fetch_multiple(
        self, 
        sticker_specs: list[dict]
    ) -> list[dict]:
        """
        Descarga múltiples stickers.
        
        Args:
            sticker_specs: Lista de dicts con keyword, start, end
            
        Returns:
            Lista de dicts con path agregado
        """
        results = []
        
        for spec in sticker_specs:
            keyword = spec.get("keyword", "")
            path = self.fetch_sticker(keyword, prefer_icon=True)
            
            if path:
                spec["path"] = path
                results.append(spec)
        
        return results
