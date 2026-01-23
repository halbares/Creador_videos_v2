"""
Analizador de guiones para extraer keywords de stickers.
Usa LLM para identificar conceptos visualizables.
"""

import logging
from typing import Optional
from ..llm.openrouter import OpenRouterClient

logger = logging.getLogger(__name__)


class StickerAnalyzer:
    """Extrae conceptos visuales del guión para generar stickers."""
    
    def __init__(self, llm_client: Optional[OpenRouterClient] = None):
        self.llm = llm_client or OpenRouterClient()
    
    def extract_sticker_keywords(
        self, 
        script: dict, 
        stickers_per_scene: int = 2,
        scene_duration: float = 10.0
    ) -> list[dict]:
        """
        Analiza el guión y extrae keywords para buscar stickers.
        Genera 1-2 stickers POR ESCENA (cada ~10 segundos).
        
        Args:
            script: Dict con narration_text, subtitles, etc.
            stickers_per_scene: Stickers por cada escena de ~10s
            scene_duration: Duración de cada escena
            
        Returns:
            Lista de dicts con keyword, start, end
        """
        narration = script.get("narration_text", "")
        subtitles = script.get("subtitles", [])
        
        if not narration:
            return []
        
        # Calcular duración total
        total_duration = 0
        if subtitles:
            total_duration = max(s.get("end", 0) for s in subtitles)
        else:
            total_duration = len(narration.split()) / 2.5
        
        # Calcular número de escenas y total de stickers
        num_scenes = max(1, int(total_duration / scene_duration))
        total_stickers = num_scenes * stickers_per_scene
        
        prompt = f"""
Analiza este guión de video de Mindfulness y extrae {total_stickers} conceptos visuales que se puedan representar con imágenes/stickers.

GUIÓN:
"{narration}"

DURACIÓN TOTAL: {total_duration:.1f} segundos

REGLAS:
1. Elige conceptos CONCRETOS y visuales (persona, objeto, naturaleza)
2. Prefiere conceptos iconográficos (cerebro, corazón, montaña, sol, luna)
3. Evita conceptos abstractos (paz, amor, energía) a menos que tengan representación icónica
4. Distribuye los stickers a lo largo del video
5. Cada sticker debe aparecer 5-10 segundos

Responde SOLO con JSON, sin explicaciones:
{{
  "stickers": [
    {{"keyword": "brain icon", "keyword_es": "cerebro", "start": 5.0, "end": 12.0}},
    {{"keyword": "meditation person", "keyword_es": "meditación", "start": 20.0, "end": 28.0}}
  ]
}}
"""
        
        try:
            response = self.llm._call_llm([{"role": "user", "content": prompt}])
            if not response:
                return self._fallback_keywords(total_duration, total_stickers)
            
            result = self.llm._extract_json(response)
            if result and "stickers" in result:
                return result["stickers"]
            
        except Exception as e:
            logger.error(f"Error extrayendo keywords: {e}")
        
        return self._fallback_keywords(total_duration, total_stickers)
    
    def suggest_visual_style_and_mood(self, script: dict) -> tuple[str, str]:
        """
        Usa LLM para sugerir el ESTILO y MOOD visual basado en el guión.
        
        Args:
            script: Dict con narration_text
            
        Returns:
            Tuple (style, mood)
        """
        narration = script.get("narration_text", "")[:1000]
        
        prompt = f"""
Analiza este guión de video de Mindfulness y elige el ESTILO VISUAL y la PALETA DE COLORES (Mood) más apropiados para el arte generativo de fondo.

GUIÓN:
"{narration}"

OPCIONES DE ESTILO (elige UNO):
- particles: Partículas fluyendo (energía, conexión, pensamientos)
- blob: Formas orgánicas suaves (respiración, relajación profunda, yo interior)
- ink: Tinta disolviéndose (fluidez, dejar ir, impermanencia)
- smoke: Humo/Niebla etérea (misterio, calma, espíritu)
- marble: Patrones líquidos densos (complejidad, riqueza, transformación)
- mandala: Geometría sagrada giratoria (espiritualidad, centro, divinidad)
- hex: Red hexagonal pulsante (orden, estructura, tecnología zen)
- rings: Anillos concéntricos (sonido, vibración, expansión)
- voronoi: Células conectadas (naturaleza molecular, tejido de la realidad)
- starfield: Campo de estrellas 3D (infinito, viaje astral, sueño profundo)
- nebula: Nubes de gas cósmico (transformación, creatividad, misterio)
- aurora: Luces del norte ondulantes (magia, esperanza, asombro)
- gradient: Gradientes suaves cambiantes (calma pura, simplicidad)
- singleline: Línea única abstracta (claridad, enfoque, camino)
- breathing: Círculo de respiración guiada (ejercicio de respiración, paz)

OPCIONES DE MOOD (elige UNO):
- calm: Azul/Cyan tranquilo (meditación, relajación)
- deep: Púrpura/Violeta profundo (introspección, universo interior)
- nature: Verde esmeralda (naturaleza, bosques, plantas)
- sunset: Naranjas/Rojos cálidos (gratitud, energía positiva)
- ocean: Turquesa/Aqua (fluidez, agua, respiración)
- cosmic: Rosa/Violeta/Amarillo (espiritualidad, cosmos, estrellas)
- warm: Tonos tierra cálidos (hogar, confort, seguridad)
- minimal: Grises elegantes (minimalismo, claridad mental)

Responde SOLO con un JSON:
{{
  "style": "blob",
  "mood": "ocean"
}}
"""
        
        try:
            response = self.llm._call_llm([{"role": "user", "content": prompt}])
            if response:
                result = self.llm._extract_json(response)
                if result:
                    style = result.get("style", "particles").lower()
                    mood = result.get("mood", "calm").lower()
                    
                    valid_styles = ["particles", "blob", "ink", "smoke", "marble", "mandala", "hex", "rings", "voronoi", "starfield", "nebula", "aurora", "gradient", "singleline", "breathing"]
                    valid_moods = ["calm", "deep", "nature", "sunset", "ocean", "cosmic", "warm", "minimal"]
                    
                    if style not in valid_styles: style = "particles"
                    if mood not in valid_moods: mood = "calm"
                    
                    return style, mood
                    
        except Exception as e:
            logger.error(f"Error sugiriendo estilo/mood: {e}")
        
        # Fallback aleatorio
        import random
        return random.choice(["particles", "blob", "ink"]), random.choice(["calm", "ocean", "sunset", "cosmic"])
    
    def _fallback_keywords(self, duration: float, count: int) -> list[dict]:
        """Keywords por defecto si falla el LLM."""
        defaults = [
            {"keyword": "meditation person", "keyword_es": "meditación", "start": 5.0, "end": 12.0},
            {"keyword": "peaceful nature", "keyword_es": "naturaleza", "start": duration * 0.5, "end": duration * 0.5 + 8.0},
        ]
        return defaults[:count]
