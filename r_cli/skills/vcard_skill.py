"""
vCard Skill for R CLI.

vCard (VCF) utilities:
- Parse vCard files
- Generate contact cards
- Export to VCF format
"""

import json
import uuid
from typing import Optional

from r_cli.core.agent import Skill
from r_cli.core.llm import Tool


class VCardSkill(Skill):
    """Skill for vCard operations."""

    name = "vcard"
    description = "vCard: parse and generate VCF contact files"

    def get_tools(self) -> list[Tool]:
        return [
            Tool(
                name="vcard_parse",
                description="Parse a vCard file",
                parameters={
                    "type": "object",
                    "properties": {
                        "content": {
                            "type": "string",
                            "description": "VCF file content",
                        },
                    },
                    "required": ["content"],
                },
                handler=self.vcard_parse,
            ),
            Tool(
                name="vcard_create",
                description="Create a vCard contact",
                parameters={
                    "type": "object",
                    "properties": {
                        "name": {
                            "type": "string",
                            "description": "Full name",
                        },
                        "email": {
                            "type": "string",
                            "description": "Email address",
                        },
                        "phone": {
                            "type": "string",
                            "description": "Phone number",
                        },
                        "organization": {
                            "type": "string",
                            "description": "Organization/company",
                        },
                        "title": {
                            "type": "string",
                            "description": "Job title",
                        },
                        "address": {
                            "type": "string",
                            "description": "Address",
                        },
                        "url": {
                            "type": "string",
                            "description": "Website URL",
                        },
                    },
                    "required": ["name"],
                },
                handler=self.vcard_create,
            ),
            Tool(
                name="vcard_generate",
                description="Generate VCF file from contacts",
                parameters={
                    "type": "object",
                    "properties": {
                        "contacts": {
                            "type": "array",
                            "description": "List of contacts",
                        },
                    },
                    "required": ["contacts"],
                },
                handler=self.vcard_generate,
            ),
            Tool(
                name="vcard_to_json",
                description="Convert VCF to JSON",
                parameters={
                    "type": "object",
                    "properties": {
                        "content": {
                            "type": "string",
                            "description": "VCF content",
                        },
                    },
                    "required": ["content"],
                },
                handler=self.vcard_to_json,
            ),
            Tool(
                name="vcard_merge",
                description="Merge multiple vCards",
                parameters={
                    "type": "object",
                    "properties": {
                        "vcards": {
                            "type": "array",
                            "description": "List of vCard strings",
                        },
                    },
                    "required": ["vcards"],
                },
                handler=self.vcard_merge,
            ),
        ]

    def _unfold_lines(self, content: str) -> list[str]:
        """Unfold wrapped lines in vCard."""
        lines = []
        current = ""

        for line in content.replace("\r\n", "\n").split("\n"):
            if line.startswith((" ", "\t")):
                current += line[1:]
            else:
                if current:
                    lines.append(current)
                current = line

        if current:
            lines.append(current)

        return lines

    def _parse_single_vcard(self, lines: list[str]) -> dict:
        """Parse a single vCard from lines."""
        contact = {}

        for line in lines:
            if ":" not in line:
                continue

            key_part, value = line.split(":", 1)
            key = key_part.split(";")[0].upper()
            params = key_part.split(";")[1:] if ";" in key_part else []

            if key == "N":
                parts = value.split(";")
                contact["name"] = {
                    "family": parts[0] if len(parts) > 0 else "",
                    "given": parts[1] if len(parts) > 1 else "",
                    "middle": parts[2] if len(parts) > 2 else "",
                    "prefix": parts[3] if len(parts) > 3 else "",
                    "suffix": parts[4] if len(parts) > 4 else "",
                }
            elif key == "FN":
                contact["fullName"] = value
            elif key == "EMAIL":
                if "emails" not in contact:
                    contact["emails"] = []
                email_type = "other"
                for p in params:
                    if "TYPE=" in p.upper():
                        email_type = p.split("=")[1].lower()
                contact["emails"].append({"type": email_type, "value": value})
            elif key == "TEL":
                if "phones" not in contact:
                    contact["phones"] = []
                phone_type = "other"
                for p in params:
                    if "TYPE=" in p.upper():
                        phone_type = p.split("=")[1].lower()
                contact["phones"].append({"type": phone_type, "value": value})
            elif key == "ORG":
                contact["organization"] = value.replace(";", ", ")
            elif key == "TITLE":
                contact["title"] = value
            elif key == "URL":
                contact["url"] = value
            elif key == "ADR":
                parts = value.split(";")
                contact["address"] = {
                    "poBox": parts[0] if len(parts) > 0 else "",
                    "extended": parts[1] if len(parts) > 1 else "",
                    "street": parts[2] if len(parts) > 2 else "",
                    "city": parts[3] if len(parts) > 3 else "",
                    "region": parts[4] if len(parts) > 4 else "",
                    "postal": parts[5] if len(parts) > 5 else "",
                    "country": parts[6] if len(parts) > 6 else "",
                }
            elif key == "NOTE":
                contact["note"] = value.replace("\\n", "\n")
            elif key == "BDAY":
                contact["birthday"] = value
            elif key == "UID":
                contact["uid"] = value

        return contact

    def vcard_parse(self, content: str) -> str:
        """Parse vCard content."""
        lines = self._unfold_lines(content)

        contacts = []
        current_lines = []
        in_vcard = False

        for line in lines:
            if line.upper().startswith("BEGIN:VCARD"):
                in_vcard = True
                current_lines = []
            elif line.upper().startswith("END:VCARD"):
                if current_lines:
                    contact = self._parse_single_vcard(current_lines)
                    contacts.append(contact)
                in_vcard = False
            elif in_vcard:
                current_lines.append(line)

        return json.dumps({
            "contact_count": len(contacts),
            "contacts": contacts,
        }, indent=2)

    def vcard_create(
        self,
        name: str,
        email: Optional[str] = None,
        phone: Optional[str] = None,
        organization: Optional[str] = None,
        title: Optional[str] = None,
        address: Optional[str] = None,
        url: Optional[str] = None,
    ) -> str:
        """Create single vCard."""
        # Parse name
        name_parts = name.split()
        if len(name_parts) >= 2:
            given = name_parts[0]
            family = " ".join(name_parts[1:])
        else:
            given = name
            family = ""

        uid = str(uuid.uuid4())

        lines = [
            "BEGIN:VCARD",
            "VERSION:3.0",
            f"UID:{uid}",
            f"N:{family};{given};;;",
            f"FN:{name}",
        ]

        if email:
            lines.append(f"EMAIL;TYPE=INTERNET:{email}")
        if phone:
            lines.append(f"TEL;TYPE=CELL:{phone}")
        if organization:
            lines.append(f"ORG:{organization}")
        if title:
            lines.append(f"TITLE:{title}")
        if address:
            lines.append(f"ADR;TYPE=HOME:;;{address};;;;")
        if url:
            lines.append(f"URL:{url}")

        lines.append("END:VCARD")

        return "\r\n".join(lines)

    def vcard_generate(self, contacts: list) -> str:
        """Generate VCF from contacts list."""
        vcards = []

        for contact in contacts:
            if isinstance(contact, str):
                contact = {"name": contact}

            name = contact.get("name", "Unknown")
            vcard = self.vcard_create(
                name=name,
                email=contact.get("email"),
                phone=contact.get("phone"),
                organization=contact.get("organization"),
                title=contact.get("title"),
                address=contact.get("address"),
                url=contact.get("url"),
            )
            vcards.append(vcard)

        return "\r\n".join(vcards)

    def vcard_to_json(self, content: str) -> str:
        """Convert VCF to JSON."""
        return self.vcard_parse(content)

    def vcard_merge(self, vcards: list) -> str:
        """Merge multiple vCards."""
        merged = []
        for vcard in vcards:
            merged.append(vcard.strip())
        return "\r\n".join(merged)

    def execute(self, **kwargs) -> str:
        """Direct skill execution."""
        if "content" in kwargs:
            return self.vcard_parse(kwargs["content"])
        return "Provide VCF content to parse"
