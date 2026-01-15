"""
Validador de guiones generados por el LLM.
Verifica estructura, formato y reglas de contenido.
"""

import logging
from dataclasses import dataclass
from typing import Optional

import yaml

logger = logging.getLogger(__name__)


@dataclass
class ValidationResult:
    """Resultado de la validación."""
    is_valid: bool
    errors: list[str]
    warnings: list[str]
    
    def __bool__(self):
        return self.is_valid


class ScriptValidator:
    """Validador de guiones generados."""
    
    def __init__(self, prompts_path: str = "./config/prompts.yaml"):
        """
        Inicializa el validador.
        
        Args:
            prompts_path: Ruta al archivo de prompts con reglas de validación
        """
        self.rules = self._load_rules(prompts_path)
    
    def _load_rules(self, path: str) -> dict:
        """Carga las reglas de validación desde YAML."""
        default_rules = {
            "min_narration_length": 200,
            "max_narration_length": 800,
            "min_subtitles": 8,
            "max_subtitle_duration": 4.0,
            "max_words_per_subtitle": 15,
            "required_fields": ["narration_text", "subtitles"]
        }
        
        try:
            with open(path, "r", encoding="utf-8") as f:
                config = yaml.safe_load(f)
                rules = config.get("validation_rules", {})
                return {**default_rules, **rules}
        except FileNotFoundError:
            logger.warning(f"Archivo de reglas no encontrado: {path}")
            return default_rules
    
    def _validate_required_fields(self, script: dict) -> tuple[list[str], list[str]]:
        """Valida que existan los campos requeridos."""
        errors = []
        warnings = []
        
        required = self.rules.get("required_fields", [])
        for field in required:
            if field not in script or not script[field]:
                errors.append(f"Campo requerido faltante: {field}")
        
        return errors, warnings
    
    def _validate_narration(self, script: dict) -> tuple[list[str], list[str]]:
        """Valida el texto de narración."""
        errors = []
        warnings = []
        
        narration = script.get("narration_text", "")
        
        if not narration:
            errors.append("Texto de narración vacío")
            return errors, warnings
        
        # Longitud
        min_len = self.rules.get("min_narration_length", 200)
        max_len = self.rules.get("max_narration_length", 800)
        
        if len(narration) < min_len:
            errors.append(f"Narración muy corta ({len(narration)} chars, mínimo {min_len})")
        elif len(narration) > max_len:
            warnings.append(f"Narración muy larga ({len(narration)} chars, máximo {max_len})")
        
        # Verificar puntuación
        if not any(p in narration for p in [".", "!", "?"]):
            warnings.append("Narración sin puntuación final (puede afectar TTS)")
        
        # Verificar frases muy largas
        sentences = narration.replace("!", ".").replace("?", ".").split(".")
        for i, sentence in enumerate(sentences):
            words = sentence.split()
            if len(words) > 15:
                warnings.append(f"Frase {i+1} tiene {len(words)} palabras (máx recomendado: 12)")
        
        return errors, warnings
    
    def _validate_subtitles(self, script: dict) -> tuple[list[str], list[str]]:
        """Valida la estructura de subtítulos."""
        errors = []
        warnings = []
        
        subtitles = script.get("subtitles", [])
        
        if not subtitles:
            errors.append("No hay subtítulos definidos")
            return errors, warnings
        
        min_subs = self.rules.get("min_subtitles", 8)
        max_duration = self.rules.get("max_subtitle_duration", 4.0)
        max_words = self.rules.get("max_words_per_subtitle", 15)
        
        if len(subtitles) < min_subs:
            warnings.append(f"Pocos subtítulos ({len(subtitles)}, mínimo recomendado {min_subs})")
        
        prev_end = 0
        for i, sub in enumerate(subtitles):
            # Verificar estructura
            if "start" not in sub or "end" not in sub or "text" not in sub:
                errors.append(f"Subtítulo {i+1}: estructura inválida (falta start/end/text)")
                continue
            
            start = sub["start"]
            end = sub["end"]
            text = sub["text"]
            
            # Verificar tipos
            try:
                start = float(start)
                end = float(end)
            except (TypeError, ValueError):
                errors.append(f"Subtítulo {i+1}: timestamps inválidos")
                continue
            
            # Verificar orden
            if start < prev_end - 0.1:  # Tolerancia de 100ms
                warnings.append(f"Subtítulo {i+1}: se superpone con el anterior")
            
            if end <= start:
                errors.append(f"Subtítulo {i+1}: end ({end}) <= start ({start})")
            
            # Verificar duración
            duration = end - start
            if duration > max_duration:
                warnings.append(f"Subtítulo {i+1}: duración muy larga ({duration:.1f}s)")
            
            # Verificar longitud de texto
            words = text.split()
            if len(words) > max_words:
                warnings.append(f"Subtítulo {i+1}: muchas palabras ({len(words)}, máx {max_words})")
            
            prev_end = end
        
        # Verificar duración total
        if subtitles:
            total_duration = subtitles[-1].get("end", 0)
            if total_duration < 30:
                warnings.append(f"Duración total muy corta ({total_duration:.1f}s)")
            elif total_duration > 70:
                warnings.append(f"Duración total muy larga ({total_duration:.1f}s)")
        
        return errors, warnings
    
    def _validate_hooks(self, script: dict) -> tuple[list[str], list[str]]:
        """Valida los hooks alternativos."""
        errors = []
        warnings = []
        
        hooks = script.get("hooks_alternativos", [])
        
        if not hooks:
            warnings.append("No hay hooks alternativos (se recomienda tener 3)")
        elif len(hooks) < 3:
            warnings.append(f"Solo hay {len(hooks)} hooks alternativos (se recomiendan 3)")
        
        for i, hook in enumerate(hooks):
            if isinstance(hook, str):
                if len(hook) > 100:
                    warnings.append(f"Hook {i+1}: muy largo ({len(hook)} chars)")
                if len(hook.split()) > 15:
                    warnings.append(f"Hook {i+1}: demasiadas palabras")
        
        return errors, warnings
    
    def validate(self, script: dict) -> ValidationResult:
        """
        Valida un guión completo.
        
        Args:
            script: Diccionario con el guión a validar
            
        Returns:
            ValidationResult con el resultado de la validación
        """
        all_errors = []
        all_warnings = []
        
        # Ejecutar todas las validaciones
        validators = [
            self._validate_required_fields,
            self._validate_narration,
            self._validate_subtitles,
            self._validate_hooks,
        ]
        
        for validator in validators:
            errors, warnings = validator(script)
            all_errors.extend(errors)
            all_warnings.extend(warnings)
        
        is_valid = len(all_errors) == 0
        
        return ValidationResult(
            is_valid=is_valid,
            errors=all_errors,
            warnings=all_warnings
        )
    
    def fix_common_issues(self, script: dict) -> dict:
        """
        Intenta corregir problemas comunes en el guión.
        
        Args:
            script: Guión a corregir
            
        Returns:
            Guión corregido
        """
        fixed = script.copy()
        
        # Asegurar que existan hooks_alternativos
        if "hooks_alternativos" not in fixed:
            fixed["hooks_alternativos"] = []
        
        # Asegurar que los subtítulos tengan la estructura correcta
        subtitles = fixed.get("subtitles", [])
        fixed_subs = []
        
        for sub in subtitles:
            if isinstance(sub, dict):
                fixed_sub = {
                    "start": float(sub.get("start", 0)),
                    "end": float(sub.get("end", 0)),
                    "text": str(sub.get("text", ""))
                }
                fixed_subs.append(fixed_sub)
        
        fixed["subtitles"] = fixed_subs
        
        # Agregar puntuación si falta
        narration = fixed.get("narration_text", "")
        if narration and not narration.rstrip().endswith((".", "!", "?")):
            fixed["narration_text"] = narration.rstrip() + "."
        
        return fixed


