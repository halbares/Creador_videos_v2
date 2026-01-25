"""
Cloud Uploader - Wrapper para rclone para subir videos a Google Drive.

Funcionalidades:
- Subir archivos a Google Drive
- Obtener enlaces públicos de descarga
- Verificar existencia de archivos remotos
"""

import logging
import os
import subprocess
from pathlib import Path
from typing import Optional
from datetime import datetime

from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)


class CloudUploader:
    """Wrapper para rclone para subir archivos a Google Drive."""
    
    def __init__(
        self,
        remote_name: Optional[str] = None,
        base_folder: Optional[str] = None
    ):
        """
        Inicializa el uploader.
        
        Args:
            remote_name: Nombre del remote en rclone (default: GDRIVE_REMOTE o 'gdrive')
            base_folder: Carpeta base en Drive (default: GDRIVE_FOLDER o 'Videos/Creador')
        """
        self.remote = remote_name or os.getenv("GDRIVE_REMOTE", "gdrive")
        self.base_folder = base_folder or os.getenv("GDRIVE_FOLDER", "Videos/Creador")
        self.is_ready = False
        
        # Verificar que rclone está disponible
        self._verify_rclone()
    
    def _verify_rclone(self) -> None:
        """Verifica que rclone está instalado y el remote existe."""
        try:
            result = subprocess.run(
                ["rclone", "listremotes"],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode != 0:
                logger.warning("rclone no está configurado correctamente (return code != 0)")
                return
            
            remotes = result.stdout.strip().split("\n")
            remote_with_colon = f"{self.remote}:"
            
            if remote_with_colon not in remotes:
                logger.warning(
                    f"Remote '{self.remote}' no encontrado en rclone. "
                    f"Remotes disponibles: {remotes}. "
                    "La subida automática estará deshabilitada."
                )
                return
                
            self.is_ready = True
                
        except FileNotFoundError:
            logger.warning("rclone no está instalado. Instálalo con: sudo pacman -S rclone")
        except Exception as e:
            logger.warning(f"Error verificando rclone: {e}")
    
    def _run_rclone(self, args: list[str], timeout: int = 300) -> subprocess.CompletedProcess:
        """Ejecuta un comando rclone."""
        cmd = ["rclone"] + args
        logger.debug(f"Ejecutando: {' '.join(cmd)}")
        
        return subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout
        )
    
    def ensure_folder_exists(self) -> bool:
        """Crea la carpeta base si no existe."""
        if not self.is_ready:
            return False
            
        remote_path = f"{self.remote}:{self.base_folder}"
        
        result = self._run_rclone(["mkdir", remote_path])
        
        if result.returncode != 0:
            logger.error(f"Error creando carpeta: {result.stderr}")
            return False
        
        logger.info(f"Carpeta verificada/creada: {remote_path}")
        return True
    
    def upload(
        self,
        local_path: str,
        subfolder: Optional[str] = None,
        show_progress: bool = True
    ) -> Optional[str]:
        """
        Sube un archivo a Google Drive.
        
        Args:
            local_path: Ruta local del archivo
            subfolder: Subcarpeta opcional (ej: '2026/01')
            show_progress: Si mostrar progreso en consola
            
        Returns:
            Ruta remota del archivo o None si falla
        """
        local_file = Path(local_path)
        
        if not self.is_ready:
            logger.warning("Upload omitido: rclone no está listo")
            return None
        
        if not local_file.exists():
            logger.error(f"Archivo no existe: {local_path}")
            return None
        
        # Construir ruta remota
        if subfolder:
            remote_folder = f"{self.base_folder}/{subfolder}"
        else:
            # Organizar por fecha
            date_folder = datetime.now().strftime("%Y/%m")
            remote_folder = f"{self.base_folder}/{date_folder}"
        
        remote_path = f"{self.remote}:{remote_folder}"
        
        # Asegurar que la carpeta existe
        self._run_rclone(["mkdir", remote_path])
        
        # Subir archivo
        args = ["copy", str(local_file), remote_path]
        
        if show_progress:
            args.append("--progress")
        
        logger.info(f"Subiendo {local_file.name} a {remote_path}...")
        result = self._run_rclone(args, timeout=600)  # 10 min timeout
        
        if result.returncode != 0:
            logger.error(f"Error subiendo archivo: {result.stderr}")
            return None
        
        # Retornar ruta completa del archivo remoto
        full_remote_path = f"{remote_folder}/{local_file.name}"
        logger.info(f"Archivo subido: {full_remote_path}")
        
        return full_remote_path
    
    def get_public_link(self, remote_path: str) -> Optional[str]:
        """
        Obtiene un enlace público de descarga para un archivo.
        
        Args:
            remote_path: Ruta del archivo en el remote (sin el nombre del remote)
            
        Returns:
            URL pública de descarga directa o None si falla
        """
        if not self.is_ready:
            return None
            
        full_path = f"{self.remote}:{remote_path}"
        
        logger.info(f"Obteniendo enlace público para: {full_path}")
        result = self._run_rclone(["link", full_path], timeout=30)
        
        if result.returncode != 0:
            logger.error(f"Error obteniendo enlace: {result.stderr}")
            return None
        
        url = result.stdout.strip()
        
        if not url:
            logger.error("No se obtuvo URL")
            return None
        
        # Convertir URL de vista a URL de descarga directa según el servicio
        
        # Google Drive: 
        # De: https://drive.google.com/open?id=FILE_ID
        # A:  https://drive.google.com/uc?id=FILE_ID&export=download&confirm=t
        if "drive.google.com/open?id=" in url:
            file_id = url.split("id=")[-1]
            url = f"https://drive.google.com/uc?id={file_id}&export=download&confirm=t"
            logger.info(f"URL Google Drive convertida: {url}")
        
        # Dropbox:
        # De: https://www.dropbox.com/...?rlkey=xxx&dl=0
        # A:  https://www.dropbox.com/...?rlkey=xxx&raw=1
        elif "dropbox.com" in url:
            # Reemplazar dl=0 o dl=1 con raw=1 (funciona tanto con ? como con &)
            if "&dl=0" in url:
                url = url.replace("&dl=0", "&raw=1")
            elif "&dl=1" in url:
                url = url.replace("&dl=1", "&raw=1")
            elif "?dl=0" in url:
                url = url.replace("?dl=0", "?raw=1")
            elif "?dl=1" in url:
                url = url.replace("?dl=1", "?raw=1")
            else:
                url = url + "&raw=1"
            logger.info(f"URL Dropbox convertida: {url}")
        
        logger.info(f"Enlace público: {url}")
        return url
    
    def upload_and_get_link(
        self,
        local_path: str,
        subfolder: Optional[str] = None
    ) -> Optional[dict]:
        """
        Sube un archivo y obtiene su enlace público en un solo paso.
        
        Args:
            local_path: Ruta local del archivo
            subfolder: Subcarpeta opcional
            
        Returns:
            Dict con 'remote_path' y 'public_url' o None si falla
        """
        # Subir
        remote_path = self.upload(local_path, subfolder, show_progress=False)
        
        if not remote_path:
            return None
        
        # Obtener enlace
        public_url = self.get_public_link(remote_path)
        
        if not public_url:
            return None
        
        return {
            "remote_path": remote_path,
            "public_url": public_url,
            "local_path": local_path
        }
    
    def delete(self, remote_path: str) -> bool:
        """
        Elimina un archivo del remote.
        
        Args:
            remote_path: Ruta del archivo en el remote
            
        Returns:
            True si se eliminó correctamente
        """
        if not self.is_ready:
            return None
            
        full_path = f"{self.remote}:{remote_path}"
        
        result = self._run_rclone(["delete", full_path])
        
        if result.returncode != 0:
            logger.error(f"Error eliminando archivo: {result.stderr}")
            return False
        
        logger.info(f"Archivo eliminado: {full_path}")
        return True
    
    def file_exists(self, remote_path: str) -> bool:
        """Verifica si un archivo existe en el remote."""
        if not self.is_ready:
            return None
            
        full_path = f"{self.remote}:{remote_path}"
        
        result = self._run_rclone(["lsf", full_path])
        
        return result.returncode == 0 and len(result.stdout.strip()) > 0
    
    def cleanup_old_files(self, days: int = 7, dry_run: bool = True) -> dict:
        """
        Elimina archivos más antiguos de X días del remote.
        
        Args:
            days: Número de días de antigüedad mínima (default: 7)
            dry_run: Si True, solo lista los archivos sin eliminar
            
        Returns:
            Dict con 'deleted' (lista de archivos) y 'count' (cantidad)
        """
        folder_path = f"{self.remote}:{self.base_folder}"
        
        if dry_run:
            # Listar archivos que serían eliminados
            args = ["lsf", folder_path, "-R", "--min-age", f"{days}d"]
        else:
            # Eliminar archivos
            args = ["delete", folder_path, "--min-age", f"{days}d", "-v"]
        
        logger.info(f"{'[DRY-RUN] ' if dry_run else ''}Limpiando archivos > {days} días en {folder_path}")
        
        result = self._run_rclone(args, timeout=300)
        
        deleted_files = []
        if result.returncode == 0:
            if dry_run:
                deleted_files = [f.strip() for f in result.stdout.strip().split('\n') if f.strip()]
                logger.info(f"[DRY-RUN] Se eliminarían {len(deleted_files)} archivos")
            else:
                # Contar archivos eliminados del stderr
                for line in result.stderr.split('\n'):
                    if 'Deleted' in line:
                        deleted_files.append(line.strip())
                logger.info(f"Eliminados {len(deleted_files)} archivos antiguos")
        else:
            logger.error(f"Error en limpieza: {result.stderr}")
        
        return {
            "deleted": deleted_files,
            "count": len(deleted_files),
            "dry_run": dry_run
        }


