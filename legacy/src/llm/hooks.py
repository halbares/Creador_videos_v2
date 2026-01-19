"""
Generador de hooks alternativos.
Crea variaciones del hook principal para pruebas A/B.
"""

import json
import logging
import os
from typing import Optional

import yaml
from dotenv import load_dotenv
from openai import OpenAI

from ..utils.backoff import with_retry, global_rate_limiter

load_dotenv()
logger = logging.getLogger(__name__)


class HooksGenerator:
    """Generador de hooks alternativos para videos."""
    
    def __init__(self, prompts_path: str = "./config/prompts.yaml"):
        """
        Inicializa el generador de hooks.
        
        Args:
            prompts_path: Ruta al archivo de prompts
        """
        self.prompts = self._load_prompts(prompts_path)
        self.rate_limiter = global_rate_limiter
        
        api_key = os.getenv("OPENROUTER_API_KEY")
        self.model = os.getenv("LLM_MODEL_BACKUP", "meta-llama/llama-4-scout")
        
        if api_key:
            self.client = OpenAI(
                base_url="https://openrouter.ai/api/v1",
                api_key=api_key,
            )
        else:
            self.client = None
    
    def _load_prompts(self, path: str) -> dict:
        """Carga los prompts desde YAML."""
        try:
            with open(path, "r", encoding="utf-8") as f:
                return yaml.safe_load(f)
        except FileNotFoundError:
            return {}
    
    @with_retry(max_attempts=2, min_wait=1.0, max_wait=30.0)
    def generate_hooks(
        self,
        content: str,
        existing_hooks: Optional[list[str]] = None,
        count: int = 3
    ) -> list[dict]:
        """
        Genera hooks alternativos para el contenido.
        
        Args:
            content: Contenido del video (guión o resumen)
            existing_hooks: Hooks existentes para variar
            count: Número de hooks a generar
            
        Returns:
            Lista de dicts con hooks y su emoción asociada
        """
        if not self.client:
            logger.warning("OpenRouter no configurado")
            return self._generate_fallback_hooks(content, count)
        
        self.rate_limiter.wait_if_needed("openrouter")
        
        prompt_template = self.prompts.get("hooks_regeneration", "")
        
        if not prompt_template:
            # Prompt por defecto
            prompt_template = """
            Genera {count} hooks alternativos para un video viral sobre este contenido:
            
            CONTENIDO:
            {content}
            
            Cada hook debe:
            - Durar máximo 3 segundos al leerse
            - Ser impactante e intrigante
            - Generar curiosidad inmediata
            
            RESPONDE EN JSON:
            {{"hooks": [{{"text": "...", "emotion": "sorpresa/curiosidad/miedo/identificación"}}]}}
            """
        
        user_prompt = prompt_template.format(
            content=content[:1500],
            existing_hooks="\n".join(existing_hooks or []),
            count=count
        )
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": user_prompt}],
                temperature=0.9,  # Alta creatividad
                max_tokens=500,
            )
            
            response_text = response.choices[0].message.content
            
            # Extraer JSON
            import re
            json_match = re.search(r"\{[\s\S]*\}", response_text)
            if json_match:
                data = json.loads(json_match.group())
                return data.get("hooks", [])
            
            return self._generate_fallback_hooks(content, count)
            
        except Exception as e:
            logger.error(f"Error generando hooks: {e}")
            return self._generate_fallback_hooks(content, count)
    
    def _generate_fallback_hooks(self, content: str, count: int) -> list[dict]:
        """
        Genera hooks de respaldo sin LLM.
        Usa plantillas y extrae palabras clave del contenido.
        """
        power_words = self.prompts.get("power_words", {})
        
        # Extraer primera frase como base
        first_sentence = content.split(".")[0][:50] if content else "este secreto"
        
        templates = [
            {"text": f"¿Sabías que {first_sentence.lower()}?", "emotion": "curiosidad"},
            {"text": f"Nadie te dice esto sobre {first_sentence.lower()}.", "emotion": "misterio"},
            {"text": f"Esto cambiará tu vida. {first_sentence}.", "emotion": "promesa"},
            {"text": f"El mayor error que cometes con {first_sentence.lower()}.", "emotion": "miedo"},
            {"text": f"Descubre el secreto de {first_sentence.lower()}.", "emotion": "curiosidad"},
        ]
        
        return templates[:count]
    
    def regenerate_for_script(self, script: dict) -> dict:
        """
        Regenera hooks para un guión existente.
        
        Args:
            script: Guión con estructura completa
            
        Returns:
            Guión actualizado con nuevos hooks
        """
        content = script.get("narration_text", "")
        existing = script.get("hooks_alternativos", [])
        
        # Convertir hooks existentes a strings si son dicts
        existing_texts = []
        for h in existing:
            if isinstance(h, dict):
                existing_texts.append(h.get("text", ""))
            else:
                existing_texts.append(str(h))
        
        new_hooks = self.generate_hooks(content, existing_texts, count=3)
        
        # Actualizar guión
        updated = script.copy()
        updated["hooks_alternativos"] = new_hooks
        
        return updated


def main():
    """Función principal para testing."""
    import argparse
    from rich.console import Console
    from rich.table import Table
    
    parser = argparse.ArgumentParser(description="Hooks Generator")
    parser.add_argument("--regenerate", action="store_true", help="Regenerar hooks para guiones")
    parser.add_argument("--text", type=str, help="Generar hooks para texto")
    args = parser.parse_args()
    
    console = Console()
    generator = HooksGenerator()
    
    if args.text:
        console.print(f"[cyan]Generando hooks para: {args.text[:50]}...[/cyan]")
        hooks = generator.generate_hooks(args.text)
        
        table = Table(title="Hooks Generados")
        table.add_column("Hook", style="green")
        table.add_column("Emoción", style="yellow")
        
        for hook in hooks:
            table.add_row(
                hook.get("text", str(hook)),
                hook.get("emotion", "N/A")
            )
        
        console.print(table)
    else:
        # Ejemplo con texto de prueba
        test_content = """
        Dormir bien es esencial para tu salud mental y física.
        Estudios demuestran que 7 horas de sueño mejoran la concentración un 40%.
        """
        
        console.print("[cyan]Generando hooks de ejemplo...[/cyan]")
        hooks = generator.generate_hooks(test_content)
        
        for i, hook in enumerate(hooks, 1):
            console.print(f"[green]{i}.[/green] {hook.get('text', hook)} "
                         f"[dim]({hook.get('emotion', 'N/A')})[/dim]")


if __name__ == "__main__":
    main()