def main():
    """Función principal para testing."""
    import argparse
    import json
    from rich.console import Console
    from rich.panel import Panel
    
    parser = argparse.ArgumentParser(description="Script Validator")
    parser.add_argument("--file", type=str, help="Archivo JSON con guión a validar")
    args = parser.parse_args()
    
    console = Console()
    validator = ScriptValidator()
    
    if args.file:
        try:
            with open(args.file, "r", encoding="utf-8") as f:
                script = json.load(f)
        except Exception as e:
            console.print(f"[red]Error leyendo archivo: {e}[/red]")
            return
    else:
        # Script de prueba
        script = {
            "narration_text": "Test de narración corta.",
            "subtitles": [
                {"start": 0, "end": 3, "text": "Test subtitle"}
            ]
        }
    
    result = validator.validate(script)
    
    if result.is_valid:
        console.print(Panel("[green]✓ Guión válido[/green]", title="Resultado"))
    else:
        console.print(Panel("[red]✗ Guión inválido[/red]", title="Resultado"))
    
    if result.errors:
        console.print("\n[red]Errores:[/red]")
        for error in result.errors:
            console.print(f"  • {error}")
    
    if result.warnings:
        console.print("\n[yellow]Advertencias:[/yellow]")
        for warning in result.warnings:
            console.print(f"  • {warning}")


if __name__ == "__main__":
    main()
