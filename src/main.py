"""
Entrada principal Creador Videos V3
"""
import sys
import logging
from src.orchestrator import VideoOrchestrator

# Configurar logging
logging.basicConfig(level=logging.INFO)

DEMO_SCRIPT = """
{
    "title": "La Revolución V3",
    "concept": "Demo técnica",
    "music_mood": "epic",
    "scenes": [
        {
            "id": 1,
            "text": "Bienvenido a la nueva era de la creación de video.",
            "visual_cue": {
                "keywords": ["futuristic technology", "ai", "robot"],
                "description": "tecnología futurista brillante",
                "effect": "zoom"
            }
        },
        {
            "id": 2,
            "text": "Ya no se trata de videos estáticos y aburridos.",
            "visual_cue": {
                "keywords": ["bored person", "generic office"],
                "description": "gente aburrida en oficina blanco y negro",
                "effect": "static"
            }
        },
        {
            "id": 3,
            "text": "Ahora, cada frase tiene su propia vida visual.",
            "visual_cue": {
                "keywords": ["explosion colors", "dynamic art"],
                "description": "explosión de creatividad en 4k",
                "effect": "shake"
            }
        }
    ]
}
"""

def main():
    print("🎬 Creador de Videos V3 - NextGen")
    orchestrator = VideoOrchestrator()
    
    # Ejecutar demo
    orchestrator.run_demo(DEMO_SCRIPT)

if __name__ == "__main__":
    main()
