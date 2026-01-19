"""
Script Parser
Se encarga de validar y convertir la salida del LLM en objetos de dominio.
"""
import json
import logging
from typing import Dict, Any, Union
from ..domain.models import VideoScript, Scene, VisualCue

logger = logging.getLogger(__name__)

class ScriptParser:
    """Validador y parseador de guiones estructurados."""
    
    def parse(self, raw_input: Union[str, Dict[str, Any]]) -> VideoScript:
        """
        Convierte un JSON (string o dict) en un objeto VideoScript validado.
        """
        try:
            # 1. Normalizar entrada
            if isinstance(raw_input, str):
                # Limpiar bloques de código markdown si existen
                clean_input = raw_input.replace("```json", "").replace("```", "").strip()
                data = json.loads(clean_input)
            else:
                data = raw_input
                
            # 2. Validación estricta con Pydantic
            script = VideoScript(**data)
            
            # 3. Validaciones de negocio adicionales
            self._validate_logic(script)
            
            return script
            
        except json.JSONDecodeError as e:
            logger.error(f"Error decodificando JSON del LLM: {e}")
            raise ValueError("El LLM no devolvió un JSON válido")
        except Exception as e:
            logger.error(f"Error parseando guión: {e}")
            raise e
            
    def _validate_logic(self, script: VideoScript):
        """Reglas de negocio extra."""
        if len(script.scenes) < 3:
            logger.warning("El guión es muy corto (menos de 3 escenas).")
            
        # Verificar que los IDs sean secuenciales
        expected_id = 1
        for scene in script.scenes:
            if scene.id != expected_id:
                logger.warning(f"IDs de escena desordenados. Esperado {expected_id}, encontrado {scene.id}")
            expected_id += 1

if __name__ == "__main__":
    # Test rápido
    parser = ScriptParser()
    
    test_json = """
    {
        "title": "Prueba de Concepto V3",
        "concept": "Demostración de arquitectura",
        "music_mood": "lo-fi",
        "scenes": [
            {
                "id": 1,
                "text": "¿Cansado de los videos aburridos?",
                "visual_cue": {
                    "keywords": ["bored person", "yawn", "computer"],
                    "description": "persona aburrida frente a la pantalla",
                    "effect": "zoom"
                }
            },
            {
                "id": 2,
                "text": "La V3 cambia el juego por completo.",
                "visual_cue": {
                    "keywords": ["explosion", "mind blown", "colors"],
                    "description": "explosión de colores dinámica",
                    "effect": "shake"
                }
            }
        ]
    }
    """
    
    try:
        result = parser.parse(test_json)
        print(f"✅ Script validado: '{result.title}' con {len(result.scenes)} escenas.")
        print(f"   Primer Visual Key: {result.scenes[0].visual_cue.keywords}")
    except Exception as e:
        print(f"❌ Error: {e}")
