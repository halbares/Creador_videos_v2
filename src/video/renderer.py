"""
Renderizador de video con FFmpeg.
Genera videos verticales (9:16) con efectos para retención.
"""

import logging
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Optional, Literal

from pydub import AudioSegment

logger = logging.getLogger(__name__)


class VideoRenderer:
    """Renderiza videos finales con FFmpeg."""
    
    # Dimensiones para Shorts/Reels
    WIDTH = 1080
    HEIGHT = 1920
    FPS = 30
    
    def __init__(
        self,
        output_dir: str = "./output",
        temp_dir: str = "./temp"
    ):
        """
        Inicializa el renderizador.
        
        Args:
            output_dir: Directorio para videos finales
            temp_dir: Directorio para archivos temporales
        """
        self.output_dir = Path(output_dir)
        self.temp_dir = Path(temp_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.temp_dir.mkdir(parents=True, exist_ok=True)
        
        # Verificar FFmpeg
        if not self._check_ffmpeg():
            logger.warning("FFmpeg no encontrado en PATH")
    
    def _check_ffmpeg(self) -> bool:
        """Verifica que FFmpeg esté instalado."""
        try:
            subprocess.run(
                ["ffmpeg", "-version"],
                capture_output=True,
                check=True
            )
            return True
        except (subprocess.CalledProcessError, FileNotFoundError):
            return False
    
    def _get_audio_duration(self, audio_path: str) -> float:
        """Obtiene la duración de un archivo de audio."""
        try:
            audio = AudioSegment.from_file(audio_path)
            return len(audio) / 1000.0
        except Exception as e:
            logger.error(f"Error leyendo audio: {e}")
            return 60.0  # Fallback
    
    def _get_video_duration(self, video_path: str) -> float:
        """Obtiene la duración de un archivo de video."""
        try:
            result = subprocess.run([
                "ffprobe", "-v", "error",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                video_path
            ], capture_output=True, text=True, check=True)
            
            return float(result.stdout.strip())
        except Exception as e:
            logger.error(f"Error leyendo duración de video: {e}")
            return 0.0
    
    def create_color_background(
        self,
        duration: float,
        color: str = "0x1a1a2e",
        output_path: Optional[str] = None
    ) -> str:
        """
        Crea un video de fondo con color sólido.
        
        Args:
            duration: Duración en segundos
            color: Color en formato hex (0xRRGGBB)
            output_path: Ruta de salida opcional
            
        Returns:
            Ruta al video generado
        """
        if not output_path:
            output_path = str(self.temp_dir / "background_color.mp4")
        
        cmd = [
            "ffmpeg", "-y",
            "-f", "lavfi",
            "-i", f"color=c={color}:s={self.WIDTH}x{self.HEIGHT}:d={duration}:r={self.FPS}",
            "-c:v", "libx264",
            "-preset", "fast",
            "-pix_fmt", "yuv420p",
            output_path
        ]
        
        try:
            subprocess.run(cmd, capture_output=True, check=True)
            logger.info(f"Fondo de color creado: {output_path}")
            return output_path
        except subprocess.CalledProcessError as e:
            logger.error(f"Error creando fondo: {e.stderr.decode()}")
            raise
    
    def prepare_image_background(
        self,
        image_path: str,
        duration: float,
        output_path: Optional[str] = None,
        effect: str = "zoom"
    ) -> str:
        """
        Prepara una imagen como fondo con efectos de movimiento.
        
        Args:
            image_path: Ruta a la imagen
            duration: Duración en segundos
            output_path: Ruta de salida opcional
            effect: Efecto a aplicar (zoom, pan, kenburns)
            
        Returns:
            Ruta al video generado
        """
        if not output_path:
            output_path = str(self.temp_dir / "background_image.mp4")
        
        # Efectos para evitar que la imagen se vea estática (RETENCIÓN)
        if effect == "zoom":
            # Zoom lento hacia adentro
            filter_expr = (
                f"scale=-2:{self.HEIGHT * 2},"
                f"zoompan=z='min(zoom+0.0005,1.3)':d={int(duration * self.FPS)}:"
                f"x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':"
                f"s={self.WIDTH}x{self.HEIGHT}:fps={self.FPS}"
            )
        elif effect == "pan":
            # Pan horizontal lento
            filter_expr = (
                f"scale={self.WIDTH * 2}:-2,"
                f"crop={self.WIDTH}:{self.HEIGHT}:"
                f"'(in_w-out_w)*t/{duration}':0"
            )
        elif effect == "kenburns":
            # Combinación de zoom y pan (estilo documental)
            filter_expr = (
                f"scale=-2:{self.HEIGHT * 2},"
                f"zoompan=z='if(lte(on,1),1.5,max(1.001,zoom-0.0005))':"
                f"d={int(duration * self.FPS)}:"
                f"x='iw/2-(iw/zoom/2)+sin(on/100)*20':"
                f"y='ih/2-(ih/zoom/2)':"
                f"s={self.WIDTH}x{self.HEIGHT}:fps={self.FPS}"
            )
        else:
            # Sin efecto, solo escalar
            filter_expr = f"scale={self.WIDTH}:{self.HEIGHT}:force_original_aspect_ratio=increase,crop={self.WIDTH}:{self.HEIGHT}"
        
        cmd = [
            "ffmpeg", "-y",
            "-loop", "1",
            "-i", image_path,
            "-vf", filter_expr,
            "-t", str(duration),
            "-c:v", "libx264",
            "-preset", "fast",
            "-pix_fmt", "yuv420p",
            output_path
        ]
        
        try:
            subprocess.run(cmd, capture_output=True, check=True)
            logger.info(f"Fondo de imagen creado: {output_path}")
            return output_path
        except subprocess.CalledProcessError as e:
            logger.error(f"Error creando fondo: {e.stderr.decode()}")
            raise
    
    def prepare_video_background(
        self,
        video_path: str,
        target_duration: float,
        output_path: Optional[str] = None
    ) -> str:
        """
        Prepara un video como fondo, ajustando duración y dimensiones.
        
        Args:
            video_path: Ruta al video original
            target_duration: Duración objetivo
            output_path: Ruta de salida opcional
            
        Returns:
            Ruta al video procesado
        """
        if not output_path:
            output_path = str(self.temp_dir / "background_video.mp4")
        
        source_duration = self._get_video_duration(video_path)
        
        # Calcular si necesitamos loop o corte
        if source_duration < target_duration:
            # Necesitamos hacer loop
            loop_times = int(target_duration / source_duration) + 1
            input_opts = ["-stream_loop", str(loop_times)]
        else:
            input_opts = []
        
        # Filtro para escalar y centrar
        filter_expr = (
            f"scale={self.WIDTH}:{self.HEIGHT}:"
            f"force_original_aspect_ratio=increase,"
            f"crop={self.WIDTH}:{self.HEIGHT},"
            f"setpts=PTS-STARTPTS"
        )
        
        cmd = [
            "ffmpeg", "-y",
            *input_opts,
            "-i", video_path,
            "-vf", filter_expr,
            "-t", str(target_duration),
            "-an",  # Sin audio del video de fondo
            "-c:v", "libx264",
            "-preset", "fast",
            "-pix_fmt", "yuv420p",
            output_path
        ]
        
        try:
            subprocess.run(cmd, capture_output=True, check=True)
            logger.info(f"Fondo de video preparado: {output_path}")
            return output_path
        except subprocess.CalledProcessError as e:
            logger.error(f"Error preparando video: {e.stderr.decode()}")
            raise
    
    def render_final(
        self,
        audio_path: str,
        background_path: str,
        subtitles_path: str,
        output_filename: str,
        is_background_image: bool = False,
        image_effect: str = "zoom"
    ) -> Optional[str]:
        """
        Renderiza el video final combinando todos los elementos.
        
        Args:
            audio_path: Ruta al audio de narración
            background_path: Ruta al fondo (imagen o video)
            subtitles_path: Ruta a los subtítulos ASS
            output_filename: Nombre del archivo de salida (sin extensión)
            is_background_image: Si el fondo es una imagen
            image_effect: Efecto para imágenes (zoom, pan, kenburns)
            
        Returns:
            Ruta al video final o None si hay error
        """
        output_path = self.output_dir / f"{output_filename}.mp4"
        
        # Obtener duración del audio
        duration = self._get_audio_duration(audio_path)
        logger.info(f"Duración del audio: {duration:.2f}s")
        
        # Preparar fondo
        if is_background_image:
            prepared_bg = self.prepare_image_background(
                background_path, duration, effect=image_effect
            )
        else:
            prepared_bg = self.prepare_video_background(
                background_path, duration
            )
        
        # Renderizar video final con subtítulos
        # Usar filtro ASS para subtítulos
        filter_complex = f"ass='{subtitles_path}'"
        
        cmd = [
            "ffmpeg", "-y",
            "-i", prepared_bg,
            "-i", audio_path,
            "-vf", filter_complex,
            "-c:v", "libx264",
            "-preset", "medium",
            "-crf", "23",
            "-c:a", "aac",
            "-b:a", "192k",
            "-shortest",
            "-pix_fmt", "yuv420p",
            str(output_path)
        ]
        
        try:
            logger.info("Renderizando video final...")
            result = subprocess.run(cmd, capture_output=True, check=True)
            logger.info(f"Video renderizado: {output_path}")
            return str(output_path)
            
        except subprocess.CalledProcessError as e:
            logger.error(f"Error renderizando: {e.stderr.decode()}")
            return None
    
    def render_preview(
        self,
        subtitles_path: str,
        duration: float = 10.0,
        output_filename: str = "preview"
    ) -> Optional[str]:
        """
        Genera una preview rápida solo con subtítulos.
        
        Args:
            subtitles_path: Ruta a los subtítulos
            duration: Duración de la preview
            output_filename: Nombre del archivo
            
        Returns:
            Ruta al video de preview
        """
        output_path = self.output_dir / f"{output_filename}_preview.mp4"
        
        # Crear fondo simple
        bg_path = self.create_color_background(duration)
        
        # Agregar subtítulos
        cmd = [
            "ffmpeg", "-y",
            "-i", bg_path,
            "-vf", f"ass='{subtitles_path}'",
            "-c:v", "libx264",
            "-preset", "ultrafast",
            "-t", str(duration),
            "-pix_fmt", "yuv420p",
            str(output_path)
        ]
        
        try:
            subprocess.run(cmd, capture_output=True, check=True)
            logger.info(f"Preview generada: {output_path}")
            return str(output_path)
        except subprocess.CalledProcessError as e:
            logger.error(f"Error: {e.stderr.decode()}")
            return None


def main():
    """Función principal para testing."""
    import argparse
    from rich.console import Console
    
    parser = argparse.ArgumentParser(description="Video Renderer")
    parser.add_argument("--test", action="store_true", help="Test de renderizado")
    parser.add_argument("--preview", action="store_true", help="Generar preview")
    parser.add_argument("--audio", type=str, help="Ruta al audio")
    parser.add_argument("--background", type=str, help="Ruta al fondo")
    parser.add_argument("--subtitles", type=str, help="Ruta a los subtítulos")
    parser.add_argument("--output", type=str, default="test_video", help="Nombre de salida")
    args = parser.parse_args()
    
    console = Console()
    renderer = VideoRenderer()
    
    if args.preview and args.subtitles:
        console.print("[cyan]Generando preview...[/cyan]")
        path = renderer.render_preview(args.subtitles, output_filename=args.output)
        if path:
            console.print(f"[green]✓ Preview: {path}[/green]")
        return
    
    if args.audio and args.background and args.subtitles:
        console.print("[cyan]Renderizando video final...[/cyan]")
        
        is_image = args.background.lower().endswith((".jpg", ".jpeg", ".png", ".webp"))
        
        path = renderer.render_final(
            args.audio,
            args.background,
            args.subtitles,
            args.output,
            is_background_image=is_image
        )
        
        if path:
            console.print(f"[green]✓ Video final: {path}[/green]")
        else:
            console.print("[red]✗ Error renderizando[/red]")
        return
    
    # Test básico
    console.print("[cyan]Test de renderizador...[/cyan]")
    
    # Crear fondo de prueba
    bg_path = renderer.create_color_background(5.0)
    console.print(f"[green]✓ Fondo de color creado: {bg_path}[/green]")


if __name__ == "__main__":
    main()
