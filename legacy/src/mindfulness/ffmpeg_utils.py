import logging
import subprocess
from pathlib import Path
from typing import List, Optional

logger = logging.getLogger(__name__)

class FFmpegAssembler:
    """
    Handles complex FFmpeg assembly for Mindfulness videos.
    Combines:
    1. Pexels Clips (concat with xfade)
    2. p5.js Generative Overlay (blended)
    3. Audio & Subtitles
    """

    WIDTH = 1080
    HEIGHT = 1920
    FPS = 30

    def __init__(self, output_dir: str):
        self.output_dir = Path(output_dir)

    def frames_to_video(self, frames_dir: str, duration: float, output_path: str) -> bool:
        """Converts a sequence of p5.js frames (PNG) to a video file."""
        cmd = [
            "ffmpeg", "-y",
            "-framerate", str(self.FPS),
            "-i", str(Path(frames_dir) / "frame_%04d.png"),
            "-c:v", "libx264",
            "-pix_fmt", "yuv420p",
            "-t", str(duration),
            output_path
        ]
        try:
            subprocess.run(cmd, check=True, capture_output=True)
            return True
        except subprocess.CalledProcessError as e:
            logger.error(f"Error converting frames to video: {e.stderr.decode()}")
            return False

    def assemble_interleaved_video(
        self,
        clips: List[str],
        audio_path: str,
        subtitles_path: str,
        output_path: str
    ) -> bool:
        """
        Assembles video by concatenating clips with smooth crossfades.
        """
        if not clips:
            logger.error("No clips provided")
            return False

        # Scale all clips to target resolution first to avoid concat errors
        # Create temporary scaled files? Or huge filter complex?
        # Huge filter complex is more efficient but complex to build string.
        
        inputs = []
        filter_parts = []
        
        # 1. Prepare Inputs
        for i, clip in enumerate(clips):
            inputs.extend(["-i", clip])
            # Scale, normalize FPS and timebase, reset PTS
            filter_parts.append(
                f"[{i}:v]scale={self.WIDTH}:{self.HEIGHT}:force_original_aspect_ratio=increase,"
                f"crop={self.WIDTH}:{self.HEIGHT},fps={self.FPS},settb=1/{self.FPS},setsar=1,setpts=PTS-STARTPTS[v{i}];"
            )

        # 2. Build Xfade Chain
        # We need a fixed duration for xfade overlap (e.g. 1s)
        # We need to calculate cumulative offsets.
        # Since we don't know exact durations inside this function easily without probing,
        # we will assume the caller provides clips that are roughly the right length 
        # BUT xfade needs `offset`. 
        # To do this robustly in one command, we need durations.
        
        # Strategy: Use a simpler 'movie' approach or assume fixed durations?
        # No, better: Use the 'concat' filter with crossfade enabled (simpler/safer).
        # ffmpeg -i 1.mp4 -i 2.mp4 -filter_complex "[0][1]xfade=transition=fade:duration=1:offset=4[f1];[f1][2]xfade...""
        
        # We MUST know offset. Offset = length of prev video - xfade duration.
        # Getting duration of every clip:
        durations = []
        for clip in clips:
            durations.append(self._get_duration(clip))
            
        xfade_dur = 1.0
        curr_offset = 0.0
        
        # Start chain
        last_pad = "v0"
        
        for i in range(1, len(clips)):
            prev_dur = durations[i-1]
            curr_offset += prev_dur - xfade_dur
            
            filter_parts.append(
                f"[{last_pad}][v{i}]xfade=transition=fade:duration={xfade_dur}:offset={curr_offset}[x{i}];"
            )
            last_pad = f"x{i}"
            
        # Final filter map
        # Add audio and subtitles
        # Note: Concatenated video [xN] needs to be mapped.
        
        # Apply subtitles to the final concatenated stream
        filter_parts.append(
            f"[{last_pad}]subtitles={subtitles_path}:force_style='Fontsize=98,PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,BorderStyle=1,Outline=4,Shadow=2'[final]"
        )

        full_filter = "".join(filter_parts)

        cmd = [
            "ffmpeg", "-y",
            *inputs,
            "-i", audio_path,
            "-filter_complex", full_filter,
            "-map", "[final]",
            "-map", f"{len(clips)}:a",
            "-c:v", "libx264",
            "-preset", "medium",
            "-crf", "23",
            "-c:a", "aac",
            "-b:a", "192k",
            "-shortest", 
            output_path
        ]

        logger.info(f"Running interleaved assembly...")
        try:
            subprocess.run(cmd, check=True, capture_output=True)
            return True
        except subprocess.CalledProcessError as e:
            logger.error(f"Error in assembly: {e.stderr.decode()}")
            return False

    def _get_duration(self, path: str) -> float:
        try:
            r = subprocess.run(
                ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", path],
                capture_output=True, text=True
            )
            return float(r.stdout.strip())
        except:
            return 5.0 # Fallback

    def assemble_with_stickers(
        self,
        p5_video: str,
        stickers: List[dict],
        audio_path: str,
        subtitles_path: str,
        output_path: str
    ) -> bool:
        """
        Ensambla video final con p5 base + stickers animados + subtítulos.
        
        Args:
            p5_video: Video de arte generativo (base)
            stickers: Lista de dicts con path, start, end
            audio_path: Ruta al audio
            subtitles_path: Ruta a subtítulos ASS
            output_path: Ruta de salida
            
        Returns:
            True si exitoso
        """
        from .sticker_overlay import StickerOverlay
        
        overlay = StickerOverlay(self.WIDTH, self.HEIGHT)
        sticker_inputs, filter_complex = overlay.build_complete_filter(
            stickers, 
            subtitles_path,
            animation="float"
        )
        
        # Construir comando
        cmd = [
            "ffmpeg", "-y",
            "-i", p5_video,
            *sticker_inputs,
            "-i", audio_path,
            "-filter_complex", filter_complex,
            "-map", "[final]",
            "-map", f"{1 + len(stickers)}:a",  # Audio es el último input
            "-c:v", "libx264",
            "-preset", "medium",
            "-crf", "23",
            "-c:a", "aac",
            "-b:a", "192k",
            "-shortest",
            output_path
        ]
        
        logger.info(f"Assembling video with {len(stickers)} stickers...")
        try:
            subprocess.run(cmd, check=True, capture_output=True)
            return True
        except subprocess.CalledProcessError as e:
            logger.error(f"Error in sticker assembly: {e.stderr.decode()}")
            return False
