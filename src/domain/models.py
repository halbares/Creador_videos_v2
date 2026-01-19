"""
Modelos de Dominio (Clean Architecture)
Definen la estructura de datos central del sistema.
"""
from typing import List, Optional
from pydantic import BaseModel, Field

class VisualCue(BaseModel):
    """Describe qué se debe ver en pantalla durante una escena."""
    keywords: List[str] = Field(..., description="Palabras clave para buscar el video clip")
    description: str = Field(..., description="Dercripción narrativa de la escena visual")
    effect: str = Field("zoom", description="Efecto de movimiento (zoom, pan, static)")

class Scene(BaseModel):
    """
    Una unidad atómica de narrativa audiovisual.
    Sincroniza un fragmento de texto con un asset visual.
    """
    id: int
    text: str = Field(..., description="Texto que se narra en esta escena")
    visual_cue: VisualCue
    
    # Timing (se llena post-TTS/Whisper)
    start_time: float = 0.0
    end_time: float = 0.0
    duration: float = 0.0
    
    # Asset (se llena post-Búsqueda)
    video_path: Optional[str] = None

class VideoScript(BaseModel):
    """El guión completo estructurado en escenas."""
    title: str
    concept: str
    scenes: List[Scene]
    music_mood: str = "energetic"
    
    @property
    def total_duration(self) -> float:
        return sum(s.duration for s in self.scenes)
