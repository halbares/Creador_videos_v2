"""
Retry Queue - Cola persistente para reintentar publicaciones fallidas.

Guarda en JSON los videos que fallaron al publicar para reintentar después.
"""

import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Optional
from dataclasses import dataclass, asdict

from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)


@dataclass
class QueueItem:
    """Item en la cola de reintentos."""
    video_path: str
    remote_path: Optional[str]
    video_url: Optional[str]
    script: dict
    destinations: list[str]
    error: str
    attempts: int
    created_at: str
    last_attempt: str
    
    def to_dict(self) -> dict:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: dict) -> "QueueItem":
        return cls(**data)


class RetryQueue:
    """Cola persistente para publicaciones fallidas."""
    
    def __init__(self, cache_dir: str = "./cache"):
        """
        Inicializa la cola de reintentos.
        
        Args:
            cache_dir: Directorio donde guardar la cola
        """
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.queue_file = self.cache_dir / "publish_queue.json"
        
        # Cargar cola existente
        self._queue: list[QueueItem] = self._load()
    
    def _load(self) -> list[QueueItem]:
        """Carga la cola desde el archivo JSON."""
        if not self.queue_file.exists():
            return []
        
        try:
            with open(self.queue_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                return [QueueItem.from_dict(item) for item in data]
        except (json.JSONDecodeError, KeyError) as e:
            logger.error(f"Error cargando cola: {e}")
            return []
    
    def _save(self) -> None:
        """Guarda la cola en el archivo JSON."""
        data = [item.to_dict() for item in self._queue]
        
        with open(self.queue_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    
    def add(
        self,
        video_path: str,
        script: dict,
        error: str,
        remote_path: Optional[str] = None,
        video_url: Optional[str] = None,
        destinations: Optional[list[str]] = None
    ) -> None:
        """
        Agrega un video fallido a la cola.
        
        Args:
            video_path: Ruta local del video
            script: Dict del guión
            error: Mensaje de error
            remote_path: Ruta en Google Drive si se logró subir
            video_url: URL pública si se logró obtener
            destinations: Lista de destinos
        """
        if destinations is None:
            dest_env = os.getenv("PUBLISH_DESTINATIONS", "facebook,youtube")
            destinations = [d.strip() for d in dest_env.split(",")]
        
        now = datetime.now().isoformat()
        
        item = QueueItem(
            video_path=video_path,
            remote_path=remote_path,
            video_url=video_url,
            script=script,
            destinations=destinations,
            error=error,
            attempts=1,
            created_at=now,
            last_attempt=now
        )
        
        self._queue.append(item)
        self._save()
        
        logger.info(f"Video agregado a cola de reintentos: {video_path}")
    
    def get_pending(self) -> list[QueueItem]:
        """Retorna todos los items pendientes."""
        return self._queue.copy()
    
    def get_count(self) -> int:
        """Retorna la cantidad de items en la cola."""
        return len(self._queue)
    
    def update_attempt(self, index: int, new_error: Optional[str] = None) -> None:
        """
        Actualiza un intento de publicación.
        
        Args:
            index: Índice del item en la cola
            new_error: Nuevo mensaje de error si sigue fallando
        """
        if 0 <= index < len(self._queue):
            item = self._queue[index]
            item.attempts += 1
            item.last_attempt = datetime.now().isoformat()
            
            if new_error:
                item.error = new_error
            
            self._save()
    
    def remove(self, index: int) -> Optional[QueueItem]:
        """
        Elimina un item de la cola (publicación exitosa).
        
        Args:
            index: Índice del item a eliminar
            
        Returns:
            El item eliminado o None
        """
        if 0 <= index < len(self._queue):
            item = self._queue.pop(index)
            self._save()
            logger.info(f"Video removido de cola: {item.video_path}")
            return item
        return None
    
    def remove_by_path(self, video_path: str) -> bool:
        """
        Elimina un item por su ruta de video.
        
        Args:
            video_path: Ruta del video
            
        Returns:
            True si se eliminó
        """
        for i, item in enumerate(self._queue):
            if item.video_path == video_path:
                self.remove(i)
                return True
        return False
    
    def clear(self) -> int:
        """
        Limpia toda la cola.
        
        Returns:
            Cantidad de items eliminados
        """
        count = len(self._queue)
        self._queue = []
        self._save()
        logger.info(f"Cola limpiada: {count} items eliminados")
        return count
    
    def get_summary(self) -> dict:
        """Retorna un resumen de la cola."""
        if not self._queue:
            return {"count": 0, "items": []}
        
        return {
            "count": len(self._queue),
            "oldest": self._queue[0].created_at if self._queue else None,
            "total_attempts": sum(item.attempts for item in self._queue),
            "items": [
                {
                    "video": Path(item.video_path).name,
                    "error": item.error[:50],
                    "attempts": item.attempts,
                    "has_url": item.video_url is not None
                }
                for item in self._queue
            ]
        }


# CLI para testing
if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Retry Queue Manager")
    parser.add_argument("--list", action="store_true", help="Listar cola")
    parser.add_argument("--clear", action="store_true", help="Limpiar cola")
    parser.add_argument("--count", action="store_true", help="Mostrar cantidad")
    
    args = parser.parse_args()
    
    queue = RetryQueue()
    
    if args.list:
        summary = queue.get_summary()
        print(f"\n📋 Cola de reintentos: {summary['count']} items\n")
        
        for i, item in enumerate(summary.get("items", [])):
            print(f"  {i+1}. {item['video']}")
            print(f"     Error: {item['error']}...")
            print(f"     Intentos: {item['attempts']}")
            print(f"     URL: {'✓' if item['has_url'] else '✗'}")
            print()
    
    elif args.clear:
        count = queue.clear()
        print(f"✓ Cola limpiada: {count} items eliminados")
    
    elif args.count:
        print(f"Items en cola: {queue.get_count()}")
