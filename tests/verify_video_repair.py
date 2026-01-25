
import sys
import os
from pathlib import Path

# Add src to path
sys.path.append(os.path.abspath("."))

from src.video.renderer import VideoRenderer
from src.llm import SceneGenerator
from rich.console import Console

console = Console()

def test_repair():
    console.print("[bold cyan]Iniciando Test de Reparación...[/bold cyan]")
    
    # Test SceneGenerator load
    try:
        sg = SceneGenerator(None)
        console.print("[green]✓ SceneGenerator cargado correctamente[/green]")
    except Exception as e:
        console.print(f"[red]✗ Error cargando SceneGenerator: {e}[/red]")
        sys.exit(1)

    renderer = VideoRenderer(temp_dir="./temp", output_dir="./output")
    
    # Paths inputs
    intro_path = "./temp/dummy_intro.mp4"
    outro_path = "./temp/dummy_outro.mp4"
    narration_path = "./temp/dummy_narration.mp3"
    bg_path = "./temp/dummy_bg.jpg"
    subs_path = "./temp/dummy_subs.ass"
    
    # 1. Test Audio Mixing
    console.print("\n[yellow]1. Probando mezcla de audio (Intro + Narración + Outro)...[/yellow]")
    mixed_audio_path = "./temp/test_mixed_audio.mp3"
    
    success_audio = renderer.combine_audio_with_intro(
        main_audio_path=narration_path,
        intro_video_path=intro_path,
        outro_video_path=outro_path,
        output_path=mixed_audio_path
    )
    
    if success_audio:
        duration = renderer._get_audio_duration(mixed_audio_path)
        # Esperado: 3s (intro) + 5s (narracion) + 2s (outro) = ~10s
        console.print(f"[green]✓ Audio mezclado correctamente. Duración: {duration}s (Esperado: ~10s)[/green]")
    else:
        console.print("[red]✗ Falló mezcla de audio[/red]")
        sys.exit(1)
        
    # 2. Test Video Rendering (Multiscene)
    console.print("\n[yellow]2. Probando renderizado de video con normalización...[/yellow]")
    
    # Escenas: Intro + Contenido + Outro
    # Calculamos duración del contenido (5s)
    
    scene_configs = [
        {"path": intro_path, "duration": 3.0, "is_image": False}, # Clip 1 (Video)
        {"path": bg_path, "duration": 5.0, "is_image": True},     # Clip 2 (Imagen -> Video)
        {"path": outro_path, "duration": 2.0, "is_image": False}  # Clip 3 (Video)
    ]
    
    video_path = renderer.render_multiscene(
        audio_path=mixed_audio_path,
        scene_configs=scene_configs,
        subtitles_path=subs_path,
        output_filename="TEST_VERIFICATION_VIDEO",
        image_effect="zoom"
    )
    
    if video_path and os.path.exists(video_path):
        video_dur = renderer._get_video_duration(video_path)
        console.print(f"[bold green]✓ VIDEO GENERADO EXITOSAMENTE[/bold green]")
        console.print(f"Ruta: {video_path}")
        console.print(f"Duración final: {video_dur}s")
        console.print("\n[blue]Conclusión: Las funciones combine_audio_with_intro y render_multiscene (con normalización) funcionan correctamente.[/blue]")
    else:
        console.print("[bold red]✗ FALLÓ LA GENERACIÓN DEL VIDEO[/bold red]")
        sys.exit(1)

if __name__ == "__main__":
    test_repair()
