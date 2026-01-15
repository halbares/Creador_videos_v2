"""
Pipeline principal para orquestar todo el proceso de creación de videos.
Coordina scraping → LLM → TTS → Video.
"""

import logging
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn
from rich.panel import Panel

from .scraper import RSSClient, RedditClient, YouTubeClient, BlogScraper
from .llm import OpenRouterClient, ScriptValidator
from .tts.edge_tts import EdgeTTSEngine
from .video import SubtitleGenerator, VideoRenderer, PexelsClient
from .utils import ContentCache

load_dotenv()
logger = logging.getLogger(__name__)
console = Console()


class VideoPipeline:
    """Orquestador principal del pipeline de creación de videos."""
    
    def __init__(
        self,
        output_dir: str = "./output",
        temp_dir: str = "./temp",
        cache_dir: str = "./cache",
        assets_dir: str = "./assets"
    ):
        """
        Inicializa el pipeline.
        
        Args:
            output_dir: Directorio para videos finales
            temp_dir: Directorio para archivos temporales
            cache_dir: Directorio para cache
            assets_dir: Directorio para assets (fondos)
        """
        self.output_dir = Path(output_dir)
        self.temp_dir = Path(temp_dir)
        self.cache_dir = Path(cache_dir)
        self.assets_dir = Path(assets_dir)
        
        # Crear directorios
        for dir_path in [self.output_dir, self.temp_dir, self.cache_dir, self.assets_dir]:
            dir_path.mkdir(parents=True, exist_ok=True)
        
        # Inicializar componentes
        self.cache = ContentCache(str(self.cache_dir))
        self.validator = ScriptValidator()
        
        # Componentes lazy-loaded
        self._llm_client = None
        self._tts_engine = None
        self._subtitle_gen = None
        self._renderer = None
        self._pexels = None
    
    @property
    def llm_client(self) -> OpenRouterClient:
        if self._llm_client is None:
            self._llm_client = OpenRouterClient(cache=self.cache)
        return self._llm_client
    
    @property
    def tts_engine(self) -> EdgeTTSEngine:
        if self._tts_engine is None:
            # Usar Edge-TTS con voz colombiana masculina
            self._tts_engine = EdgeTTSEngine(
                output_dir=str(self.temp_dir),
                voice="es-CO-GonzaloNeural"  # Gonzalo de Colombia
            )
        return self._tts_engine
    
    @property
    def subtitle_gen(self) -> SubtitleGenerator:
        if self._subtitle_gen is None:
            self._subtitle_gen = SubtitleGenerator(output_dir=str(self.temp_dir))
        return self._subtitle_gen
    
    @property
    def renderer(self) -> VideoRenderer:
        if self._renderer is None:
            self._renderer = VideoRenderer(
                output_dir=str(self.output_dir),
                temp_dir=str(self.temp_dir)
            )
        return self._renderer
    
    @property
    def pexels(self) -> PexelsClient:
        if self._pexels is None:
            self._pexels = PexelsClient(assets_dir=str(self.assets_dir))
        return self._pexels
    
    def _generate_video_metadata(
        self,
        video_folder: Path,
        script: dict,
        video_filename: str
    ) -> str:
        """
        Genera archivo metadata.md con info para redes sociales.
        
        Args:
            video_folder: Carpeta del video
            script: Guión con título, keywords, etc.
            video_filename: Nombre del archivo de video
            
        Returns:
            Ruta al archivo metadata.md
        """
        title = script.get("title", "Video de Bienestar")
        keywords = script.get("keywords", ["bienestar", "salud", "vida sana"])
        narration = script.get("narration_text", "")
        source_url = script.get("source_url", "")
        hooks = script.get("hooks_alternativos", [])
        
        # Generar descripción SEO atractiva
        # Tomar el hook y primeras líneas de la narración
        first_hook = hooks[0] if hooks else title
        narration_preview = narration[:200] + "..." if len(narration) > 200 else narration
        
        description = f"""{first_hook}

{narration_preview}

✨ Si este contenido te ayudó, ¡dale like y comparte!
🔔 Sígueme para más tips de bienestar diario.
💬 Cuéntame en los comentarios: ¿qué tema te gustaría ver?"""
        
        # Generar hashtags (máximo 30 para Instagram, 5 principales para TikTok)
        base_hashtags = [
            "bienestar", "saludable", "vidaSana", "wellness", "salud",
            "habitosSaludables", "motivacion", "crecimientoPersonal",
            "mindfulness", "autocuidado", "tips", "consejosdevida"
        ]
        
        # Agregar keywords del script como hashtags
        keyword_hashtags = [kw.replace(" ", "").replace("-", "") for kw in keywords[:5]]
        
        all_hashtags = keyword_hashtags + base_hashtags
        # Limitar a 20 hashtags únicos
        unique_hashtags = list(dict.fromkeys(all_hashtags))[:20]
        
        hashtags_str = " ".join([f"#{tag}" for tag in unique_hashtags])
        
        # Crear contenido del archivo
        metadata_content = f"""# {title}

## 📹 Archivo de Video
`{video_filename}`

---

## 📝 Descripción para Redes Sociales

{description}

---

## 🏷️ Hashtags

### Para TikTok/Reels (Top 5)
{" ".join([f"#{tag}" for tag in unique_hashtags[:5]])}

### Para Instagram/YouTube (Completos)
{hashtags_str}

---

## 🎣 Hooks Alternativos
Usa estos hooks para versiones del video o para probar engagement:

"""
        for i, hook in enumerate(hooks, 1):
            metadata_content += f"{i}. {hook}\n"
        
        metadata_content += f"""
---

## 📊 Keywords SEO
{", ".join(keywords)}

---

## 🔗 Fuente Original
{source_url if source_url else "Contenido original"}

---

*Generado automáticamente por Creador de Videos Virales*
*Fecha: {datetime.now().strftime("%Y-%m-%d %H:%M")}*
"""
        
        # Guardar archivo
        metadata_path = video_folder / "metadata.md"
        with open(metadata_path, "w", encoding="utf-8") as f:
            f.write(metadata_content)
        
        return str(metadata_path)
    
    def step_scrape(self, sources: Optional[list[str]] = None) -> list[dict]:
        """
        Paso 1: Obtener contenido de fuentes.
        
        Args:
            sources: Lista de fuentes (rss, reddit, youtube, blogs) o None para todas
            
        Returns:
            Lista de contenido obtenido
        """
        console.print(Panel("[bold cyan]PASO 1: Obteniendo contenido[/bold cyan]"))
        
        all_content = []
        sources = sources or ["rss", "reddit", "youtube", "blogs"]
        
        scrapers = {
            "rss": RSSClient(cache=self.cache),
            "reddit": RedditClient(cache=self.cache),
            "youtube": YouTubeClient(cache=self.cache),
            "blogs": BlogScraper(cache=self.cache),
        }
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            console=console
        ) as progress:
            for source in sources:
                if source not in scrapers:
                    continue
                
                task = progress.add_task(f"Scraping {source}...", total=None)
                
                try:
                    scraper = scrapers[source]
                    items = scraper.fetch_all()
                    
                    for item in items:
                        all_content.append(item.to_dict() if hasattr(item, "to_dict") else item)
                    
                    progress.update(task, description=f"[green]✓ {source}: {len(items)} items")
                    
                except Exception as e:
                    logger.error(f"Error scraping {source}: {e}")
                    progress.update(task, description=f"[red]✗ {source}: error")
        
        console.print(f"\n[green]Total: {len(all_content)} items obtenidos[/green]\n")
        return all_content
    
    def step_generate_script(
        self,
        content: Optional[dict] = None,
        from_cache: bool = False
    ) -> Optional[dict]:
        """
        Paso 2: Generar guión con LLM.
        
        Args:
            content: Contenido específico a procesar
            from_cache: Si usar contenido del cache
            
        Returns:
            Guión generado o None
        """
        console.print(Panel("[bold cyan]PASO 2: Generando guión[/bold cyan]"))
        
        if from_cache:
            pending = self.cache.get_pending_content()
            if not pending:
                console.print("[yellow]No hay contenido pendiente en cache[/yellow]")
                return None
            content = pending[0]
        
        if not content:
            console.print("[red]No hay contenido para procesar[/red]")
            return None
        
        # Construir texto para el LLM
        text_parts = []
        if content.get("title"):
            text_parts.append(f"Título: {content['title']}")
        if content.get("summary"):
            text_parts.append(f"Resumen: {content['summary']}")
        elif content.get("content"):
            text_parts.append(f"Contenido: {content['content']}")
        if content.get("top_comments"):
            text_parts.append(f"Comentarios: {' | '.join(content['top_comments'][:3])}")
        
        source_text = "\n\n".join(text_parts)
        source_url = content.get("url", "")
        
        console.print(f"[dim]Procesando: {content.get('title', 'Sin título')[:60]}...[/dim]")
        
        with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"), console=console) as progress:
            task = progress.add_task("Generando guión con LLM...", total=None)
            
            script = self.llm_client.generate_script(source_text, source_url)
            
            if script:
                progress.update(task, description="[green]✓ Guión generado")
            else:
                progress.update(task, description="[red]✗ Error generando guión")
                return None
        
        # Validar guión
        result = self.validator.validate(script)
        
        if not result.is_valid:
            console.print("[red]Errores en el guión:[/red]")
            for error in result.errors:
                console.print(f"  • {error}")
            
            # Intentar corregir
            script = self.validator.fix_common_issues(script)
            result = self.validator.validate(script)
        
        if result.warnings:
            console.print("[yellow]Advertencias:[/yellow]")
            for warning in result.warnings[:3]:
                console.print(f"  • {warning}")
        
        # Mostrar hooks para selección
        hooks = script.get("hooks_alternativos", [])
        if hooks:
            console.print("\n[cyan]Hooks alternativos disponibles:[/cyan]")
            for i, hook in enumerate(hooks, 1):
                text = hook.get("text", hook) if isinstance(hook, dict) else hook
                console.print(f"  {i}. {text}")
        
        # Guardar en cache
        import hashlib
        script_id = hashlib.sha256(source_url.encode()).hexdigest()[:12]
        self.cache.store_script(script_id, script)
        script["_id"] = script_id
        script["source_url"] = source_url  # Guardar URL para metadata
        
        # Marcar contenido como procesado para no repetirlo
        content_url = content.get("url", "")
        if content_url:
            # Primero intentar con source si existe
            content_source = content.get("source", "")
            if content_source:
                self.cache.mark_processed(content_source, content_url)
            else:
                # Si no hay source, buscar en todas las fuentes
                self.cache.mark_processed_by_url(content_url)
            console.print(f"[dim]✓ Contenido marcado como procesado[/dim]")
        
        console.print(f"\n[green]Guión guardado con ID: {script_id}[/green]\n")
        return script
    
    def step_generate_audio(
        self,
        script: dict,
        script_id: Optional[str] = None
    ) -> Optional[dict]:
        """
        Paso 3: Generar audio con XTTS.
        
        Args:
            script: Guión con narration_text y subtitles
            script_id: ID para nombrar el archivo
            
        Returns:
            Dict con audio_path, duration, subtitles ajustados
        """
        console.print(Panel("[bold cyan]PASO 3: Generando audio[/bold cyan]"))
        
        narration = script.get("narration_text", "")
        if not narration:
            console.print("[red]No hay texto de narración[/red]")
            return None
        
        script_id = script_id or script.get("_id", "audio")
        subtitles = script.get("subtitles", [])
        
        # El TTS ahora muestra su propio progreso detallado
        result = self.tts_engine.synthesize_with_timing(
            narration, subtitles, f"audio_{script_id}"
        )
        
        if not result:
            console.print("[red]✗ Error generando audio[/red]")
            return None
        
        console.print(f"[green]Duración final: {result['duration']:.2f}s[/green]\n")
        
        return result
    
    def step_get_background(
        self,
        keywords: list[str],
        prefer_video: bool = True
    ) -> Optional[str]:
        """
        Paso 4: Obtener fondo de Pexels.
        
        Args:
            keywords: Palabras clave para buscar
            prefer_video: Si preferir video sobre imagen
            
        Returns:
            Ruta al archivo de fondo
        """
        console.print(Panel("[bold cyan]PASO 4: Obteniendo fondo[/bold cyan]"))
        
        console.print(f"[dim]Keywords: {', '.join(keywords[:3])}[/dim]")
        
        with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"), console=console) as progress:
            task = progress.add_task("Buscando en Pexels...", total=None)
            
            media_type = "video" if prefer_video else "photo"
            path = self.pexels.get_random_background(keywords, media_type)
            
            if path:
                progress.update(task, description=f"[green]✓ {media_type.title()} descargado")
            else:
                progress.update(task, description="[yellow]! Intentando con imagen...")
                path = self.pexels.get_random_background(keywords, "photo")
        
        if path:
            console.print(f"[green]Fondo: {path}[/green]\n")
        else:
            console.print("[yellow]No se encontró fondo, usando color sólido[/yellow]\n")
        
        return path
    
    def step_render_video(
        self,
        audio_path: str,
        background_path: Optional[str],
        subtitles: list[dict],
        script_id: str,
        image_effect: str = "zoom"
    ) -> Optional[str]:
        """
        Paso 5: Renderizar video final.
        
        Args:
            audio_path: Ruta al audio
            background_path: Ruta al fondo (o None para color sólido)
            subtitles: Lista de subtítulos con timings
            script_id: ID para nombrar archivos
            image_effect: Efecto para imágenes (zoom, pan, kenburns)
            
        Returns:
            Ruta al video final
        """
        console.print(Panel("[bold cyan]PASO 5: Renderizando video[/bold cyan]"))
        
        # Generar subtítulos ASS
        console.print("[dim]Generando subtítulos...[/dim]")
        subs_path = self.subtitle_gen.generate_animated(
            subtitles, f"subs_{script_id}", animation="fade"
        )
        
        if not subs_path:
            console.print("[red]Error generando subtítulos[/red]")
            return None
        
        # Determinar tipo de fondo
        is_image = False
        if background_path:
            is_image = background_path.lower().endswith((".jpg", ".jpeg", ".png", ".webp"))
        else:
            # Crear fondo de color
            from pydub import AudioSegment
            audio = AudioSegment.from_file(audio_path)
            duration = len(audio) / 1000.0
            background_path = self.renderer.create_color_background(duration)
        
        # Renderizar
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_name = f"video_{script_id}_{timestamp}"
        
        with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"), console=console) as progress:
            task = progress.add_task("Renderizando con FFmpeg...", total=None)
            
            video_path = self.renderer.render_final(
                audio_path,
                background_path,
                subs_path,
                output_name,
                is_background_image=is_image,
                image_effect=image_effect
            )
            
            if video_path:
                progress.update(task, description="[green]✓ Video renderizado")
            else:
                progress.update(task, description="[red]✗ Error renderizando")
        
        if video_path:
            console.print(f"\n[bold green]🎬 Video final: {video_path}[/bold green]\n")
        
        return video_path
    
    def run_full_pipeline(
        self,
        sources: Optional[list[str]] = None,
        prefer_video_bg: bool = True,
        image_effect: str = "zoom",
        skip_scrape: bool = False
    ) -> Optional[str]:
        """
        Ejecuta el pipeline completo para UN video.
        
        Args:
            sources: Fuentes de scraping
            prefer_video_bg: Si preferir video sobre imagen de fondo
            image_effect: Efecto para imágenes de fondo
            skip_scrape: Si saltar el paso de scraping
            
        Returns:
            Ruta al video final o None
        """
        console.print(Panel(
            "[bold magenta]🚀 PIPELINE COMPLETO[/bold magenta]\n"
            "Scraping → LLM → TTS → Video",
            title="Creador de Videos Virales"
        ))
        
        try:
            # Paso 1: Scraping (opcional)
            if not skip_scrape:
                content = self.step_scrape(sources)
                
                if not content:
                    console.print("[yellow]No se obtuvo contenido nuevo. Usando cache...[/yellow]")
            
            # Paso 2: Generar guión
            script = self.step_generate_script(from_cache=True)
            
            if not script:
                console.print("[red]No se pudo generar el guión[/red]")
                return None
            
            script_id = script.get("_id", "video")
            
            # Paso 3: Generar audio
            audio_result = self.step_generate_audio(script, script_id)
            
            if not audio_result:
                console.print("[red]No se pudo generar el audio[/red]")
                return None
            
            # Paso 4: Obtener fondo
            keywords = script.get("keywords", ["wellness", "health", "calm"])
            background = self.step_get_background(keywords, prefer_video_bg)
            
            # Paso 5: Renderizar
            video_path = self.step_render_video(
                audio_result["audio_path"],
                background,
                audio_result["subtitles"],
                script_id,
                image_effect
            )
            
            if not video_path:
                console.print("[red]No se pudo renderizar el video[/red]")
                return None
            
            # Paso 6: Crear carpeta del video y metadata
            console.print(Panel("[bold cyan]PASO 6: Organizando archivos[/bold cyan]"))
            
            # Crear nombre de carpeta legible basado en el título
            import unicodedata
            title = script.get("title", "video")
            
            # Convertir título a slug legible
            slug = unicodedata.normalize("NFKD", title)
            slug = slug.encode("ascii", "ignore").decode("ascii")  # Remover acentos
            slug = re.sub(r"[^\w\s-]", "", slug)  # Solo letras, números, espacios, guiones
            slug = re.sub(r"[\s_]+", "_", slug)  # Espacios a guiones bajos
            slug = slug.strip("_").lower()[:50]  # Limitar longitud
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            video_folder_name = f"{slug}_{timestamp}"
            video_folder = self.output_dir / video_folder_name
            video_folder.mkdir(parents=True, exist_ok=True)
            
            # Mover video a la carpeta
            import shutil
            video_filename = Path(video_path).name
            new_video_path = video_folder / video_filename
            shutil.move(video_path, new_video_path)
            
            # Generar metadata.md
            metadata_path = self._generate_video_metadata(video_folder, script, video_filename)
            
            console.print(f"[green]✓ Carpeta creada: {video_folder}[/green]")
            console.print(f"[green]✓ Metadata generada: {metadata_path}[/green]")
            console.print(f"\n[bold green]🎬 Video listo: {new_video_path}[/bold green]\n")
            
            return str(new_video_path)
            
        except KeyboardInterrupt:
            console.print("\n[yellow]Pipeline cancelado por el usuario[/yellow]")
            return None
        except Exception as e:
            logger.exception("Error en pipeline")
            console.print(f"\n[red]Error: {e}[/red]")
            return None
    
    def run_batch_pipeline(
        self,
        count: int = 1,
        sources: Optional[list[str]] = None,
        prefer_video_bg: bool = True,
        image_effect: str = "zoom",
        process_all_pending: bool = False
    ) -> list[str]:
        """
        Ejecuta el pipeline para múltiples videos.
        
        Args:
            count: Número de videos a generar
            sources: Fuentes de scraping
            prefer_video_bg: Si preferir video sobre imagen de fondo
            image_effect: Efecto para imágenes de fondo
            process_all_pending: Si procesar todo el cache pendiente
            
        Returns:
            Lista de rutas a videos generados
        """
        generated_videos = []
        
        console.print(Panel(
            f"[bold magenta]🎬 MODO BATCH[/bold magenta]\n"
            f"{'Procesando TODO el cache pendiente' if process_all_pending else f'Generando {count} video(s)'}",
            title="Creador de Videos Virales"
        ))
        
        # Paso 1: Scraping (solo una vez)
        console.print("\n[bold cyan]Fase 1: Obteniendo contenido...[/bold cyan]")
        self.step_scrape(sources)
        
        # Determinar cuántos videos procesar
        pending = self.cache.get_pending_content()
        
        if process_all_pending:
            videos_to_generate = len(pending)
            console.print(f"[yellow]Contenido pendiente: {videos_to_generate} items[/yellow]")
        else:
            videos_to_generate = min(count, len(pending))
        
        if videos_to_generate == 0:
            console.print("[red]No hay contenido pendiente para procesar[/red]")
            return []
        
        console.print(f"\n[bold green]Generando {videos_to_generate} video(s)...[/bold green]\n")
        
        # Generar videos
        for i in range(videos_to_generate):
            console.print(Panel(
                f"[bold yellow]VIDEO {i + 1} de {videos_to_generate}[/bold yellow]",
                style="yellow"
            ))
            
            try:
                # Ejecutar pipeline sin scraping (ya lo hicimos)
                video_path = self.run_full_pipeline(
                    sources=sources,
                    prefer_video_bg=prefer_video_bg,
                    image_effect=image_effect,
                    skip_scrape=True  # No repetir scraping
                )
                
                if video_path:
                    generated_videos.append(video_path)
                    console.print(f"[green]✓ Video {i + 1} completado: {video_path}[/green]\n")
                else:
                    console.print(f"[red]✗ Video {i + 1} falló[/red]\n")
                    
            except KeyboardInterrupt:
                console.print("\n[yellow]Batch cancelado por el usuario[/yellow]")
                break
            except Exception as e:
                logger.error(f"Error en video {i + 1}: {e}")
                console.print(f"[red]Error en video {i + 1}: {e}[/red]\n")
        
        # Resumen final
        console.print(Panel(
            f"[bold green]🎉 BATCH COMPLETADO[/bold green]\n"
            f"Videos generados: {len(generated_videos)} de {videos_to_generate}\n"
            f"Ubicación: {self.output_dir}",
            title="Resumen"
        ))
        
        for path in generated_videos:
            console.print(f"  🎬 {path}")
        
        return generated_videos
    
    def get_pending_count(self) -> int:
        """Retorna la cantidad de contenido pendiente en cache."""
        return len(self.cache.get_pending_content())
    
    def close(self):
        """Limpia recursos."""
        if self._pexels:
            self._pexels.close()
        self.cache.close()


