"""
XML Skill for R CLI.

XML utilities:
- Parse and navigate
- XPath queries
- Convert to/from JSON
- Validate
"""

import json
import xml.etree.ElementTree as ET
from typing import Optional

from r_cli.core.agent import Skill
from r_cli.core.llm import Tool


class XMLSkill(Skill):
    """Skill for XML operations."""

    name = "xml"
    description = "XML: parse, xpath, convert, validate"

    def get_tools(self) -> list[Tool]:
        return [
            Tool(
                name="xml_parse",
                description="Parse XML and show structure",
                parameters={
                    "type": "object",
                    "properties": {
                        "xml": {
                            "type": "string",
                            "description": "XML content",
                        },
                    },
                    "required": ["xml"],
                },
                handler=self.xml_parse,
            ),
            Tool(
                name="xml_xpath",
                description="Query XML with XPath",
                parameters={
                    "type": "object",
                    "properties": {
                        "xml": {
                            "type": "string",
                            "description": "XML content",
                        },
                        "xpath": {
                            "type": "string",
                            "description": "XPath expression",
                        },
                    },
                    "required": ["xml", "xpath"],
                },
                handler=self.xml_xpath,
            ),
            Tool(
                name="xml_to_json",
                description="Convert XML to JSON",
                parameters={
                    "type": "object",
                    "properties": {
                        "xml": {
                            "type": "string",
                            "description": "XML content",
                        },
                    },
                    "required": ["xml"],
                },
                handler=self.xml_to_json,
            ),
            Tool(
                name="json_to_xml",
                description="Convert JSON to XML",
                parameters={
                    "type": "object",
                    "properties": {
                        "json_data": {
                            "type": "string",
                            "description": "JSON content",
                        },
                        "root_name": {
                            "type": "string",
                            "description": "Root element name (default: root)",
                        },
                    },
                    "required": ["json_data"],
                },
                handler=self.json_to_xml,
            ),
            Tool(
                name="xml_validate",
                description="Validate XML syntax",
                parameters={
                    "type": "object",
                    "properties": {
                        "xml": {
                            "type": "string",
                            "description": "XML content",
                        },
                    },
                    "required": ["xml"],
                },
                handler=self.xml_validate,
            ),
            Tool(
                name="xml_prettify",
                description="Format/prettify XML",
                parameters={
                    "type": "object",
                    "properties": {
                        "xml": {
                            "type": "string",
                            "description": "XML content",
                        },
                    },
                    "required": ["xml"],
                },
                handler=self.xml_prettify,
            ),
            Tool(
                name="xml_extract_text",
                description="Extract all text content from XML",
                parameters={
                    "type": "object",
                    "properties": {
                        "xml": {
                            "type": "string",
                            "description": "XML content",
                        },
                    },
                    "required": ["xml"],
                },
                handler=self.xml_extract_text,
            ),
        ]

    def _element_to_dict(self, element: ET.Element) -> dict:
        """Convert XML element to dictionary."""
        result = {}

        # Attributes
        if element.attrib:
            result["@attributes"] = dict(element.attrib)

        # Children
        children = list(element)
        if children:
            child_dict = {}
            for child in children:
                child_data = self._element_to_dict(child)
                if child.tag in child_dict:
                    # Multiple children with same tag -> list
                    if not isinstance(child_dict[child.tag], list):
                        child_dict[child.tag] = [child_dict[child.tag]]
                    child_dict[child.tag].append(child_data)
                else:
                    child_dict[child.tag] = child_data
            result.update(child_dict)

        # Text content
        if element.text and element.text.strip():
            if result:
                result["#text"] = element.text.strip()
            else:
                return element.text.strip()

        return result if result else ""

    def _dict_to_xml(self, data: dict, parent: ET.Element, item_name: str = "item"):
        """Convert dictionary to XML elements."""
        if isinstance(data, dict):
            for key, value in data.items():
                if key.startswith("@"):
                    # Attribute
                    parent.set(key[1:], str(value))
                elif key == "#text":
                    parent.text = str(value)
                elif isinstance(value, list):
                    for item in value:
                        child = ET.SubElement(parent, key)
                        self._dict_to_xml(item, child, item_name)
                elif isinstance(value, dict):
                    child = ET.SubElement(parent, key)
                    self._dict_to_xml(value, child, item_name)
                else:
                    child = ET.SubElement(parent, key)
                    child.text = str(value)
        elif isinstance(data, list):
            for item in data:
                child = ET.SubElement(parent, item_name)
                self._dict_to_xml(item, child, item_name)
        else:
            parent.text = str(data)

    def xml_parse(self, xml: str) -> str:
        """Parse XML and show structure."""
        try:
            root = ET.fromstring(xml)

            def describe(element, depth=0):
                result = {
                    "tag": element.tag,
                    "attributes": dict(element.attrib) if element.attrib else None,
                    "text": element.text.strip() if element.text and element.text.strip() else None,
                    "children": [describe(child, depth + 1) for child in element],
                }
                return {k: v for k, v in result.items() if v}

            return json.dumps({
                "root": root.tag,
                "structure": describe(root),
            }, indent=2)

        except ET.ParseError as e:
            return f"XML parse error: {e}"
        except Exception as e:
            return f"Error: {e}"

    def xml_xpath(self, xml: str, xpath: str) -> str:
        """Query XML with XPath."""
        try:
            root = ET.fromstring(xml)
            results = root.findall(xpath)

            if not results:
                return json.dumps({"count": 0, "results": []}, indent=2)

            output = []
            for elem in results:
                if elem.text and elem.text.strip():
                    output.append({
                        "tag": elem.tag,
                        "text": elem.text.strip(),
                        "attributes": dict(elem.attrib) if elem.attrib else None,
                    })
                else:
                    output.append({
                        "tag": elem.tag,
                        "attributes": dict(elem.attrib) if elem.attrib else None,
                        "children": len(list(elem)),
                    })

            return json.dumps({"count": len(output), "results": output}, indent=2)

        except ET.ParseError as e:
            return f"XML parse error: {e}"
        except Exception as e:
            return f"Error: {e}"

    def xml_to_json(self, xml: str) -> str:
        """Convert XML to JSON."""
        try:
            root = ET.fromstring(xml)
            result = {root.tag: self._element_to_dict(root)}
            return json.dumps(result, indent=2)

        except ET.ParseError as e:
            return f"XML parse error: {e}"
        except Exception as e:
            return f"Error: {e}"

    def json_to_xml(self, json_data: str, root_name: str = "root") -> str:
        """Convert JSON to XML."""
        try:
            data = json.loads(json_data)

            root = ET.Element(root_name)
            self._dict_to_xml(data, root)

            # Pretty print
            return self._prettify_element(root)

        except json.JSONDecodeError as e:
            return f"JSON parse error: {e}"
        except Exception as e:
            return f"Error: {e}"

    def xml_validate(self, xml: str) -> str:
        """Validate XML syntax."""
        try:
            root = ET.fromstring(xml)

            # Count elements
            count = sum(1 for _ in root.iter())

            return json.dumps({
                "valid": True,
                "root_element": root.tag,
                "total_elements": count,
            }, indent=2)

        except ET.ParseError as e:
            return json.dumps({
                "valid": False,
                "error": str(e),
            }, indent=2)

    def _prettify_element(self, element: ET.Element, indent: int = 0) -> str:
        """Prettify XML element."""
        result = []
        prefix = "  " * indent

        # Start tag
        attrs = " ".join(f'{k}="{v}"' for k, v in element.attrib.items())
        tag_open = f"{prefix}<{element.tag}"
        if attrs:
            tag_open += f" {attrs}"

        children = list(element)
        if not children and not element.text:
            result.append(f"{tag_open}/>")
        else:
            result.append(f"{tag_open}>")

            if element.text and element.text.strip():
                if children:
                    result.append(f"{prefix}  {element.text.strip()}")
                else:
                    result[-1] = result[-1] + element.text.strip() + f"</{element.tag}>"
                    return "\n".join(result)

            for child in children:
                result.append(self._prettify_element(child, indent + 1))

            result.append(f"{prefix}</{element.tag}>")

        return "\n".join(result)

    def xml_prettify(self, xml: str) -> str:
        """Format/prettify XML."""
        try:
            root = ET.fromstring(xml)
            return '<?xml version="1.0" encoding="UTF-8"?>\n' + self._prettify_element(root)

        except ET.ParseError as e:
            return f"XML parse error: {e}"
        except Exception as e:
            return f"Error: {e}"

    def xml_extract_text(self, xml: str) -> str:
        """Extract all text content."""
        try:
            root = ET.fromstring(xml)
            texts = []

            for elem in root.iter():
                if elem.text and elem.text.strip():
                    texts.append(elem.text.strip())
                if elem.tail and elem.tail.strip():
                    texts.append(elem.tail.strip())

            return "\n".join(texts)

        except ET.ParseError as e:
            return f"XML parse error: {e}"
        except Exception as e:
            return f"Error: {e}"

    def execute(self, **kwargs) -> str:
        """Direct skill execution."""
        action = kwargs.get("action", "parse")
        if action == "parse":
            return self.xml_parse(kwargs.get("xml", ""))
        return f"Unknown action: {action}"
