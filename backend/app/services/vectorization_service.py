"""
Service de vectorisation d'images bitmap en SVG avec Potrace.
Utilise le binaire potrace (CLI) ou pypotrace si disponible.
"""

import logging
import io
import subprocess
import tempfile
import os
from typing import Optional
from PIL import Image
import numpy as np
import xml.etree.ElementTree as ET

logger = logging.getLogger(__name__)

# Try to import pypotrace (optional C extension)
try:
    import pypotrace
    PYPOTRACE_AVAILABLE = True
    logger.info("pypotrace C extension available")
except ImportError:
    PYPOTRACE_AVAILABLE = False
    logger.warning("pypotrace not available, falling back to potrace CLI binary")


class VectorizationService:
    """
    Service de conversion bitmap → SVG avec Potrace.
    Optimisé pour schémas techniques de brevets.
    Utilise pypotrace (C extension) si disponible, sinon le binaire potrace CLI.
    """

    def __init__(self):
        """Initialize vectorization service."""
        self.default_params = {
            "turnpolicy": "minority",
            "turdsize": 2,
            "alphamax": 1.0,
            "opticurve": True,
            "opttolerance": 0.2
        }

    def bitmap_to_svg(
        self,
        image_bytes: bytes,
        threshold: int = 128,
        invert: bool = False
    ) -> str:
        """
        Convertit image bitmap en SVG vectorisé.

        Args:
            image_bytes: Image source (bytes)
            threshold: Seuil de binarisation (0-255)
            invert: Inverser noir/blanc

        Returns:
            Contenu SVG (string)
        """
        logger.info("Starting bitmap to SVG vectorization")

        if PYPOTRACE_AVAILABLE:
            return self._vectorize_with_pypotrace(image_bytes, threshold, invert)
        else:
            return self._vectorize_with_cli(image_bytes, threshold, invert)

    # ------------------------------------------------------------------
    # Backend 1: pypotrace C extension
    # ------------------------------------------------------------------

    def _vectorize_with_pypotrace(
        self,
        image_bytes: bytes,
        threshold: int,
        invert: bool
    ) -> str:
        """Uses the pypotrace C extension."""
        img = Image.open(io.BytesIO(image_bytes))
        width, height = img.size

        img_gray = img.convert('L')
        img_bw = img_gray.point(lambda x: 255 if x > threshold else 0, '1')

        if invert:
            img_bw = img_bw.point(lambda x: 255 - x)

        bitmap_array = np.array(img_bw, dtype=bool)

        bmp = pypotrace.Bitmap(bitmap_array)
        path = bmp.trace(
            turdsize=self.default_params["turdsize"],
            turnpolicy=self.default_params["turnpolicy"],
            alphamax=self.default_params["alphamax"],
            opticurve=self.default_params["opticurve"],
            opttolerance=self.default_params["opttolerance"]
        )

        svg_content = self._path_to_svg(path, width, height)
        logger.info(f"Vectorization (pypotrace) complete: {len(svg_content)} bytes SVG")
        return svg_content

    # ------------------------------------------------------------------
    # Backend 2: potrace CLI binary
    # ------------------------------------------------------------------

    def _vectorize_with_cli(
        self,
        image_bytes: bytes,
        threshold: int,
        invert: bool
    ) -> str:
        """
        Uses the system 'potrace' binary (already installed in Docker image).
        Converts image → PBM temp file → runs potrace → reads SVG output.
        """
        img = Image.open(io.BytesIO(image_bytes))
        width, height = img.size

        # Convert to grayscale then binarise
        img_gray = img.convert('L')
        img_bw = img_gray.point(lambda x: 255 if x > threshold else 0, '1')

        if invert:
            img_bw = img_bw.point(lambda x: 255 - x)

        with tempfile.TemporaryDirectory() as tmpdir:
            pbm_path = os.path.join(tmpdir, "input.pbm")
            svg_path = os.path.join(tmpdir, "output.svg")

            # Save as PBM (binary bitmap), which potrace reads natively
            img_bw.save(pbm_path)

            # Build potrace command
            cmd = [
                "potrace",
                pbm_path,
                "--svg",
                "--output", svg_path,
                "--turdsize", str(self.default_params["turdsize"]),
                "--alphamax", str(self.default_params["alphamax"]),
                "--opttolerance", str(self.default_params["opttolerance"]),
            ]

            if not self.default_params["opticurve"]:
                cmd.append("--longcurve")

            try:
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=60,
                    check=True
                )
            except FileNotFoundError:
                logger.error("potrace binary not found. Returning placeholder SVG.")
                return self._placeholder_svg(width, height)
            except subprocess.CalledProcessError as e:
                logger.error(f"potrace failed: {e.stderr}")
                return self._placeholder_svg(width, height)
            except subprocess.TimeoutExpired:
                logger.error("potrace timed out. Returning placeholder SVG.")
                return self._placeholder_svg(width, height)

            with open(svg_path, "r", encoding="utf-8") as f:
                svg_content = f.read()

        logger.info(f"Vectorization (CLI) complete: {len(svg_content)} bytes SVG")
        return svg_content

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _placeholder_svg(self, width: int, height: int) -> str:
        """Returns a minimal valid empty SVG as a last-resort fallback."""
        return (
            f'<svg xmlns="http://www.w3.org/2000/svg" '
            f'width="{width}" height="{height}" '
            f'viewBox="0 0 {width} {height}" version="1.1"></svg>'
        )

    def _path_to_svg(self, path, width: int, height: int) -> str:
        """
        Convertit Potrace path (pypotrace) en SVG.
        """
        svg = ET.Element('svg', {
            'xmlns': 'http://www.w3.org/2000/svg',
            'width': str(width),
            'height': str(height),
            'viewBox': f'0 0 {width} {height}',
            'version': '1.1'
        })

        for curve in path:
            path_data = []

            start_point = curve.start_point
            path_data.append(f'M {start_point.x},{start_point.y}')

            for segment in curve.segments:
                if segment.is_corner:
                    c = segment.c
                    path_data.append(f'L {c.x},{c.y}')
                    end = segment.end_point
                    path_data.append(f'L {end.x},{end.y}')
                else:
                    c1 = segment.c1
                    c2 = segment.c2
                    end = segment.end_point
                    path_data.append(
                        f'C {c1.x},{c1.y} {c2.x},{c2.y} {end.x},{end.y}'
                    )

            path_data.append('Z')

            path_elem = ET.Element('path', {
                'd': ' '.join(path_data),
                'fill': 'black',
                'stroke': 'none'
            })
            svg.append(path_elem)

        return ET.tostring(svg, encoding='unicode')

    def optimize_svg(self, svg_content: str) -> str:
        """
        Optimise SVG pour réduire taille et améliorer qualité.

        Uses scour if available, otherwise basic optimization.
        """
        try:
            import scour.scour

            options = scour.scour.sanitizeOptions()
            options.strip_xml_prolog = True
            options.remove_metadata = True
            options.indent_type = 'space'
            options.indent_depth = 2
            options.newlines = True
            options.strip_comments = True
            options.remove_descriptive_elements = True

            optimized = scour.scour.scourString(svg_content, options)
            logger.info("SVG optimized with scour")
            return optimized

        except ImportError:
            logger.warning("scour not available, using basic optimization")
            return self._basic_svg_optimization(svg_content)

    def _basic_svg_optimization(self, svg_content: str) -> str:
        """Basic SVG optimization without scour."""
        root = ET.fromstring(svg_content)

        for elem in root.iter():
            if elem.tag is ET.Comment:
                root.remove(elem)

        self._indent_xml(root)
        return ET.tostring(root, encoding='unicode')

    def _indent_xml(self, elem, level=0):
        """Add indentation to XML for readability."""
        indent = "\n" + "  " * level
        if len(elem):
            if not elem.text or not elem.text.strip():
                elem.text = indent + "  "
            if not elem.tail or not elem.tail.strip():
                elem.tail = indent
            for child in elem:
                self._indent_xml(child, level + 1)
            if not child.tail or not child.tail.strip():
                child.tail = indent
        else:
            if level and (not elem.tail or not elem.tail.strip()):
                elem.tail = indent


# Global instance
vectorizer = VectorizationService()
