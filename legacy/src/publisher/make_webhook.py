"""
Make.com Webhook Client - Envía datos de video a Make.com para publicación.

Envía un POST con:
- URL pública del video
- Metadata (título, descripción, hashtags)
- Destinos (facebook, youtube)
"""

import json
import logging
import os
from datetime import datetime
from typing import Optional
import requests

from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)


class MakeWebhookClient:
    """Cliente para enviar datos a webhooks de Make.com."""
    
    def __init__(
        self,
        webhook_url: Optional[str] = None,
        secret: Optional[str] = None,
        timeout: int = 30
    ):
        """
        Inicializa el cliente de webhook.
        
        Args:
            webhook_url: URL del webhook de Make.com
            secret: Secret opcional para validación
            timeout: Timeout de requests en segundos
        """
        self.webhook_url = webhook_url or os.getenv("MAKE_WEBHOOK_URL", "")
        self.secret = secret or os.getenv("MAKE_WEBHOOK_SECRET", "")
        self.timeout = timeout
        
        if not self.webhook_url:
            logger.warning(
                "MAKE_WEBHOOK_URL no configurada. "
                "Configúrala en .env para habilitar publicación."
            )
    
    def is_configured(self) -> bool:
        """Verifica si el webhook está configurado."""
        return bool(self.webhook_url)
    
    def publish(
        self,
        video_url: str,
        title: str,
        description: str,
        hashtags: list[str],
        destinations: list[str],
        duration: Optional[float] = None,
        extra_metadata: Optional[dict] = None
    ) -> dict:
        """
        Envía los datos del video al webhook de Make.com.
        
        Args:
            video_url: URL pública del video (Google Drive)
            title: Título del video
            description: Descripción completa para redes
            hashtags: Lista de hashtags
            destinations: Lista de destinos ['facebook', 'youtube']
            duration: Duración del video en segundos
            extra_metadata: Metadata adicional opcional
            
        Returns:
            Dict con 'success', 'response', y 'error' si aplica
        """
        if not self.is_configured():
            return {
                "success": False,
                "error": "Webhook no configurado. Configura MAKE_WEBHOOK_URL en .env"
            }
        
        # Construir payload
        payload = {
            "video_url": video_url,
            "title": title,
            "description": description,
            "hashtags": " ".join([f"#{h}" if not h.startswith("#") else h for h in hashtags]),
            "hashtags_list": hashtags,
            "destinations": destinations,
            "duration": duration,
            "created_at": datetime.now().isoformat(),
            "metadata": extra_metadata or {}
        }
        
        # Headers
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "CreadorVideos/1.0"
        }
        
        if self.secret:
            headers["X-Webhook-Secret"] = self.secret
        
        logger.info(f"Enviando a Make.com: {self.webhook_url[:50]}...")
        logger.debug(f"Payload: {json.dumps(payload, indent=2)}")
        
        try:
            response = requests.post(
                self.webhook_url,
                json=payload,
                headers=headers,
                timeout=self.timeout
            )
            
            response.raise_for_status()
            
            result = {
                "success": True,
                "status_code": response.status_code,
                "response": response.text[:500] if response.text else "OK"
            }
            
            logger.info(f"Webhook enviado exitosamente: {response.status_code}")
            return result
            
        except requests.exceptions.Timeout:
            error_msg = f"Timeout después de {self.timeout}s"
            logger.error(error_msg)
            return {"success": False, "error": error_msg}
            
        except requests.exceptions.HTTPError as e:
            error_msg = f"HTTP Error: {e.response.status_code} - {e.response.text[:200]}"
            logger.error(error_msg)
            return {"success": False, "error": error_msg}
            
        except requests.exceptions.RequestException as e:
            error_msg = f"Error de conexión: {str(e)}"
            logger.error(error_msg)
            return {"success": False, "error": error_msg}
    
    def publish_from_metadata(
        self,
        video_url: str,
        script: dict,
        destinations: Optional[list[str]] = None
    ) -> dict:
        """
        Publica usando el dict de script generado por el pipeline.
        
        Args:
            video_url: URL pública del video
            script: Dict del guión con title, keywords, narration_text, etc.
            destinations: Lista de destinos (default: desde .env)
            
        Returns:
            Dict con resultado de la publicación
        """
        # Obtener destinos de .env si no se especifican
        if destinations is None:
            dest_env = os.getenv("PUBLISH_DESTINATIONS", "facebook,youtube")
            destinations = [d.strip() for d in dest_env.split(",")]
        
        # Extraer datos del script
        title = script.get("title", "Video de Bienestar")
        keywords = script.get("keywords", ["bienestar", "salud"])
        narration = script.get("narration_text", "")
        hooks = script.get("hooks_alternativos", [])
        
        # Construir descripción
        first_hook = hooks[0] if hooks else title
        if isinstance(first_hook, dict):
            first_hook = first_hook.get("text", title)
        
        description = f"""{first_hook}

{narration[:300]}{'...' if len(narration) > 300 else ''}

✨ Si este contenido te ayudó, ¡dale like y comparte!
🔔 Sígueme para más tips de bienestar diario."""
        
        # Duration si está disponible
        duration = script.get("_duration")
        
        return self.publish(
            video_url=video_url,
            title=title,
            description=description,
            hashtags=keywords[:10],  # Limitar hashtags
            destinations=destinations,
            duration=duration,
            extra_metadata={
                "script_id": script.get("_id"),
                "source_url": script.get("source_url", ""),
                "hooks": hooks[:3]  # Incluir hooks alternativos
            }
        )
    
    def test_connection(self) -> dict:
        """
        Envía un ping de prueba al webhook.
        
        Returns:
            Dict con resultado del test
        """
        if not self.is_configured():
            return {
                "success": False,
                "error": "Webhook no configurado"
            }
        
        payload = {
            "test": True,
            "timestamp": datetime.now().isoformat(),
            "message": "Test de conexión desde Creador de Videos"
        }
        
        try:
            response = requests.post(
                self.webhook_url,
                json=payload,
                timeout=10
            )
            
            return {
                "success": response.status_code < 400,
                "status_code": response.status_code,
                "response": response.text[:200]
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }


# CLI para testing
if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Make.com Webhook Client")
    parser.add_argument("--test", action="store_true", help="Test de conexión")
    parser.add_argument("--url", help="URL del video para publicar")
    parser.add_argument("--title", default="Test Video", help="Título del video")
    
    args = parser.parse_args()
    
    client = MakeWebhookClient()
    
    if args.test:
        if not client.is_configured():
            print("✗ Webhook no configurado. Configura MAKE_WEBHOOK_URL en .env")
        else:
            print(f"Testing webhook: {client.webhook_url[:50]}...")
            result = client.test_connection()
            if result["success"]:
                print(f"✓ Conexión exitosa: {result.get('status_code')}")
            else:
                print(f"✗ Error: {result.get('error')}")
    
    elif args.url:
        result = client.publish(
            video_url=args.url,
            title=args.title,
            description="Test description",
            hashtags=["test", "video"],
            destinations=["facebook", "youtube"]
        )
        
        if result["success"]:
            print(f"✓ Publicado exitosamente")
        else:
            print(f"✗ Error: {result.get('error')}")
