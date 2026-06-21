#!/usr/bin/env python3
"""
pdf_converter.py

Convert DOCX to PDF using LibreOffice Headless.

Usage:
    python pdf_converter.py --input recipe.docx --output recipe.pdf

    or as HTTP endpoint:
    POST /convert
    {"docx_path": "/path/to/file.docx"}
"""

import subprocess
import sys
import argparse
import os
import tempfile
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# Configuration
LIBREOFFICE_PATH = os.getenv("LIBREOFFICE_PATH", "/usr/bin/soffice")
PDF_CONVERSION_TIMEOUT = int(os.getenv("PDF_CONVERSION_TIMEOUT", 30))


def convert_docx_to_pdf(docx_path: str, pdf_path: str = None) -> str:
    """
    Convert DOCX file to PDF using LibreOffice Headless.

    Args:
        docx_path: Path to input DOCX file
        pdf_path: Path to output PDF file (default: same directory as docx_path)

    Returns:
        Path to generated PDF file
    """

    # TODO: Implement DOCX to PDF conversion
    # Requirements:
    # 1. Check LibreOffice is installed
    # 2. Validate input file exists
    # 3. Run: soffice --headless --convert-to pdf --outdir /path /input.docx
    # 4. Verify output file was created
    # 5. Return PDF path

    raise NotImplementedError("PDF conversion not yet implemented")


def main():
    """Command-line interface."""
    parser = argparse.ArgumentParser(description="Convert DOCX to PDF")
    parser.add_argument("--input", "-i", required=True, help="Input DOCX file path")
    parser.add_argument("--output", "-o", help="Output PDF file path (optional)")
    parser.add_argument("--server", action="store_true", help="Run as Flask server")
    parser.add_argument("--port", default=5002, type=int, help="Server port (default: 5002)")

    args = parser.parse_args()

    if args.server:
        # TODO: Implement Flask server
        # POST /convert
        # Input: {"docx_path": "..."}
        # Output: {"pdf_path": "...", "success": true}

        try:
            from flask import Flask, request, jsonify
        except ImportError:
            print("Error: Flask not installed. Install with: pip install flask", file=sys.stderr)
            sys.exit(1)

        app = Flask(__name__)

        @app.route("/convert", methods=["POST"])
        def convert_endpoint():
            try:
                data = request.json
                docx_path = data.get("docx_path")

                if not docx_path:
                    return jsonify({"error": "docx_path field required"}), 400

                pdf_path = convert_docx_to_pdf(docx_path)

                return jsonify({
                    "pdf_path": pdf_path,
                    "success": True
                }), 200

            except Exception as e:
                return jsonify({"error": str(e)}), 500

        @app.route("/health", methods=["GET"])
        def health():
            return jsonify({"status": "ok"}), 200

        print(f"Starting Flask server on port {args.port}...")
        app.run(host="0.0.0.0", port=args.port, debug=False)

    else:
        # CLI mode
        if not os.path.exists(args.input):
            print(f"Error: Input file not found: {args.input}", file=sys.stderr)
            sys.exit(1)

        try:
            pdf_path = convert_docx_to_pdf(args.input, args.output)
            print(f"✓ Converted: {pdf_path}")
        except Exception as e:
            print(f"Conversion failed: {str(e)}", file=sys.stderr)
            sys.exit(1)


if __name__ == "__main__":
    main()
