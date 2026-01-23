import logging
import os
import re
import random
from pathlib import Path
from typing import Optional

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

from ..llm.openrouter import OpenRouterClient
from ..tts.edge_tts import EdgeTTSEngine
from ..video.pexels import PexelsClient
from ..video.subtitles import SubtitleGenerator
from ..scraper.youtube import YouTubeClient
from ..scraper.rss import RSSClient
from .ffmpeg_utils import FFmpegAssembler
from ..utils.cache import ContentCache

# Publisher Imports
import sys
sys.path.append(str(Path(__file__).parent.parent))
from publisher import CloudUploader, MakeWebhookClient

logger = logging.getLogger(__name__)
console = Console()

class MindfulnessPipeline:
    """
    Orchestrator for Mindfulness/Generative Art Videos.
    """
    
    def __init__(self, output_dir="./output", temp_dir="./temp", cache_dir="./cache", assets_dir="./assets"):
        self.output_dir = Path(output_dir)
        self.temp_dir = Path(temp_dir)
        self.cache_dir = Path(cache_dir)
        
        self.cache = ContentCache(cache_dir=str(cache_dir))
        
        self.llm = OpenRouterClient() # Reuse existing
        # TTS with calming voice (assuming config allows selection or defaults)
        self.tts = EdgeTTSEngine(output_dir=str(temp_dir), voice="es-CO-GonzaloNeural") 
        self.pexels = PexelsClient(assets_dir=str(assets_dir))
        self.subs_gen = SubtitleGenerator(output_dir=str(temp_dir))
        self.assembler = FFmpegAssembler(output_dir=str(output_dir))
        
        # Publisher Init
        self.uploader = CloudUploader()
        self.webhook = MakeWebhookClient()
        
        self.youtube = YouTubeClient(cache=self.cache)

        
        # Ensure dirs
        for d in [self.output_dir, self.temp_dir, self.cache_dir]:
            d.mkdir(parents=True, exist_ok=True)

    def generate_mindfulness_video(self, source_content: Optional[dict] = None):
        """Main flow execution with sticker-based visuals."""
        console.print(f"[bold cyan]🧘 Generando Video de Mindfulness[/bold cyan]")

        if not source_content:
            console.print("[red]No hay contenido fuente[/red]")
            return

        topic = source_content.get('title', 'Mindfulness')
        console.print(f"[cyan]Tema: {topic}[/cyan]")

        # 1. Scripting
        script = self._step_script(source_content)
        if not script: return

        # 2. Audio & Subtitles
        audio_res = self._step_audio(script)
        if not audio_res: return

        duration = audio_res['duration']
        
        # 3. Extract Sticker Keywords from Script
        console.print("[cyan]3. Analizando guión para stickers...[/cyan]")
        from .sticker_analyzer import StickerAnalyzer

        analyzer = StickerAnalyzer(self.llm)
        sticker_specs = analyzer.extract_sticker_keywords(script, stickers_per_scene=1, scene_duration=10.0)
        console.print(f"[green]✓ Identificados {len(sticker_specs)} conceptos para stickers[/green]")
        
        # 4. Fetch Stickers (Pexels + remove background)
        console.print("[cyan]4. Descargando y preparando stickers...[/cyan]")
        from .sticker_fetcher import StickerFetcher
        fetcher = StickerFetcher(cache_dir=str(self.cache_dir / "stickers"))
        stickers = fetcher.fetch_multiple(sticker_specs)
        console.print(f"[green]✓ {len(stickers)} stickers listos[/green]")
        
        # 5. Suggest Visual Style and Mood using LLM
        console.print("[cyan]5. Seleccionando estilo visual...[/cyan]")
        style, mood = analyzer.suggest_visual_style_and_mood(script)
        console.print(f"[green]✓ Estilo: {style} | Mood: {mood}[/green]")
        
        # 6. Generate Generative Art (full duration)
        p5_video = self._step_p5_visuals(duration, topic, audio_res['audio_path'], style, mood)
        if not p5_video: return

        # 6. Generate Subtitles
        console.print("[cyan]5. Generando subtítulos...[/cyan]")
        
        # Sanitize title for filenames
        raw_title = script.get('title', 'video')
        safe_title = re.sub(r'[^\w\-]', '_', raw_title)
        
        subs_file = self.subs_gen.generate_animated(
            audio_res['subtitles'], 
            f"subs_{safe_title}", 
            animation="fade" 
        )
        
        # 7. Final Assembly: P5 base + Stickers + Audio + Subtitles
        console.print("[cyan]6. Ensamblaje Final...[/cyan]")
        
        output_name = f"Mindfulness_{safe_title}.mp4"
        output_path = str(self.output_dir / output_name)
        
        success = self.assembler.assemble_with_stickers(
            p5_video,
            stickers,
            audio_res['audio_path'], 
            subs_file, 
            output_path
        )
        
        if success:
             console.print(f"\n[bold green]✨ Video Completado: {output_path}[/bold green]\n")
             
             # 8. PUBLICATION (Upload & Webhook)
             console.print("[cyan]8. Publicando (Subida + Webhook)...[/cyan]")
             
             if not self.webhook.is_configured():
                 console.print("[yellow]⚠ Webhook no configurado. Saltando publicación automática.[/yellow]")
             else:
                 # Generar descripción completa para metadatos
                 # Asegurar que existan hashtags
                 hashtags = script.get("keywords", [])
                 if not hashtags: hashtags = ["mindfulness", "bienestar", "meditacion"]
                 
                 # Subir a la nube
                 console.print("[dim]Subiendo a la nube...[/dim]")
                 upload_result = self.uploader.upload_and_get_link(output_path, subfolder="Mindfulness")
                 
                 if upload_result:
                     video_url = upload_result["public_url"]
                     console.print(f"[green]✓ Video subido: {video_url}[/green]")
                     
                     # Enviar Webhook
                     console.print("[dim]Enviando webhook a Make...[/dim]")
                     
                     # Preparar metadatos enriquecidos
                     script["source_url"] = source_content.get("url", "")
                     script["_duration"] = duration
                     
                     webhook_result = self.webhook.publish_from_metadata(
                        video_url=video_url,
                        script=script,
                        destinations=["facebook", "youtube"] # Default destinations
                     )
                     
                     if webhook_result["success"]:
                        console.print(f"[bold green]🚀 Publicación EXITOSA a Make.com (Code {webhook_result['status_code']})[/bold green]")
                     else:
                        console.print(f"[red]✗ Error en webhook: {webhook_result.get('error')}[/red]")
                 else:
                     console.print("[red]✗ Error subiendo video a la nube[/red]")

             # Marcar el contenido como usado para no repetirlo
             self._mark_content_used(source_content)
        else:
             console.print("[red]Falló el ensamblaje[/red]")

    def _step_script(self, content: dict) -> Optional[dict]:
        """Generates script from RSS article or transcript."""
        console.print("[cyan]1. Adaptando Guión (Estilo Trend Hunter)...[/cyan]")
        
        # Determine source type
        transcript = content.get('transcript', '')
        article_text = content.get('content', '') or content.get('summary', '')
        
        source_text = ""
        if transcript and transcript != "[No transcription available]":
             source_text = f"TRANSCRIPCIÓN ORIGINAL:\n\"{transcript[:4000]}\""
        else:
             source_text = f"CONTENIDO ARTÍCULO (RSS):\n\"{article_text[:4000]}\""
        
        prompt = f"""
        Actúa como un experto en adaptar contenido viral al español.
        Toma este material exitoso y crea una versión MEJORADA y RESUMIDA para un Short/Reel de Mindfulness.
        
        {source_text}
        
        ESTRUCTURA OBLIGATORIA (Alta Retención):
        1. HOOK (0-5s): Una frase impactante basada en el contenido original.
        2. CUERPO (5-50s): Los mejores 3 consejos o la esencia del mensaje. Lenguaje simple, "bálsamo visual", extremadamente relajante.
        3. CALL TO ACTION (50-60s): Invitación suave.
        
        IMPORTANTE: Adapta todo al español neutro, tono calmado y profesional.
        
        Formato JSON esperado:
        {{
            "title": "Título en Español",
            "hook": "Texto del hook",
            "narration_text": "Texto completo del guión",
            "keywords": ["tag1", "tag2"], 
            "visual_mood": "calm" (o "nature", "deep")
        }}
        """
        
        script = self.llm.generate_script(prompt, source_url=content.get('url', ''))
        if script:
            console.print(f"[green]✓ Guión Adaptado: {script.get('title')}[/green]")
        return script

    def _step_audio(self, script: dict) -> Optional[dict]:
        console.print("[cyan]2. Generando Audio y Subtítulos...[/cyan]")
        return self.tts.synthesize_with_timing(
            script['narration_text'], 
            script.get('subtitles', []),
            f"mindfulness_{script.get('title', 'audio')}"
        )

    def _step_p5_visuals(self, duration: float, topic: str, audio_path: str, style: str = "particles", mood: str = "calm") -> Optional[str]:
        console.print(f"[cyan]6. Generando Arte Generativo ({style}/{mood})...[/cyan]")
        
        frames_dir = self.temp_dir / "p5_frames"
        if frames_dir.exists():
            import shutil
            shutil.rmtree(frames_dir)
        frames_dir.mkdir()

        # Analyze Audio
        import json
        from pydub import AudioSegment
        
        audio = AudioSegment.from_file(audio_path)
        fps = 30
        amplitudes = []
        
        # Extract RMS per frame
        for i in range(0, int(duration * fps)):
            start = i * 1000 / fps
            end = (i + 1) * 1000 / fps
            chunk = audio[start:end]
            if len(chunk) > 0:
                norm_rms = chunk.rms / 10000.0
                amplitudes.append(min(norm_rms, 2.0))
            else:
                amplitudes.append(0)
                
        audio_data_path = self.temp_dir / "audio_reactivity.json"
        with open(audio_data_path, "w") as f:
            json.dump(amplitudes, f)
        
        cmd = [
            "node", 
            str(Path(__file__).parent / "render_art.js"), 
            str(frames_dir), 
            str(duration), 
            style,
            mood,
            str(audio_data_path)
        ]
        
        import subprocess
        try:
            with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"), console=console) as progress:
                task = progress.add_task(f"Renderizando {int(duration)}s de arte...", total=None)
                result = subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                progress.update(task, description="[green]✓ Frames generados[/green]")

            # Convert to video
            output_vid = str(self.temp_dir / "p5_overlay.mp4")
            if self.assembler.frames_to_video(str(frames_dir), duration, output_vid):
                return output_vid
        except subprocess.CalledProcessError as e:
            console.print(f"[red]Error en Node.js: {e}[/red]")
            if e.stderr:
                console.print(f"[red]Detalles: {e.stderr}[/red]")
            return None
        return None


    def _step_hunt_trends(self, count: int) -> list[dict]:
        """
        Obtiene contenido para videos, priorizando caché sobre scraping.
        
        1. Primero busca en caché contenido pendiente
        2. Solo scrapea si no hay suficiente en caché
        3. Retorna contenido listo para procesar
        """
        console.print(f"[bold magenta]🌍 Buscando {count} Tendencias...[/bold magenta]")
        
        # 1. Primero buscar en caché
        console.print("[cyan]Revisando contenido pendiente en caché...[/cyan]")
        pending = self.cache.get_pending_content(source="rss")
        
        # Filtrar solo mindfulness/health
        keywords = ["mindfulness", "meditation", "ansiedad", "salud", "health", "bienestar", "relax", "yoga", "stoic", "mental"]
        
        relevant_pending = []
        for item in pending:
            text = (item.get("title", "") + " " + item.get("summary", "")).lower()
            if any(k in text for k in keywords):
                relevant_pending.append(item)
        
        if len(relevant_pending) >= count:
            console.print(f"[green]✓ Usando {count} artículos del caché ({len(relevant_pending)} disponibles)[/green]")
            return relevant_pending[:count]
        
        console.print(f"[yellow]Solo {len(relevant_pending)} en caché, scrapeando más...[/yellow]")
        
        # 2. Scrapear para obtener más contenido
        new_items = self._scrape_new_content()
        
        # Combinar pendientes + nuevos
        all_items = relevant_pending + new_items
        
        # Filtrar y mezclar
        import random
        random.shuffle(all_items)
        
        relevant = []
        for item in all_items:
            if len(relevant) >= count:
                break
            text = (item.get("title", "") + " " + item.get("summary", "")).lower()
            if any(k in text for k in keywords):
                relevant.append(item)
        
        console.print(f"[green]✓ Encontrados {len(relevant)} artículos relevantes[/green]")
        return relevant
    
    def _scrape_new_content(self) -> list[dict]:
        """Scrapea nuevo contenido de RSS y lo guarda en caché."""
        console.print("[cyan]📰 Scrapeando feeds RSS...[/cyan]")
        rss = RSSClient(cache=self.cache)
        items = rss.fetch_all()
        
        # Convertir a dicts si es necesario
        dict_items = []
        for item in items:
            if hasattr(item, "to_dict"):
                dict_items.append(item.to_dict())
            elif hasattr(item, "__dict__"):
                dict_items.append({
                    "title": getattr(item, "title", ""),
                    "summary": getattr(item, "summary", ""),
                    "url": getattr(item, "url", getattr(item, "link", "")),
                    "source": "rss"
                })
            else:
                dict_items.append(item)
        
        # Guardar en caché (esto también marca cuáles son nuevos)
        new_count = self.cache.store_scraped_content("rss", dict_items)
        console.print(f"[green]✓ {new_count} artículos nuevos guardados en caché[/green]")
        
        return dict_items
    
    def _mark_content_used(self, content: dict) -> None:
        """Marca un contenido como procesado para no repetirlo."""
        url = content.get("url", content.get("link", ""))
        if url:
            self.cache.mark_processed_by_url(url)
            console.print(f"[dim]Marcado como procesado: {url[:50]}...[/dim]")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Mindfulness Video Generator")
    parser.add_argument("--count", type=int, default=1, help="Number of videos to generate")
    
    args = parser.parse_args()
    
    pipeline = MindfulnessPipeline()
    
    # 1. Hunt Trends first
    viral_contents = pipeline._step_hunt_trends(args.count)
    
    if not viral_contents:
        console.print("[red]No se encontraron tendencias válidas[/red]")
        exit(1)
    
    console.print(f"\n[bold magenta]🧘 Generando {len(viral_contents)} Videos basados en tendencias[/bold magenta]")
    
    for i, content in enumerate(viral_contents):
        console.print(f"\n[bold]🎥 Generando Video {i+1}/{len(viral_contents)}: {content['title']}[/bold]")
        try:
            pipeline.generate_mindfulness_video(source_content=content)
        except Exception as e:
            console.print(f"[red]Error generando video {i+1}: {e}[/red]")
            import traceback
            traceback.print_exc()

    console.print(f"\n[bold green]✅ Proceso Completado[/bold green]")