# CLI para testing
if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Cloud Uploader - rclone wrapper")
    parser.add_argument("--upload", help="Archivo a subir")
    parser.add_argument("--link", help="Obtener link de archivo remoto")
    parser.add_argument("--test", action="store_true", help="Test de conexión")
    parser.add_argument("--cleanup", action="store_true", help="Limpiar archivos antiguos")
    parser.add_argument("--days", type=int, default=7, help="Días de antigüedad para cleanup (default: 7)")
    parser.add_argument("--confirm", action="store_true", help="Confirmar eliminación (sin esto es dry-run)")
    
    args = parser.parse_args()
    
    uploader = CloudUploader()
    
    if args.test:
        print(f"✓ Remote: {uploader.remote}")
        print(f"✓ Carpeta base: {uploader.base_folder}")
        uploader.ensure_folder_exists()
        print("✓ Conexión exitosa")
    
    elif args.upload:
        result = uploader.upload_and_get_link(args.upload)
        if result:
            print(f"✓ Subido: {result['remote_path']}")
            print(f"✓ URL: {result['public_url']}")
        else:
            print("✗ Error subiendo archivo")
    
    elif args.link:
        url = uploader.get_public_link(args.link)
        if url:
            print(f"✓ URL: {url}")
        else:
            print("✗ Error obteniendo link")
    
    elif args.cleanup:
        dry_run = not args.confirm
        print(f"{'[DRY-RUN] ' if dry_run else ''}Limpiando archivos > {args.days} días...")
        result = uploader.cleanup_old_files(days=args.days, dry_run=dry_run)
        
        if result["count"] > 0:
            print(f"\n{'Archivos que se eliminarían:' if dry_run else 'Archivos eliminados:'}")
            for f in result["deleted"][:10]:  # Mostrar max 10
                print(f"  - {f}")
            if result["count"] > 10:
                print(f"  ... y {result['count'] - 10} más")
            
            if dry_run:
                print(f"\nTotal: {result['count']} archivos")
                print("Para eliminar realmente, usa: --cleanup --confirm")
        else:
            print("No hay archivos para limpiar")
