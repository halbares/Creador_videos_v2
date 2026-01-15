"""
Cliente para OpenRouter API.
Compatible con el SDK de OpenAI.
"""

import json
import logging
import os
import re
from typing import Optional

import yaml
from dotenv import load_dotenv
from openai import OpenAI

from ..utils.backoff import with_retry, global_rate_limiter, APIError
from ..utils.cache import ContentCache

load_dotenv()
logger = logging.getLogger(__name__)


class OpenRouterClient:
    """Cliente para generar guiones usando OpenRouter."""
    
    def __init__(
        self,
        prompts_path: str = "./config/prompts.yaml",
        cache: Optional[ContentCache] = None
    ):
        """
        Inicializa el cliente de OpenRouter.
        
        Args:
            prompts_path: Ruta al archivo de prompts
            cache: Instancia de cache
        """
        self.prompts = self._load_prompts(prompts_path)
        self.cache = cache or ContentCache()
        self.rate_limiter = global_rate_limiter
        
        # Configurar cliente
        self.api_key = os.getenv("OPENROUTER_API_KEY")
        self.model_primary = os.getenv("LLM_MODEL_PRIMARY", "qwen/qwen3-235b-a22b-2507")
        self.model_backup = os.getenv("LLM_MODEL_BACKUP", "meta-llama/llama-4-scout")
        
        if not self.api_key:
            logger.warning("OPENROUTER_API_KEY no configurada")
            self.client = None
        else:
            self.client = OpenAI(
                base_url="https://openrouter.ai/api/v1",
                api_key=self.api_key,
            )
    
    def _load_prompts(self, path: str) -> dict:
        """Carga los prompts desde YAML."""
        try:
            with open(path, "r", encoding="utf-8") as f:
                return yaml.safe_load(f)
        except FileNotFoundError:
            logger.warning(f"Archivo de prompts no encontrado: {path}")
            return {}
    
    def _extract_json(self, text: str) -> Optional[dict]:
        """
        Extrae JSON de la respuesta del LLM.
        Maneja casos donde el JSON está envuelto en markdown o texto.
        """
        # Intentar parsear directamente
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass
        
        # Buscar JSON en bloques de código
        json_patterns = [
            r"```json\s*([\s\S]*?)\s*```",
            r"```\s*([\s\S]*?)\s*```",
            r"\{[\s\S]*\}",
        ]
        
        for pattern in json_patterns:
            matches = re.findall(pattern, text)
            for match in matches:
                try:
                    # Limpiar el match
                    clean = match.strip()
                    if not clean.startswith("{"):
                        continue
                    return json.loads(clean)
                except json.JSONDecodeError:
                    continue
        
        logger.error("No se pudo extraer JSON de la respuesta")
        return None
    
    @with_retry(max_attempts=3, min_wait=2.0, max_wait=60.0)
    def _call_llm(
        self,
        messages: list[dict],
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 2000
    ) -> Optional[str]:
        """
        Llama al LLM con los mensajes dados.
        
        Args:
            messages: Lista de mensajes (formato OpenAI)
            model: Modelo a usar (usa primary por defecto)
            temperature: Temperatura de generación
            max_tokens: Máximo de tokens a generar
            
        Returns:
            Respuesta del LLM o None si hay error
        """
        if not self.client:
            raise APIError("Cliente OpenRouter no configurado")
        
        self.rate_limiter.wait_if_needed("openrouter")
        
        model = model or self.model_primary
        
        try:
            response = self.client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                extra_headers={
                    "HTTP-Referer": "https://github.com/creador-videos",
                    "X-Title": "Creador Videos Virales"
                }
            )
            
            return response.choices[0].message.content
            
        except Exception as e:
            logger.error(f"Error llamando a {model}: {e}")
            raise
    
    def generate_script(
        self,
        source_content: str,
        source_url: str = "",
        use_backup: bool = False
    ) -> Optional[dict]:
        """
        Genera un guión a partir del contenido fuente.
        
        Args:
            source_content: Contenido a transformar en guión
            source_url: URL de la fuente (para referencia)
            use_backup: Si usar el modelo de backup
            
        Returns:
            Dict con el guión generado o None si hay error
        """
        if not self.client:
            logger.error("OpenRouter no está configurado")
            return None
        
        # Preparar el prompt
        system_prompt = self.prompts.get("system_prompt", "")
        script_template = self.prompts.get("script_template", "")
        
        if not script_template:
            logger.error("Template de guión no encontrado")
            return None
        
        # Rellenar el template
        user_prompt = script_template.format(
            source_content=source_content[:3000],  # Limitar longitud
            source_url=source_url
        )
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        
        model = self.model_backup if use_backup else self.model_primary
        
        try:
            response = self._call_llm(messages, model=model)
            
            if not response:
                return None
            
            # Extraer JSON
            script_data = self._extract_json(response)
            
            if not script_data:
                # Intentar con modelo backup si el primario falló
                if not use_backup:
                    logger.warning("Intentando con modelo backup...")
                    return self.generate_script(source_content, source_url, use_backup=True)
                return None
            
            # Agregar metadata
            script_data["source_url"] = source_url
            script_data["model_used"] = model
            
            return script_data
            
        except Exception as e:
            logger.error(f"Error generando guión: {e}")
            
            # Intentar con backup
            if not use_backup:
                logger.warning("Intentando con modelo backup...")
                return self.generate_script(source_content, source_url, use_backup=True)
            
            return None
    
    def generate_from_cached_content(self, limit: int = 1) -> list[dict]:
        """
        Genera guiones a partir del contenido en cache.
        
        Args:
            limit: Número máximo de guiones a generar
            
        Returns:
            Lista de guiones generados
        """
        pending = self.cache.get_pending_content()[:limit]
        scripts = []
        
        for item in pending:
            # Construir contenido
            content_parts = []
            
            if item.get("title"):
                content_parts.append(f"Título: {item['title']}")
            
            if item.get("summary"):
                content_parts.append(f"Resumen: {item['summary']}")
            elif item.get("content"):
                content_parts.append(f"Contenido: {item['content']}")
            elif item.get("description"):
                content_parts.append(f"Descripción: {item['description']}")
            
            # Agregar comentarios de Reddit si existen
            if item.get("top_comments"):
                comments = "\n".join(item["top_comments"][:3])
                content_parts.append(f"Comentarios destacados:\n{comments}")
            
            content = "\n\n".join(content_parts)
            url = item.get("url", "")
            
            script = self.generate_script(content, url)
            
            if script:
                # Generar ID único
                import hashlib
                script_id = hashlib.sha256(url.encode()).hexdigest()[:12]
                
                # Guardar en cache
                self.cache.store_script(script_id, script)
                
                # Marcar contenido como procesado
                source_type = item.get("source_type", "unknown")
                self.cache.mark_processed(source_type, url)
                
                scripts.append(script)
                logger.info(f"Guión generado: {script.get('title', 'Sin título')}")
        
        return scripts