def main():
    """Punto de entrada CLI."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Creador de Videos Virales - Pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument("--full", action="store_true", help="Ejecutar pipeline completo (1 video)")
    parser.add_argument("--count", type=int, default=1, help="Número de videos a generar")
    parser.add_argument("--batch", action="store_true", help="Modo batch: procesar TODO el cache pendiente")
    parser.add_argument("--scrape", action="store_true", help="Solo scraping")
    parser.add_argument("--script", action="store_true", help="Solo generar guión desde cache")
    parser.add_argument("--pending", action="store_true", help="Mostrar cantidad de contenido pendiente")
    parser.add_argument("--sources", nargs="+", help="Fuentes para scraping (rss reddit youtube blogs)")
    parser.add_argument("--video-bg", action="store_true", default=True, help="Preferir video de fondo")
    parser.add_argument("--image-bg", action="store_true", help="Preferir imagen de fondo")
    parser.add_argument("--effect", choices=["zoom", "pan", "kenburns"], default="zoom",
                       help="Efecto para imágenes de fondo")
    
    args = parser.parse_args()
    
    pipeline = VideoPipeline()
    
    try:
        if args.pending:
            count = pipeline.get_pending_count()
            console.print(f"[cyan]Contenido pendiente en cache: {count} items[/cyan]")
            return
        
        prefer_video = not args.image_bg
        
        if args.batch:
            # Modo batch: procesar todo el cache
            pipeline.run_batch_pipeline(
                process_all_pending=True,
                sources=args.sources,
                prefer_video_bg=prefer_video,
                image_effect=args.effect
            )
        elif args.full or args.count > 1:
            # Con --count o --full
            if args.count > 1:
                pipeline.run_batch_pipeline(
                    count=args.count,
                    sources=args.sources,
                    prefer_video_bg=prefer_video,
                    image_effect=args.effect
                )
            else:
                pipeline.run_full_pipeline(
                    sources=args.sources,
                    prefer_video_bg=prefer_video,
                    image_effect=args.effect
                )
        elif args.scrape:
            pipeline.step_scrape(args.sources)
        elif args.script:
            pipeline.step_generate_script(from_cache=True)
        else:
            parser.print_help()
    finally:
        pipeline.close()


if __name__ == "__main__":
    main()
