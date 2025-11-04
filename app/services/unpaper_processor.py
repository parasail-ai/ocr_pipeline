"""Unpaper preprocessing service for cleaning scanned images."""
import logging
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class UnpaperUnavailable(Exception):
    """Raised when unpaper is not installed."""
    pass


class UnpaperProcessor:
    """
    Wrapper for unpaper command-line tool.
    Cleans scanned images by removing dark edges and deskewing pages.
    """
    
    def __init__(self):
        """Initialize unpaper processor."""
        # Check if unpaper is installed
        if not shutil.which('unpaper'):
            raise UnpaperUnavailable("unpaper command-line tool is not installed")
        
        logger.info("Unpaper processor initialized successfully")
    
    def process_image(self, input_path: Path, output_path: Optional[Path] = None) -> Path:
        """
        Process an image file using unpaper.
        
        Args:
            input_path: Path to input image
            output_path: Path for output image (optional, will use temp file if not provided)
            
        Returns:
            Path to processed image
        """
        if output_path is None:
            # Create temp output file
            suffix = input_path.suffix
            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
            output_path = Path(temp_file.name)
            temp_file.close()
        
        try:
            logger.info(f"Processing image with unpaper: {input_path}")
            
            # Run unpaper command
            # Options: --overwrite to allow same input/output, -n for noise filter level
            result = subprocess.run(
                ['unpaper', '--overwrite', str(input_path), str(output_path)],
                capture_output=True,
                text=True,
                timeout=60  # 60 second timeout
            )
            
            if result.returncode != 0:
                logger.error(f"Unpaper failed: {result.stderr}")
                raise RuntimeError(f"Unpaper processing failed: {result.stderr}")
            
            logger.info(f"Unpaper processing complete: {output_path}")
            return output_path
            
        except subprocess.TimeoutExpired:
            logger.error("Unpaper processing timed out")
            raise RuntimeError("Unpaper processing timed out after 60 seconds")
        except Exception as e:
            logger.exception(f"Unpaper processing failed: {e}")
            raise RuntimeError(f"Unpaper processing failed: {str(e)}")
    
    @staticmethod
    def is_supported_file(filename: str) -> bool:
        """Check if file type is supported by unpaper (images only)."""
        supported_extensions = {'.png', '.jpg', '.jpeg', '.tif', '.tiff', '.pnm', '.pbm', '.pgm', '.ppm'}
        extension = Path(filename).suffix.lower()
        return extension in supported_extensions