def main():
    """Función principal para testing."""
    import argparse
    from rich.console import Console
    from rich.panel import Panel
    from rich.json import JSON
    
    parser = argparse.ArgumentParser(description="OpenRouter LLM Client")
    parser.add_argument("--test", action="store_true", help="Modo de prueba")
    parser.add_argument("--text", type=str, help="Texto a transformar en guión")
    parser.add_argument("--from-cache", action="store_true", help="Generar desde cache")
    parser.add_argument("--list", action="store_true", help="Listar guiones generados")
    args = parser.parse_args()
    
    console = Console()
    client = OpenRouterClient()
    
    if not client.client:
        console.print("[red]Error: OPENROUTER_API_KEY no configurada[/red]")
        console.print("Configura la variable en tu archivo .env")
        return
    
    if args.list:
        scripts = client.cache.get_scripts_list()
        if scripts:
            for s in scripts:
                console.print(f"[cyan]{s['id']}[/cyan]: {s['title']} ({s['created_at'][:10]})")
        else:
            console.print("[yellow]No hay guiones guardados[/yellow]")
        return
    
    if args.from_cache:
        console.print("[cyan]Generando guiones desde cache...[/cyan]")
        scripts = client.generate_from_cached_content(limit=1)
        
        if scripts:
            for script in scripts:
                console.print(Panel(JSON(json.dumps(script, indent=2, ensure_ascii=False)), 
                                   title=script.get("title", "Guión")))
        else:
            console.print("[yellow]No se generaron guiones. ¿Hay contenido en cache?[/yellow]")
        return
    
    if args.text:
        console.print("[cyan]Generando guión...[/cyan]")
        script = client.generate_script(args.text, "test://input")
        
        if script:
            console.print(Panel(JSON(json.dumps(script, indent=2, ensure_ascii=False)),
                               title=script.get("title", "Guión")))
        else:
            console.print("[red]Error generando guión[/red]")
        return
    
    # Test básico
    console.print("[cyan]Test de conexión con OpenRouter...[/cyan]")
    test_text = """
    Un estudio reciente demuestra que dormir 7-8 horas mejora la productividad en un 40%.
    Los participantes que mantuvieron un horario regular de sueño reportaron mejor concentración
    y menos estrés durante el día.
    """
    
    script = client.generate_script(test_text, "https://example.com/sleep-study")
    
    if script:
        console.print("[green]✓ Conexión exitosa[/green]")
        console.print(Panel(JSON(json.dumps(script, indent=2, ensure_ascii=False)),
                           title="Guión de prueba"))
    else:
        console.print("[red]✗ Error en la conexión[/red]")


if __name__ == "__main__":
    main()
