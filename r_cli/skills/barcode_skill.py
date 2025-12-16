"""
Barcode Skill for R CLI.

Barcode utilities:
- Generate barcodes (EAN, UPC, Code128, etc.)
- Read barcodes from images
"""

import json
from pathlib import Path
from typing import Optional

from r_cli.core.agent import Skill
from r_cli.core.llm import Tool


class BarcodeSkill(Skill):
    """Skill for barcode operations."""

    name = "barcode"
    description = "Barcode: generate and read barcodes"

    def get_tools(self) -> list[Tool]:
        return [
            Tool(
                name="barcode_generate",
                description="Generate a barcode image",
                parameters={
                    "type": "object",
                    "properties": {
                        "data": {
                            "type": "string",
                            "description": "Data to encode",
                        },
                        "output": {
                            "type": "string",
                            "description": "Output file path (PNG/SVG)",
                        },
                        "barcode_type": {
                            "type": "string",
                            "description": "Type: code128, ean13, ean8, upc, isbn, code39",
                        },
                    },
                    "required": ["data", "output"],
                },
                handler=self.barcode_generate,
            ),
            Tool(
                name="barcode_read",
                description="Read barcode from image",
                parameters={
                    "type": "object",
                    "properties": {
                        "image_path": {
                            "type": "string",
                            "description": "Path to image with barcode",
                        },
                    },
                    "required": ["image_path"],
                },
                handler=self.barcode_read,
            ),
            Tool(
                name="barcode_validate",
                description="Validate barcode data (check digit)",
                parameters={
                    "type": "object",
                    "properties": {
                        "data": {
                            "type": "string",
                            "description": "Barcode data to validate",
                        },
                        "barcode_type": {
                            "type": "string",
                            "description": "Type: ean13, ean8, upc, isbn",
                        },
                    },
                    "required": ["data", "barcode_type"],
                },
                handler=self.barcode_validate,
            ),
            Tool(
                name="barcode_checksum",
                description="Calculate check digit for barcode",
                parameters={
                    "type": "object",
                    "properties": {
                        "data": {
                            "type": "string",
                            "description": "Barcode data (without check digit)",
                        },
                        "barcode_type": {
                            "type": "string",
                            "description": "Type: ean13, ean8, upc",
                        },
                    },
                    "required": ["data", "barcode_type"],
                },
                handler=self.barcode_checksum,
            ),
        ]

    def barcode_generate(
        self,
        data: str,
        output: str,
        barcode_type: str = "code128",
    ) -> str:
        """Generate barcode image."""
        try:
            import barcode
            from barcode.writer import ImageWriter

            # Map type names
            type_map = {
                "code128": "code128",
                "ean13": "ean13",
                "ean8": "ean8",
                "upc": "upca",
                "upca": "upca",
                "isbn": "isbn13",
                "isbn13": "isbn13",
                "isbn10": "isbn10",
                "code39": "code39",
                "pzn": "pzn",
                "jan": "jan",
                "itf": "itf",
            }

            bc_type = type_map.get(barcode_type.lower(), barcode_type.lower())

            try:
                bc_class = barcode.get_barcode_class(bc_type)
            except barcode.errors.BarcodeNotFoundError:
                return f"Unknown barcode type: {barcode_type}. Available: {', '.join(type_map.keys())}"

            output_path = Path(output).expanduser()

            if output_path.suffix.lower() == '.svg':
                bc = bc_class(data)
                bc.save(str(output_path.with_suffix('')))
            else:
                bc = bc_class(data, writer=ImageWriter())
                bc.save(str(output_path.with_suffix('')))

            return f"Barcode saved to {output}"

        except ImportError:
            return "Error: python-barcode not installed. Run: pip install python-barcode[images]"
        except Exception as e:
            return f"Error: {e}"

    def barcode_read(self, image_path: str) -> str:
        """Read barcode from image."""
        try:
            from PIL import Image
            import pyzbar.pyzbar as pyzbar

            path = Path(image_path).expanduser()
            if not path.exists():
                return f"File not found: {image_path}"

            img = Image.open(path)
            decoded = pyzbar.decode(img)

            if not decoded:
                return "No barcode found in image"

            results = []
            for obj in decoded:
                results.append({
                    "type": obj.type,
                    "data": obj.data.decode("utf-8"),
                })

            return json.dumps(results, indent=2)

        except ImportError:
            return "Error: pyzbar not installed. Run: pip install pyzbar pillow"
        except Exception as e:
            return f"Error: {e}"

    def barcode_validate(self, data: str, barcode_type: str) -> str:
        """Validate barcode data."""
        try:
            bc_type = barcode_type.lower()
            data = data.replace("-", "").replace(" ", "")

            if bc_type in ["ean13", "jan"]:
                if len(data) != 13:
                    return json.dumps({"valid": False, "reason": "EAN-13 must be 13 digits"})
                check = self._calculate_ean_check(data[:-1])
                valid = check == int(data[-1])

            elif bc_type == "ean8":
                if len(data) != 8:
                    return json.dumps({"valid": False, "reason": "EAN-8 must be 8 digits"})
                check = self._calculate_ean_check(data[:-1])
                valid = check == int(data[-1])

            elif bc_type in ["upc", "upca"]:
                if len(data) != 12:
                    return json.dumps({"valid": False, "reason": "UPC-A must be 12 digits"})
                check = self._calculate_upc_check(data[:-1])
                valid = check == int(data[-1])

            elif bc_type == "isbn":
                if len(data) == 13:
                    check = self._calculate_ean_check(data[:-1])
                    valid = check == int(data[-1])
                elif len(data) == 10:
                    check = self._calculate_isbn10_check(data[:-1])
                    valid = str(check) == data[-1].upper()
                else:
                    return json.dumps({"valid": False, "reason": "ISBN must be 10 or 13 digits"})
            else:
                return f"Validation not supported for type: {barcode_type}"

            return json.dumps({
                "data": data,
                "type": barcode_type,
                "valid": valid,
                "check_digit": data[-1],
                "calculated": str(check),
            }, indent=2)

        except Exception as e:
            return f"Error: {e}"

    def barcode_checksum(self, data: str, barcode_type: str) -> str:
        """Calculate check digit."""
        try:
            bc_type = barcode_type.lower()
            data = data.replace("-", "").replace(" ", "")

            if bc_type in ["ean13", "jan"]:
                if len(data) != 12:
                    return "EAN-13 needs 12 digits (without check digit)"
                check = self._calculate_ean_check(data)

            elif bc_type == "ean8":
                if len(data) != 7:
                    return "EAN-8 needs 7 digits (without check digit)"
                check = self._calculate_ean_check(data)

            elif bc_type in ["upc", "upca"]:
                if len(data) != 11:
                    return "UPC-A needs 11 digits (without check digit)"
                check = self._calculate_upc_check(data)

            else:
                return f"Checksum not supported for type: {barcode_type}"

            return json.dumps({
                "data": data,
                "check_digit": check,
                "complete": data + str(check),
            }, indent=2)

        except Exception as e:
            return f"Error: {e}"

    def _calculate_ean_check(self, data: str) -> int:
        """Calculate EAN check digit."""
        total = 0
        for i, digit in enumerate(data):
            if i % 2 == 0:
                total += int(digit)
            else:
                total += int(digit) * 3
        return (10 - (total % 10)) % 10

    def _calculate_upc_check(self, data: str) -> int:
        """Calculate UPC check digit."""
        odd_sum = sum(int(data[i]) for i in range(0, len(data), 2))
        even_sum = sum(int(data[i]) for i in range(1, len(data), 2))
        total = odd_sum * 3 + even_sum
        return (10 - (total % 10)) % 10

    def _calculate_isbn10_check(self, data: str) -> str:
        """Calculate ISBN-10 check digit."""
        total = sum((10 - i) * int(digit) for i, digit in enumerate(data))
        check = (11 - (total % 11)) % 11
        return "X" if check == 10 else str(check)

    def execute(self, **kwargs) -> str:
        """Direct skill execution."""
        action = kwargs.get("action", "generate")
        if action == "generate":
            return self.barcode_generate(
                kwargs.get("data", "123456789012"),
                kwargs.get("output", "barcode.png"),
            )
        return f"Unknown action: {action}"
