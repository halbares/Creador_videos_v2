"""
Pipeline principal para orquestar todo el proceso de creación de videos.
Coordina scraping → LLM → TTS → Video.
"""

import logging
import os
import re
import random
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
from rich.panel import Panel

from .scraper import RSSClient, RedditClient, YouTubeClient, BlogScraper
from .llm import OpenRouterClient, ScriptValidator, SceneGenerator
from .tts.edge_tts import EdgeTTSEngine
from .video import SubtitleGenerator, VideoRenderer, PexelsClient
from .utils import ContentCache
from .publisher import CloudUploader, MakeWebhookClient, RetryQueue

load_dotenv()
logger = logging.getLogger(__name__)
console = Console()


class VideoPipeline:
    """Orquestador principal del pipeline de creación de videos."""
    
    WIDTH = 1080
    HEIGHT = 1920
    FPS = 30
    
    def __init__(
        self,
        output_dir: str = "./output",
        temp_dir: str = "./temp",
        cache_dir: str = "./cache",
        assets_dir: str = "./assets",
        tts_engine: str = "edge"
    ):
        """
        Inicializa el pipeline de video.
        Args:
            output_dir: Directorio para videos finales
            temp_dir: Directorio para archivos temporales
            cache_dir: Directorio para cache
            assets_dir: Directorio para assets (fondos)
            tts_engine: Motor de TTS a usar ('edge' o 'xtts')
        """
        self.output_dir = Path(output_dir)
        self.temp_dir = Path(temp_dir)
        self.cache_dir = Path(cache_dir)
        self.assets_dir = Path(assets_dir)
        self.tts_engine_type = tts_engine
        
        # Crear directorios
        for dir_path in [self.output_dir, self.temp_dir, self.cache_dir, self.assets_dir]:
            dir_path.mkdir(parents=True, exist_ok=True)
            
        # Cargar configuración
        self.config = self._load_config()
        
        # Inicializar componentes
        self.cache = ContentCache()
        self.llm = OpenRouterClient()
        self.scene_generator = SceneGenerator(self.llm)
        self.validator = ScriptValidator()
        
        # Componentes lazy-loaded
        self._llm_client = None
        self._tts_engine = None
        self._subtitle_gen = None
        self._renderer = None
        self._pexels = None
        self._uploader = None
        self._webhook = None
        self._retry_queue = None
    def _load_config(self) -> dict:
        """Carga la configuración del pipeline."""
        import yaml
        config_path = Path("config/config.yaml")
        if config_path.exists():
            with open(config_path, "r") as f:
                return yaml.safe_load(f)
        return {}

    @property
    def llm_client(self) -> OpenRouterClient:
        if self._llm_client is None:
            self._llm_client = OpenRouterClient(cache=self.cache)
        return self._llm_client

    @property
    def tts_engine(self):
        if self._tts_engine is None:
            if self.tts_engine_type == "xtts":
                from .tts.xtts import XTTSEngine
                logger.info("Usando motor TTS Pro (XTTS v2)")
                self._tts_engine = XTTSEngine(
                    output_dir=str(self.temp_dir),
                    language="es"
                )
            else:
                from .tts.edge_tts import EdgeTTSEngine
                # Usar Edge-TTS con voz chilena
                logger.info("Usando motor TTS Rápido (Edge-TTS Chile)")
                self._tts_engine = EdgeTTSEngine(
                    output_dir=str(self.temp_dir),
                    voice="es-CL-LorenzoNeural"
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
    
    @property
    def uploader(self) -> CloudUploader:
        if self._uploader is None:
            self._uploader = CloudUploader()
        return self._uploader
    
    @property
    def webhook(self) -> MakeWebhookClient:
        if self._webhook is None:
            self._webhook = MakeWebhookClient()
        return self._webhook
    
    @property
    def retry_queue(self) -> RetryQueue:
        if self._retry_queue is None:
            self._retry_queue = RetryQueue(str(self.cache_dir))
        return self._retry_queue
    
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
        
        
        description = f"{first_hook}\n\n{narration_preview}\n\n" \
                     f"Si este contenido te ayudó, ¡dale like y comparte!\n" \
                     f"Sígueme para más tips de bienestar diario.\n" \
                     f"Cuéntame en los comentarios: ¿qué tema te gustaría ver?"
        
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
        # Crear contenido usando lista para evitar errores de comillas triples
        lines = [
            f"# {title}",
            "",
            "## 📹 Archivo de Video",
            f"`{video_filename}`",
            "",
            "---",
            "",
            "## 📝 Descripción para Redes Sociales",
            "",
            description,
            "",
            "---",
            "",
            "## 🏷️ Hashtags",
            "",
            "### Para TikTok/Reels (Top 5)",
            " ".join([f"#{tag}" for tag in unique_hashtags[:5]]),
            "",
            "### Para Instagram/YouTube (Completos)",
            hashtags_str,
            "",
            "---",
            "",
            "## 🎣 Hooks Alternativos",
            "Usa estos hooks para versiones del video o para probar engagement:",
            ""
        ]
        
        for i, hook in enumerate(hooks, 1):
            lines.append(f"{i}. {hook}")
            
        lines.extend([
            "",
            "---",
            "",
            "## 📊 Keywords SEO",
            ", ".join(keywords),
            "",
            "---",
            "",
            "## 🔗 Fuente Original",
            source_url if source_url else "Contenido original",
            "",
            "---",
            "",
            "*Generado automáticamente por Creador de Videos Virales*",
            f"*Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M')}*",
            ""
        ])
        
        metadata_content = "\n".join(lines)
        
        # Guardar archivo
        metadata_path = video_folder / "metadata.md"
        with open(metadata_path, "w", encoding="utf-8") as f:
            f.write(metadata_content)
        
        return str(metadata_path)
    
    def step_scrape(self, sources: Optional[list[str]] = None) -> list[dict]:
        """
        Paso 1: Obtener contenido de fuentes seleccionadas.
        Si hay suficiente contenido en cache, NO hace scraping (a menos que se fuerce).
        """
        # Verificar contenido pendiente
        pending_count = self.cache.get_pending_count()
        if pending_count >= 5 and not sources:
            console.print(f"[green]✓ Usando contenido en cache ({pending_count} items pendientes)[/green]")
            return self.cache.get_pending_content()

        console.print(Panel("[bold cyan]PASO 1: Obteniendo contenido[/bold cyan]"))
        
        all_content = []
        
        # Default sources (sin YouTube por lentitud)
        if not sources:
            sources = ["rss", "reddit", "blogs"]
            
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            console=console
        ) as progress:
            
            # RSS
            if "rss" in sources or "all" in sources:
                task = progress.add_task("Scraping rss...", total=None)
                try:
                    rss_client = RSSClient(cache=self.cache)
                    items = rss_client.fetch_all()
                    all_content.extend(items)
                    progress.update(task, description=f"[green]✓ rss: {len(items)} items")
                except Exception as e:
                    logger.error(f"Error scraping RSS: {e}")
            
            # Reddit
            if "reddit" in sources or "all" in sources:
                task = progress.add_task("Scraping reddit...", total=None)
                try:
                    reddit_client = RedditClient(cache=self.cache)
                    items = reddit_client.fetch_top_posts(limit=15) 
                    all_content.extend(items)
                    progress.update(task, description=f"[green]✓ reddit: {len(items)} items")
                except Exception as e:
                    logger.error(f"Error scraping Reddit: {e}")

            # Blogs
            if "blogs" in sources or "all" in sources:
                task = progress.add_task("Scraping blogs...", total=None)
                try:
                    blog_scraper = BlogScraper(cache=self.cache)
                    items = blog_scraper.scrape_configured_blogs()
                    all_content.extend(items)
                    progress.update(task, description=f"[green]✓ blogs: {len(items)} items")
                except Exception as e:
                    logger.error(f"Error scraping Blogs: {e}")
            
            # YouTube (Solo si se pide explícitamente)
            if sources and "youtube" in sources: 
                task = progress.add_task("Scraping youtube...", total=None)
                try:
                    yt_client = YouTubeClient(cache=self.cache)
                    items = yt_client.search_videos("wellness tips", limit=3)
                    all_content.extend(items)
                    progress.update(task, description=f"[green]✓ youtube: {len(items)} items")
                except Exception as e:
                    logger.error(f"Error scraping YouTube: {e}")
        
        console.print(f"\n[green]Total: {len(all_content)} items obtenidos[/green]\n")
        return all_content
    
    def step_get_scene_assets(
        self,
        scenes: list[dict],
        prefer_video: bool = True
    ) -> list[str]:
        """
        Paso 4: Obtener fondos para cada escena.
        
        Args:
            scenes: Lista de escenas con visual_keywords
            prefer_video: Si preferir video
            
        Returns:
            Lista de rutas a archivos de fondo (uno por escena)
        """
        console.print(Panel(f"[bold cyan]PASO 4: Obteniendo fondos para {len(scenes)} escenas[/bold cyan]"))
        
        background_paths = []
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            console=console
        ) as progress:
            task = progress.add_task("Descargando assets...", total=len(scenes))
            
            for i, scene in enumerate(scenes):
                keywords = scene.get("visual_keywords", [])
                if not keywords:
                    keywords = ["abstract", "background"]
                
                progress.update(task, description=f"Escena {i+1}: {', '.join(keywords[:2])}...")
                
                # Intentar obtener video único
                media_type = "video" if prefer_video else "photo"
                path = self.pexels.get_random_background(keywords, media_type)
                
                if not path:
                    # Fallback
                    path = self.pexels.get_random_background(keywords, "photo")
                
                if path:
                    background_paths.append(path)
                else:
                    logger.warning(f"No se encontró fondo para escena {i}")
                    # Usar el anterior o uno genérico
                    if background_paths:
                        background_paths.append(background_paths[-1])
                    else:
                        background_paths.append(None) # El renderer manejará esto
                
                progress.advance(task)
        
        console.print(f"[green]✓ {len(background_paths)} fondos obtenidos[/green]\n")
        return background_paths

    def step_generate_script(
        self,
        content: Optional[dict] = None,
        from_cache: bool = False
    ) -> Optional[dict]:
        """
        Paso 2: Generar guión con LLM.
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
        
        if content.get("transcript"):
            text_parts.append(f"Transcripción del video:\n{content['transcript']}")
        elif content.get("content"):
            text_parts.append(f"Contenido: {content['content']}")
        elif content.get("summary"):
            text_parts.append(f"Resumen: {content['summary']}")
            
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
        
        # Validar y corregir estructura de escenas
        if "scenes" not in script:
            console.print("[yellow]Guión sin escenas, generando estructura simple...[/yellow]")
            script["scenes"] = [{
                "narration_chunk": script.get("narration_text", ""),
                "visual_keywords": script.get("keywords", [])
            }]
        
        # Reconstruir narration_text desde escenas si es necesario
        if not script.get("narration_text"):
            script["narration_text"] = " ".join([s.get("narration_chunk", "") for s in script["scenes"]])
        
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
        script["source_url"] = source_url
        
        # Marcar contenido como procesado
        content_url = content.get("url", "")
        if content_url:
            content_source = content.get("source", "")
            if content_source:
                self.cache.mark_processed(content_source, content_url)
            else:
                self.cache.mark_processed_by_url(content_url)
        
        console.print(f"\n[green]Guión guardado con ID: {script_id}[/green]\n")
        return script
    
    def _get_random_clip_from_folder(self, folder_name: str) -> Optional[str]:
        """Obtiene un video aleatorio de una carpeta en assets."""
        folder = self.assets_dir / folder_name
        if not folder.exists():
            return None
            
        videos = list(folder.glob("*.mp4")) + list(folder.glob("*.mov"))
        if not videos:
            return None
            
        return str(random.choice(videos))
    
    def step_generate_audio(
        self,
        script: dict,
        script_id: Optional[str] = None
    ) -> Optional[dict]:
        """
        Paso 3: Generar audio con XTTS/Edge.
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

    def step_render_video(
        self,
        audio_path: str,
        background_paths: list[str],
        subtitles: list[dict],
        script_id: str,
        scenes: list[dict] = None,
        image_effect: str = "zoom"
    ) -> Optional[str]:
        """
        Paso 5: Renderizar video final (multi-escena + Intro/Outro).
        """
        console.print(Panel("[bold cyan]PASO 5: Renderizando video (Multi-Escena)[/bold cyan]"))
        
        # 1. Buscar Intro y Outro
        # Restauro intros/outros y busco su texto asociado para subtítulos
        intro_path = self._get_random_clip_from_folder("intros")
        outro_path = self._get_random_clip_from_folder("outros")
        
        intro_dur = 0.0
        outro_dur = 0.0
        intro_text = ""
        outro_text = ""
        
        if intro_path:
            intro_dur = self.renderer.get_duration(intro_path)
            # Buscar texto
            txt_path = Path(intro_path).with_suffix(".txt")
            if txt_path.exists():
                with open(txt_path, "r", encoding="utf-8") as f:
                    intro_text = f.read().strip()
            else:
                intro_text = "Bienvenidos" # Default
                
            console.print(f"[green]✓ Intro encontrada ({intro_dur:.1f}s): {Path(intro_path).name}[/green]")
            
        if outro_path:
            outro_dur = self.renderer.get_duration(outro_path)
            # Buscar texto
            txt_path = Path(outro_path).with_suffix(".txt")
            if txt_path.exists():
                with open(txt_path, "r", encoding="utf-8") as f:
                    outro_text = f.read().strip()
            else:
                outro_text = "Sígueme para más" # Default
                
            console.print(f"[green]✓ Outro encontrada ({outro_dur:.1f}s): {Path(outro_path).name}[/green]")
            
        # 2. Ajustar Audio (padding de silencio)
        final_audio_path = audio_path
        if intro_dur > 0 or outro_dur > 0:
            console.print("[dim]Ajustando timeline de audio (Intro/Outro)...[/dim]")
            final_audio_path = str(self.temp_dir / f"audio_padding_{script_id}.mp3")
            
            # Usar la nueva función que preserva el audio de la intro
            if not self.renderer.combine_audio_with_intro(
                audio_path, intro_path, outro_path, final_audio_path
            ):
                console.print("[red]Error mezclando audio de intro[/red]")
                return None
        
        # 3. Ajustar Subtítulos (offset + inyección)
        final_subtitles = []
        
        # A) Subtítulo de Intro
        if intro_dur > 0 and intro_text:
            final_subtitles.append({
                "start": 0.0,
                "end": intro_dur - 0.5, # Un poco menos para no encimar
                "text": intro_text
            })
            
        # B) Subtítulos principales desplazados
        if intro_dur > 0:
            console.print(f"[dim]Desplazando subtítulos +{intro_dur:.1f}s...[/dim]")
            for sub in subtitles:
                new_sub = sub.copy()
                new_sub["start"] += intro_dur
                new_sub["end"] += intro_dur
                final_subtitles.append(new_sub)
        else:
            final_subtitles.extend(subtitles)
            
        # C) Subtítulo de Outro
        if outro_dur > 0 and outro_text:
            # Calcular fin total
            # El audio final ya incluye outro, así que calculamos en base al start del último sub o duración de narración
            # Mejor estimación: intro_dur + audio_duration (sin outro)
            # Pero no tengo audio_duration aquí fácil. 
            # Uso el final del último subtítulo como referencia de inicio del outro
            last_end = final_subtitles[-1]["end"] if final_subtitles else intro_dur
            # Ajustar para que coincida con el video de outro (que está al final)
            # El renderer pega el video AL FINAL.
            # Necesitamos saber la duración del MAIN video.
            # Estimación: last_end es aprox el final del main.
            
            final_subtitles.append({
                "start": last_end + 0.5,
                "end": last_end + outro_dur,
                "text": outro_text
            })
        
        # 4. Generar archivo de subtítulos ASS
        console.print("[dim]Generando subtítulos animados...[/dim]")
        subs_path = self.subtitle_gen.generate_animated(
            final_subtitles, f"subs_{script_id}", animation="fade"
        )
        
        if not subs_path:
            console.print("[red]Error generando subtítulos[/red]")
            return None
        
        # 5. Configurar escenas
        scene_configs = []
        
        # Agregar Intro
        if intro_path:
            scene_configs.append({
                "path": intro_path,
                "duration": intro_dur,
                "is_image": False
            })
            
        # Escenas del contenido
        if isinstance(background_paths, list) and len(background_paths) > 1 and scenes:
            # Calcular duraciones de escenas
            total_chars = sum(len(s.get("narration_chunk", "")) for s in scenes)
            
            # Duración del audio ORIGINAL (sin silencios)
            from pydub import AudioSegment
            audio = AudioSegment.from_file(audio_path)
            content_duration = len(audio) / 1000.0
            
            for i, scene in enumerate(scenes):
                if i >= len(background_paths):
                    break
                    
                char_count = len(scene.get("narration_chunk", ""))
                ratio = char_count / total_chars if total_chars > 0 else 0
                duration = content_duration * ratio
                
                # Para la última escena, asegurar que cubra todo el resto por decimales
                if i == len(scenes) - 1:
                    # Sumar lo que llevamos
                    current_total = sum(c["duration"] for c in scene_configs if c["path"] not in [intro_path])
                    remaining = content_duration - current_total
                    if remaining > 0:
                        duration = remaining
                
                bg_path = background_paths[i]
                if bg_path: # Puede ser None
                    scene_configs.append({
                        "path": bg_path,
                        "duration": duration,
                        "is_image": bg_path.lower().endswith((".jpg", ".jpeg", ".png", ".webp"))
                    })
        else:
            # Modo simple (un solo video de fondo)
            bg_path = background_paths[0] if isinstance(background_paths, list) and background_paths else background_paths
            if isinstance(background_paths, str):
                bg_path = background_paths
            
            if bg_path:
                # Duración es la del audio original
                from pydub import AudioSegment
                audio = AudioSegment.from_file(audio_path)
                content_duration = len(audio) / 1000.0
                
                scene_configs.append({
                    "path": bg_path,
                    "duration": content_duration,
                    "is_image": bg_path.lower().endswith((".jpg", ".jpeg", ".png", ".webp"))
                })
        
        # Agregar Outro
        if outro_path:
            scene_configs.append({
                "path": outro_path,
                "duration": outro_dur,
                "is_image": False
            })

        # 6. Renderizar
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_name = f"video_{script_id}_{timestamp}"
        
        with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"), console=console) as progress:
            task = progress.add_task("Renderizando Multi-Escena con FFmpeg...", total=None)
            
            video_path = self.renderer.render_multiscene(
                final_audio_path,
                scene_configs,
                subs_path,
                output_name,
                image_effect=image_effect
            )
            
            if video_path:
                progress.update(task, description="[green]✓ Video renderizado")
            else:
                progress.update(task, description="[red]✗ Error renderizando")
        
        if video_path:
            console.print(f"\n[bold green]🎬 Video final: {video_path}[/bold green]\n")
        
        return video_path
    
    def step_publish(
        self,
        video_path: str,
        script: dict,
        mode: Optional[str] = None,
        destinations: Optional[list[str]] = None
    ) -> Optional[dict]:
        """
        Paso 7: Publicar video a la nube y redes sociales.
        
        Args:
            video_path: Ruta local del video
            script: Dict del guión con metadata
            mode: 'interactive' o 'automatic' (default desde .env)
            destinations: Lista de destinos ['facebook', 'youtube']
            
        Returns:
            Dict con resultado de la publicación o None
        """
        console.print(Panel("[bold cyan]PASO 7: Publicando video[/bold cyan]"))
        
        # Obtener modo desde .env si no se especifica
        if mode is None:
            mode = os.getenv("PUBLISH_MODE", "interactive")
        
        # Obtener destinos desde .env si no se especifica
        if destinations is None:
            dest_env = os.getenv("PUBLISH_DESTINATIONS", "facebook,youtube")
            destinations = [d.strip() for d in dest_env.split(",")]
        
        # Verificar que webhook está configurado
        if not self.webhook.is_configured():
            console.print("[yellow]⚠ Webhook no configurado. Configura MAKE_WEBHOOK_URL en .env[/yellow]")
            console.print("[dim]El video fue guardado localmente pero no se publicará.[/dim]")
            return None
        
        # Modo interactivo: pedir confirmación
        if mode == "interactive":
            console.print(f"\n[cyan]Video: {video_path}[/cyan]")
            console.print(f"[cyan]Destinos: {', '.join(destinations)}[/cyan]")
            console.print("")
            
            try:
                confirm = input("¿Publicar este video? (s/n): ").strip().lower()
                if confirm not in ("s", "si", "sí", "y", "yes"):
                    console.print("[yellow]Publicación cancelada por el usuario[/yellow]")
                    return None
            except (KeyboardInterrupt, EOFError):
                console.print("\n[yellow]Publicación cancelada[/yellow]")
                return None
        
        # Paso 7.1: Subir a Google Drive
        console.print("\n[dim]7.1 Subiendo a Google Drive...[/dim]")
        
        with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"), console=console) as progress:
            task = progress.add_task("Subiendo video...", total=None)
            
            upload_result = self.uploader.upload_and_get_link(video_path)
            
            if upload_result:
                progress.update(task, description="[green]✓ Video subido a Google Drive")
            else:
                progress.update(task, description="[red]✗ Error subiendo video")
        
        if not upload_result:
            error_msg = "Error subiendo video a Google Drive"
            console.print(f"[red]{error_msg}[/red]")
            
            # Guardar en cola de reintentos
            self.retry_queue.add(
                video_path=video_path,
                script=script,
                error=error_msg,
                destinations=destinations
            )
            console.print("[yellow]Video guardado en cola de reintentos[/yellow]")
            return None
        
        remote_path = upload_result["remote_path"]
        public_url = upload_result["public_url"]
        
        console.print(f"[green]URL: {public_url[:60]}...[/green]")
        
        # Paso 7.2: Enviar a Make.com
        console.print("\n[dim]7.2 Enviando a Make.com...[/dim]")
        
        with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"), console=console) as progress:
            task = progress.add_task("Enviando webhook...", total=None)
            
            webhook_result = self.webhook.publish_from_metadata(
                video_url=public_url,
                script=script,
                destinations=destinations
            )
            
            if webhook_result["success"]:
                progress.update(task, description="[green]✓ Webhook enviado exitosamente")
            else:
                progress.update(task, description="[red]✗ Error enviando webhook")
        
        if not webhook_result["success"]:
            error_msg = webhook_result.get("error", "Error desconocido")
            console.print(f"[red]Error: {error_msg}[/red]")
            
            # Guardar en cola de reintentos (ya tenemos la URL)
            self.retry_queue.add(
                video_path=video_path,
                script=script,
                error=error_msg,
                remote_path=remote_path,
                video_url=public_url,
                destinations=destinations
            )
            console.print("[yellow]Video guardado en cola de reintentos[/yellow]")
            return None
        
        # Éxito total
        console.print(f"\n[bold green]📤 Video publicado exitosamente![/bold green]")
        console.print(f"[green]Destinos: {', '.join(destinations)}[/green]")
        
        return {
            "success": True,
            "video_path": video_path,
            "remote_path": remote_path,
            "public_url": public_url,
            "destinations": destinations,
            "webhook_response": webhook_result.get("response")
        }
    
    def retry_failed_publications(self) -> list[dict]:
        """
        Reintenta publicar videos de la cola de fallos.
        
        Returns:
            Lista de resultados
        """
        pending = self.retry_queue.get_pending()
        
        if not pending:
            console.print("[yellow]No hay publicaciones pendientes en la cola[/yellow]")
            return []
        
        console.print(f"[cyan]Reintentando {len(pending)} publicaciones fallidas...[/cyan]\n")
        
        results = []
        
        for i, item in enumerate(pending):
            console.print(f"[dim]--- Item {i + 1} de {len(pending)} ---[/dim]")
            
            # Si ya tiene URL, solo reintentar webhook
            if item.video_url:
                console.print("[dim]URL ya disponible, reintentando webhook...[/dim]")
                
                webhook_result = self.webhook.publish_from_metadata(
                    video_url=item.video_url,
                    script=item.script,
                    destinations=item.destinations
                )
                
                if webhook_result["success"]:
                    self.retry_queue.remove(i - len([r for r in results if r.get("success")]))
                    console.print("[green]✓ Publicación exitosa[/green]\n")
                    results.append({"success": True, "video": item.video_path})
                else:
                    self.retry_queue.update_attempt(i, webhook_result.get("error"))
                    console.print(f"[red]✗ Falló nuevamente: {webhook_result.get('error')}[/red]\n")
                    results.append({"success": False, "video": item.video_path})
            else:
                # Necesita subir primero
                result = self.step_publish(
                    video_path=item.video_path,
                    script=item.script,
                    mode="automatic",
                    destinations=item.destinations
                )
                
                if result and result.get("success"):
                    self.retry_queue.remove_by_path(item.video_path)
                    results.append({"success": True, "video": item.video_path})
                else:
                    results.append({"success": False, "video": item.video_path})
        
        # Resumen
        success_count = len([r for r in results if r.get("success")])
        console.print(f"\n[bold]Completados: {success_count} de {len(pending)}[/bold]")
        
        return results
    
    def run_full_pipeline(
        self,
        sources: Optional[list[str]] = None,
        prefer_video_bg: bool = True,
        image_effect: str = "zoom",
        skip_scrape: bool = False,
        publish: bool = True,
        publish_mode: Optional[str] = None
    ) -> Optional[str]:
        """
        Ejecuta el pipeline completo para UN video.
        """
        console.print(Panel(
            "[bold magenta]🚀 PIPELINE COMPLETO (Siguiente Nivel)[/bold magenta]\n"
            "Scraping → LLM (Escenas) → TTS → Multi-Video → Publicar",
            title="Creador de Videos Virales"
        ))
        
        try:
            # Paso 1: Scraping (opcional)
            if not skip_scrape:
                content = self.step_scrape(sources)
                
                if not content:
                    console.print("[yellow]No se obtuvo contenido nuevo. Usando cache...[/yellow]")
            
            # Paso 2: Generar guión (ahora con escenas)
            script = self.step_generate_script(from_cache=True)
            
            if not script:
                console.print("[red]No se pudo generar el guión[/red]")
                return None
            
            script_id = script.get("_id", "video")
            scenes = script.get("scenes", [])
            
            # Paso 3: Generar audio
            audio_result = self.step_generate_audio(script, script_id)
            
            if not audio_result:
                console.print("[red]No se pudo generar el audio[/red]")
                return None
            
            # Paso 4: Obtener fondos para CADA escena
            background_paths = self.step_get_scene_assets(scenes, prefer_video_bg)
            
            # Paso 5: Renderizar Multi-Escena
            video_path = self.step_render_video(
                audio_result["audio_path"],
                background_paths,
                audio_result["subtitles"],
                script_id,
                scenes=scenes,
                image_effect=image_effect
            )
            
            if not video_path:
                console.print("[red]No se pudo renderizar el video[/red]")
                return None
            
            # Paso 6: Crear carpeta del video y metadata
            console.print(Panel("[bold cyan]PASO 6: Organizando archivos[/bold cyan]"))
            
            # Crear carpeta
            # Crear carpeta con fecha y título
            import unicodedata
            safe_title = unicodedata.normalize('NFKD', script.get('title', 'video')).encode('ASCII', 'ignore').decode('ASCII')
            safe_title = re.sub(r'[^\w\s-]', '', safe_title).strip().lower()
            safe_title = re.sub(r'[-\s]+', '_', safe_title)
            
            date_str = datetime.now().strftime("%Y%m%d")
            folder_name = f"{date_str}_{safe_title[:30]}"
            video_folder = self.output_dir / folder_name
            video_folder.mkdir(exist_ok=True)
            
            # Mover video
            new_video_path = video_folder / "video.mp4"
            import shutil
            shutil.move(video_path, new_video_path)
            
            # Generar metadata
            metadata_path = self._generate_video_metadata(
                video_folder=video_folder,
                script=script,
                video_filename="video.mp4"
            )
            
            console.print(f"[green]✓ Metadata generada: {metadata_path}[/green]")
            console.print(f"\n[bold green]🎬 Video listo: {new_video_path}[/bold green]\n")
            
            # Paso 7: Publicar (opcional)
            if publish:
                # Guardar duración en el script para metadata
                if audio_result and "duration" in audio_result:
                    script["_duration"] = audio_result["duration"]
                
                publish_result = self.step_publish(
                    video_path=str(new_video_path),
                    script=script,
                    mode=publish_mode
                )
                
                if not publish_result:
                    console.print("[yellow]Video guardado localmente (publicación pendiente)[/yellow]")
            else:
                console.print("[dim]Publicación omitida (--no-publish)[/dim]")
            
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
        process_all_pending: bool = False,
        publish: bool = True,
        publish_mode: Optional[str] = None,
        skip_scrape: bool = False,
        filter_urls: Optional[list[str]] = None
    ) -> list[str]:
        """
        Ejecuta el pipeline para múltiples videos.
        
        Args:
            count: Número de videos a generar
            sources: Fuentes de scraping
            prefer_video_bg: Si preferir video sobre imagen de fondo
            image_effect: Efecto para imágenes de fondo
            process_all_pending: Si procesar todo el cache pendiente
            publish: Si publicar los videos después de generarlos
            publish_mode: 'interactive' o 'automatic' (default desde .env)
            skip_scrape: Si saltar el paso de scraping global
            filter_urls: Lista de URLs específicas para procesar (ignora el resto del cache)
            
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
        if not skip_scrape:
            console.print("\n[bold cyan]Fase 1: Obteniendo contenido...[/bold cyan]")
            self.step_scrape(sources)
        else:
            console.print("\n[dim]Fase 1: Scraping omitido (usando contenido cazado)[/dim]")
        
        # Determinar cuántos videos procesar
        pending = self.cache.get_pending_content()
        
        # Filtrar por URLs si se especifica (Trend Hunter)
        if filter_urls:
            original_count = len(pending)
            pending = [p for p in pending if p.get('url') in filter_urls]
            console.print(f"[cyan]Filtrando cache: {len(pending)} de {original_count} items seleccionados[/cyan]")
        
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
                    skip_scrape=True,  # No repetir scraping
                    publish=publish,
                    publish_mode=publish_mode
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
    "Punto de entrada CLI."
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
    parser.add_argument("--tts", type=str, choices=["edge", "xtts"], default="edge", help="Motor TTS a usar (edge=rápido, xtts=calidad)")
    parser.add_argument("--video-bg", action="store_true", default=True, help="Preferir video de fondo")
    parser.add_argument("--image-bg", action="store_true", help="Preferir imagen de fondo")
    parser.add_argument("--effect", choices=["zoom", "pan", "kenburns"], default="zoom",
                       help="Efecto para imágenes de fondo")
    
    # Opciones de publicación
    parser.add_argument("--no-publish", action="store_true", help="No publicar después de generar")
    parser.add_argument("--publish-mode", choices=["interactive", "automatic"],
                       help="Modo de publicación (default: desde .env)")
    parser.add_argument("--retry-failed", action="store_true", help="Reintentar publicaciones fallidas")
    parser.add_argument("--publish-queue", action="store_true", help="Ver cola de publicaciones pendientes")
    parser.add_argument("--publish", help="Publicar un video existente (ruta)")
    
    # Nuevas opciones
    parser.add_argument("--trend-hunter", type=int, help="Buscar tendencias y generar N videos automáticamente")
    
    args = parser.parse_args()
    
    pipeline = VideoPipeline(tts_engine=args.tts)
    
    try:
        if args.trend_hunter:
            count = args.trend_hunter
            console.print(Panel(
                f"[bold magenta]🚀 TREND HUNTER (Inglés → Español)[/bold magenta]\n"
                f"Buscando {count} tendencias virales para adaptar...",
                title="Creador de Videos Virales"
            ))
            
            from .scraper import YouTubeClient
            import random
            
            yt_client = YouTubeClient(cache=pipeline.cache)
            searches = yt_client.config.get("searches", [])
            
            if not searches:
                console.print("[red]No hay búsquedas configuradas en sources.yaml[/red]")
                return

            videos_found = []
            attempts = 0
            max_attempts = 5
            
            with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"), console=console) as progress:
                task = progress.add_task("Cazando tendencias...", total=count)
                
                while len(videos_found) < count and attempts < max_attempts:
                    # Seleccionar tema aleatorio
                    search_config = random.choice(searches)
                    query = search_config.get("query")
                    
                    progress.update(task, description=f"Buscando: {query}...")
                    
                    # Buscar videos
                    candidates = yt_client.search_videos(query, max_results=10)
                    
                    # Filtrar y descargar transcripción
                    for candidate in candidates:
                        if len(videos_found) >= count:
                            break
                            
                        # Verificar si ya lo tenemos
                        if any(v.url == candidate.url for v in videos_found):
                            continue
                            
                        progress.update(task, description=f"Analizando: {candidate.title[:30]}...")
                        
                        # Descargar transcripción completa
                        full_video = yt_client.fetch_video(candidate.url)
                        
                        if full_video and full_video.transcript:
                            # Guardar en cache
                            pipeline.cache.store_scraped_content("youtube", [full_video.to_dict()])
                            videos_found.append(full_video)
                            progress.advance(task)
                            console.print(f"[green]✓ Encontrado: {full_video.title[:50]}...[/green]")
                    
                    attempts += 1
            
            if videos_found:
                console.print(f"\n[green]✓ {len(videos_found)} tendencias capturadas. Iniciando producción...[/green]\n")
                
                # Lista de URLs encontradas para filtrar
                target_urls = [v.url for v in videos_found]
                
                # Ejecutar batch SOLO con lo que tenemos
                pipeline.run_batch_pipeline(
                    process_all_pending=True,
                    skip_scrape=True,  # No volver a scrapear RSS/Reddit
                    sources=["youtube"], # Solo enfocarse en youtube por seguridad
                    prefer_video_bg=not args.image_bg,
                    image_effect=args.effect,
                    publish=not args.no_publish,
                    publish_mode=args.publish_mode,
                    filter_urls=target_urls # Solo procesar estos videos
                )
            else:
                console.print("[yellow]No se encontraron tendencias válidas con transcripción[/yellow]")
            return

        if args.pending:
            count = pipeline.get_pending_count()
            console.print(f"[cyan]Contenido pendiente en cache: {count} items[/cyan]")
            return
        
        if args.publish_queue:
            summary = pipeline.retry_queue.get_summary()
            console.print(f"\n[cyan]Cola de publicaciones pendientes: {summary['count']} items[/cyan]")
            for item in summary.get("items", []):
                console.print(f"  • {item['video']} ({item['attempts']} intentos)")
            return
        
        if args.retry_failed:
            pipeline.retry_failed_publications()
            return
        
        if args.publish:
            # Publicar video existente
            from pathlib import Path
            video_path = Path(args.publish)
            if not video_path.exists():
                console.print(f"[red]Video no encontrado: {args.publish}[/red]")
                return
            
            # Cargar metadata si existe
            metadata_path = video_path.parent / "metadata.md"
            script = {}
            if metadata_path.exists():
                # Extraer título del metadata
                with open(metadata_path, "r") as f:
                    content = f.read()
                    if content.startswith("# "):
                        script["title"] = content.split("\n")[0][2:]
            
            pipeline.step_publish(
                video_path=str(video_path),
                script=script,
                mode=args.publish_mode
            )
            return
        
        prefer_video = not args.image_bg
        publish = not args.no_publish
        
        if args.batch:
            # Modo batch: procesar todo el cache
            pipeline.run_batch_pipeline(
                process_all_pending=True,
                sources=args.sources,
                prefer_video_bg=prefer_video,
                image_effect=args.effect,
                publish=publish,
                publish_mode=args.publish_mode
            )
        elif args.full or args.count > 1:
            # Con --count o --full
            if args.count > 1:
                pipeline.run_batch_pipeline(
                    count=args.count,
                    sources=args.sources,
                    prefer_video_bg=prefer_video,
                    image_effect=args.effect,
                    publish=publish,
                    publish_mode=args.publish_mode
                )
            else:
                pipeline.run_full_pipeline(
                    sources=args.sources,
                    prefer_video_bg=prefer_video,
                    image_effect=args.effect,
                    publish=publish,
                    publish_mode=args.publish_mode
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
