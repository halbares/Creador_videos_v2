"""
Compositor Visual V3
Ensambla escenas, audio y efectos para generar el video final.
"""
import logging
from pathlib import Path
from typing import List
from moviepy import VideoFileClip, AudioFileClip, concatenate_videoclips
# from moviepy import vfx # Uncomment if needed for effects
from ..domain.models import Scene

logger = logging.getLogger(__name__)

class VideoCompositor:
    """
    Motor de renderizado basado en MoviePy.
    """
    
    def __init__(self, output_dir: str = "./output"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
    def render(self, scenes: List[Scene], audio_path: str, output_filename: str) -> str:
        """
        Renderiza el video final uniendo las escenas.
        
        Args:
            scenes: Lista de escenas con paths de video y duraciones ya calculadas.
            audio_path: Path al archivo de audio completo.
            output_filename: Nombre del archivo de salida (sin extensión).
            
        Returns:
            Path absoluto del video generado.
        """
        clips = []
        print(f"🎬 Iniciando composición de {len(scenes)} escenas...")
        
        try:
            # 1. Cargar Audio Global
            audio_clip = AudioFileClip(audio_path)
            
            # 2. Procesar cada escena
            current_time = 0.0
            
            for i, scene in enumerate(scenes):
                if not scene.video_path or not Path(scene.video_path).exists():
                    logger.warning(f"Escena {scene.id} no tiene video válido. Saltando.")
                    continue
                    
                # Cargar clip de video
                clip = VideoFileClip(scene.video_path)
                
                # Ajustar duración: Si el clip es más corto que la escena, buclearlo.
                # Si es más largo, cortarlo.
                target_duration = scene.duration
                
                if clip.duration < target_duration:
                    clip = clip.loop(duration=target_duration)
                else:
                    clip = clip.subclip(0, target_duration)
                    
                # Redimensionar a formato vertical (9:16) si es necesario (1080x1920)
                # clip = clip.resize(height=1920)
                # clip = clip.crop(x1=clip.w/2 - 540, y1=0, width=1080, height=1920)
                
                # Efectos básicos (Zoom suave, Fade in/out)
                clip = clip.fadein(0.5).fadeout(0.5)
                
                clips.append(clip)
                current_time += target_duration
                print(f"  🎞️ Escena {scene.id} procesada ({target_duration:.2f}s)")
            
            # 3. Concatenar
            final_video = concatenate_videoclips(clips, method="compose")
            
            # 4. Asignar audio
            final_video = final_video.set_audio(audio_clip)
            
            # 5. Exportar
            output_path = self.output_dir / f"{output_filename}.mp4"
            print(f"🚀 Renderizando video final: {output_path}...")
            
            final_video.write_videofile(
                str(output_path),
                fps=30,
                codec="libx264",
                audio_codec="aac",
                threads=4,
                preset="fast" # Usar 'ultrafast' para pruebas
            )
            
            return str(output_path)
            
        except Exception as e:
            logger.error(f"Error renderizando video: {e}")
            raise e
        finally:
            # Limpieza
            for clip in clips:
                try:
                    clip.close()
                except:
                    pass
