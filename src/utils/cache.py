"""
Sistema de cache en disco para contenido scrapeado.
Evita re-procesar contenido ya visto y reduce llamadas a APIs.
"""

import hashlib
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Optional

from diskcache import Cache


class ContentCache:
    """Cache persistente en disco para contenido."""
    
    def __init__(self, cache_dir: str = "./cache", default_ttl_hours: int = 24):
        """
        Inicializa el cache.
        
        Args:
            cache_dir: Directorio para almacenar el cache
            default_ttl_hours: Tiempo de vida por defecto en horas
        """
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.cache = Cache(str(self.cache_dir))
        self.default_ttl = timedelta(hours=default_ttl_hours)
    
    def _generate_key(self, content: str) -> str:
        """Genera una clave única basada en el contenido."""
        return hashlib.sha256(content.encode()).hexdigest()[:16]
    
    def get(self, key: str) -> Optional[Any]:
        """
        Obtiene un valor del cache.
        
        Args:
            key: Clave a buscar
            
        Returns:
            Valor almacenado o None si no existe/expiró
        """
        return self.cache.get(key)
    
    def set(self, key: str, value: Any, ttl_hours: Optional[int] = None) -> None:
        """
        Almacena un valor en el cache.
        
        Args:
            key: Clave para almacenar
            value: Valor a almacenar
            ttl_hours: Tiempo de vida en horas (usa default si no se especifica)
        """
        ttl = timedelta(hours=ttl_hours) if ttl_hours else self.default_ttl
        expire_time = ttl.total_seconds()
        self.cache.set(key, value, expire=expire_time)
    
    def exists(self, key: str) -> bool:
        """Verifica si una clave existe en el cache."""
        return key in self.cache
    
    def is_content_seen(self, content: str) -> bool:
        """
        Verifica si un contenido ya fue procesado.
        
        Args:
            content: Texto del contenido
            
        Returns:
            True si ya fue visto, False si es nuevo
        """
        key = self._generate_key(content)
        return self.exists(f"seen:{key}")
    
    def mark_content_seen(self, content: str, metadata: Optional[dict] = None) -> str:
        """
        Marca un contenido como procesado.
        
        Args:
            content: Texto del contenido
            metadata: Metadata adicional a almacenar
            
        Returns:
            Clave generada para el contenido
        """
        key = self._generate_key(content)
        data = {
            "seen_at": datetime.now().isoformat(),
            "content_preview": content[:200],
            "metadata": metadata or {}
        }
        self.set(f"seen:{key}", data)
        return key
    
    def store_scraped_content(self, source: str, items: list[dict]) -> int:
        """
        Almacena contenido scrapeado.
        
        Args:
            source: Nombre de la fuente (rss, reddit, youtube, etc.)
            items: Lista de items scrapeados
            
        Returns:
            Número de items nuevos almacenados
        """
        existing = self.get(f"scraped:{source}") or []
        existing_urls = {item.get("url") for item in existing}
        
        new_items = []
        for item in items:
            url = item.get("url", "")
            if url and url not in existing_urls:
                item["scraped_at"] = datetime.now().isoformat()
                new_items.append(item)
        
        if new_items:
            all_items = existing + new_items
            # Mantener solo los últimos 100 items por fuente
            all_items = all_items[-100:]
            self.set(f"scraped:{source}", all_items, ttl_hours=48)
        
        return len(new_items)
    
    def get_pending_count(self, source: Optional[str] = None) -> int:
        """Obtiene la cantidad de items pendientes."""
        return len(self.get_pending_content(source))
    
    def get_pending_content(self, source: Optional[str] = None) -> list[dict]:
        """
        Obtiene contenido pendiente de procesar.
        
        Args:
            source: Filtrar por fuente específica (opcional)
            
        Returns:
            Lista de items pendientes
        """
        if source:
            items = self.get(f"scraped:{source}") or []
            # Agregar campo source a cada item
            for item in items:
                item["source"] = source
            return [i for i in items if not i.get("processed")]
        
        # Obtener de todas las fuentes
        all_items = []
        for src in ["rss", "reddit", "youtube", "blogs"]:
            items = self.get(f"scraped:{src}") or []
            # Agregar campo source a cada item
            for item in items:
                item["source"] = src
            all_items.extend([i for i in items if not i.get("processed")])
        
        return all_items
    
    def mark_processed(self, source: str, url: str) -> None:
        """Marca un item como procesado."""
        items = self.get(f"scraped:{source}") or []
        for item in items:
            if item.get("url") == url:
                item["processed"] = True
                item["processed_at"] = datetime.now().isoformat()
        self.set(f"scraped:{source}", items, ttl_hours=48)
    
    def mark_processed_by_url(self, url: str) -> bool:
        """
        Marca un item como procesado buscando en todas las fuentes.
        
        Args:
            url: URL del contenido a marcar
            
        Returns:
            True si se encontró y marcó, False si no se encontró
        """
        for src in ["rss", "reddit", "youtube", "blogs"]:
            items = self.get(f"scraped:{src}") or []
            found = False
            for item in items:
                if item.get("url") == url:
                    item["processed"] = True
                    item["processed_at"] = datetime.now().isoformat()
                    found = True
            if found:
                self.set(f"scraped:{src}", items, ttl_hours=48)
                return True
        return False
    
    def store_script(self, script_id: str, script_data: dict) -> None:
        """
        Almacena un guión generado.
        
        Args:
            script_id: ID único del guión
            script_data: Datos del guión (JSON del LLM)
        """
        script_data["created_at"] = datetime.now().isoformat()
        self.set(f"script:{script_id}", script_data, ttl_hours=168)  # 1 semana
        
        # Mantener índice de guiones
        scripts_index = self.get("scripts:index") or []
        scripts_index.append({
            "id": script_id,
            "title": script_data.get("title", "Sin título"),
            "created_at": script_data["created_at"]
        })
        scripts_index = scripts_index[-50:]  # Mantener últimos 50
        self.set("scripts:index", scripts_index, ttl_hours=168)
    
    def get_scripts_list(self) -> list[dict]:
        """Obtiene la lista de guiones almacenados."""
        return self.get("scripts:index") or []
    
    def get_script(self, script_id: str) -> Optional[dict]:
        """Obtiene un guión por su ID."""
        return self.get(f"script:{script_id}")
    
    def clear_all(self) -> None:
        """Limpia todo el cache."""
        self.cache.clear()
    
    def get_stats(self) -> dict:
        """Obtiene estadísticas del cache."""
        return {
            "size_bytes": self.cache.volume(),
            "items_count": len(self.cache),
            "directory": str(self.cache_dir)
        }
    
    def close(self) -> None:
        """Cierra la conexión al cache."""
        self.cache.close()
