"""
Cliente Pexels V3 - Infraestructura
Implementación robusta con soporte para descargas en lote y mapeo de escenas.
"""
import os
import logging
import httpx
from pathlib import Path
from typing import List, Dict, Optional
from tenacity import retry, stop_after_attempt, wait_exponential

from ..domain.models import Scene
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

class PexelsClient:
    """
    Cliente para interactuar con la API de Pexels.
    Diseñado para procesar lotes de escenas eficientemente.
    """
    
    BASE_URL = "https://api.pexels.com"
    
    def __init__(self, assets_dir: str = "./assets"):
        self.assets_dir = Path(assets_dir)
        self.assets_dir.mkdir(parents=True, exist_ok=True)
        
        self.api_key = os.getenv("PEXELS_API_KEY")
        if not self.api_key:
            logger.warning("🚫 PEXELS_API_KEY no encontrada. Las descargas fallarán.")
            
        self.client = httpx.Client(
            headers={"Authorization": self.api_key} if self.api_key else {},
            timeout=30.0
        )

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    def search_video(self, query: str) -> Optional[Dict]:
        """Busca UN video vertical para una query dada."""
        try:
            response = self.client.get(
                f"{self.BASE_URL}/videos/search",
                params={
                    "query": query,
                    "orientation": "portrait",
                    "per_page": 5, # Pedimos varios para poder elegir mejor calidad
                    "size": "medium"
                }
            )
            response.raise_for_status()
            data = response.json()
            videos = data.get("videos", [])
            
            if not videos:
                return None
            
            # Estrategia de selección: El primer HD que sea realmente vertical
            for video in videos:
                # Filtrar solo archivos de video válidos y verticales
                files = video.get("video_files", [])
                valid_files = [
                    f for f in files 
                    if f.get("height", 0) > f.get("width", 0) and f.get("height", 0) >= 720
                ]
                
                if valid_files:
                    # Retornamos el objeto video, y adjuntamos el archivo seleccionado
                    video["_selected_file"] = max(valid_files, key=lambda x: x["height"])
                    return video
            
            # Fallback: devolver el primer resultado sea cual sea
            return videos[0]
            
        except httpx.HTTPError as e:
            logger.error(f"Error HTTP buscando '{query}': {e}")
            raise e

    def download_scenes(self, scenes: List[Scene]) -> Dict[int, str]:
        """
        Procesa una lista de escenas, busca y descarga sus assets.
        
        Returns:
            Dict[scene_id, file_path]
        """
        results = {}
        
        print(f"📥 Iniciando descarga de assets para {len(scenes)} escenas...")
        
        for scene in scenes:
            keywords = " ".join(scene.visual_cue.keywords[:3])
            print(f"  🔍 Escena {scene.id}: Buscando '{keywords}'...")
            
            video_data = self.search_video(keywords)
            
            if not video_data:
                print(f"  ⚠️ No se encontró video para '{keywords}', usando fallback...")
                # Fallback: buscar algo genérico o abstracto
                video_data = self.search_video("abstract blurred background")
            
            if video_data:
                # Descargar
                file_info = video_data.get("_selected_file") or video_data.get("video_files", [{}])[0]
                link = file_info.get("link")
                
                if link:
                    filename = f"scene_{scene.id}_{video_data['id']}.mp4"
                    path = self._download_file(link, filename)
                    if path:
                        results[scene.id] = str(path)
                        scene.video_path = str(path) # Actualizar modelo
                        print(f"  ✅ Descargado: {filename}")
        
        return results

    def _download_file(self, url: str, filename: str) -> Optional[Path]:
        """Descarga un archivo a disco."""
        target_path = self.assets_dir / filename
        
        # Cache simple: si existe, no descargar
        if target_path.exists() and target_path.stat().st_size > 0:
            return target_path
            
        try:
            with self.client.stream("GET", url) as response:
                response.raise_for_status()
                with open(target_path, "wb") as f:
                    for chunk in response.iter_bytes():
                        f.write(chunk)
            return target_path
        except Exception as e:
            logger.error(f"Error descargando {url}: {e}")
            return None
            
    def close(self):
        self.client.close()
