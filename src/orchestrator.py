"""
Orquestador Central V3
Coordina todos los subsistemas para convertir una idea en un video final.
"""
import logging
from pathlib import Path
from typing import Optional

from .domain.models import VideoScript
from .director.parser import ScriptParser
from .audio.engine import AudioEngine
from .infrastructure.pexels import PexelsClient
from .infrastructure.compositor import VideoCompositor

logger = logging.getLogger(__name__)

class VideoOrchestrator:
    """
    El 'Director de Orquesta'. 
    Recibe un script en raw (JSON/Texto), y coordina su producción.
    """
    
    def __init__(self, output_dir: str = "./output"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Subsistemas
        self.parser = ScriptParser()
        self.audio_engine = AudioEngine(model_size="base") # Usar 'base' para equilibrio calidad/vel
        self.pexels = PexelsClient()
        self.compositor = VideoCompositor(output_dir=output_dir)
        
    def produce_video(self, raw_script: str) -> Optional[str]:
        """
        Ejecuta el pipeline completo.
        """
        print("\n🚀 INICIANDO PRODUCCIÓN DE VIDEO V3")
        print("===================================")
        
        # 1. Parsing y Validación
        print("\nDO Step 1: Interpretando Guión...")
        try:
            script: VideoScript = self.parser.parse(raw_script)
            print(f"✅ Guión válido: '{script.title}' ({len(script.scenes)} escenas)")
        except Exception as e:
            logger.error(f"Falló el parsing: {e}")
            return None
            
        # 2. Generación de Audio y Alineación (Whisper)
        # Nota: En un caso real, aquí llamaríamos al TTS primero.
        # Para este prototipo, asumiremos que tenemos una forma de obtener el audio.
        # TODO: Integrar TTS real. Por ahora usaremos un placeholder o integración futura.
        print("\n🎵 Step 2: Motor de Audio (Simulado para POC)...")
        # Aquí iría: self.audio_engine.generate_and_align(script)
        # Como no tenemos TTS conectado en V3 aun, vamos a detenernos si no hay implementación
        # O podemos simular duraciones para probar el compositor.
        
        # SIMULACIÓN DE TIEMPOS para POC (Proof of Concept)
        # Asignamos 5 segundos por escena si no hay audio real
        print("⚠️  Modo POC: Asignando tiempos simulados (5s/escena)")
        for scene in script.scenes:
            scene.duration = 5.0
            
        # 3. Búsqueda de Assets (Pexels)
        print("\n🎨 Step 3: Buscando Assets Visuales...")
        try:
            downloaded_assets = self.pexels.download_scenes(script.scenes)
            print(f"✅ Assets descargados: {len(downloaded_assets)}/{len(script.scenes)}")
        except Exception as e:
            logger.error(f"Error en Pexels: {e}")
            # No retornamos None, intentamos seguir con lo que haya
        
        # 4. Composición
        print("\n🎬 Step 4: Renderizando Video Final...")
        try:
            # Necesitamos un audio dummy para moviepy si no generamos uno real
            # Para la demo, el compositor fallará si no hay audio file.
            # Vamos a crear un silencio o pedir un path de audio.
            
            # TODO: Fix temporal para la demo sin TTS
            pass 
            
            # output_path = self.compositor.render(script.scenes, audio_path, "video_v3_demo")
            # return output_path
            
        except Exception as e:
            logger.error(f"Error en composición: {e}")
            return None
            
        print("\n✅ Producción Finalizada (Simulación)")
        return "path/to/video.mp4"

    def run_demo(self, raw_script: str):
        """
        Ejecuta una demostración de los pasos 1 y 3 (Parsing y Assets).
        """
        return self.produce_video(raw_script)
