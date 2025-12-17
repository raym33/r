"""
HubLab Skill for R CLI.

Integration with HubLab.dev - Universal Capsule Compiler.
Access 8,150+ pre-built UI capsules for multi-platform development.

Features:
- Search capsules by name, category, or tags
- Get capsule details and code
- List categories and explore the catalog
- Suggest components for app descriptions
- COMPOSE: Generate full applications from descriptions
"""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Optional

from r_cli.core.agent import Skill
from r_cli.core.llm import Tool


class HubLabSkill(Skill):
    """Skill for HubLab capsule operations."""

    name = "hublab"
    description = "HubLab: search 8,150+ UI capsules, compose full applications"

    # Default paths
    HUBLAB_PATH = os.environ.get("HUBLAB_PATH", "/Users/c/hublab")
    METADATA_FILE = "lib/capsules-metadata.json"
    CAPSULES_FILE = "lib/all-capsules.ts"
    API_BASE = "https://hublab.dev/api"

    # App architecture templates
    APP_TEMPLATES = {
        "web": {
            "framework": "Next.js 14",
            "styling": "Tailwind CSS",
            "structure": [
                "app/",
                "app/page.tsx",
                "app/layout.tsx",
                "app/globals.css",
                "components/",
                "components/ui/",
                "lib/",
                "lib/utils.ts",
                "public/",
                "package.json",
                "tailwind.config.js",
                "tsconfig.json",
            ],
        },
        "mobile": {
            "framework": "React Native / Expo",
            "styling": "NativeWind",
            "structure": [
                "app/",
                "components/",
                "hooks/",
                "lib/",
                "assets/",
            ],
        },
        "desktop": {
            "framework": "Tauri + React",
            "styling": "Tailwind CSS",
            "structure": [
                "src/",
                "src-tauri/",
                "components/",
            ],
        },
    }

    # Feature detection patterns
    FEATURE_PATTERNS = {
        "auth": {
            "keywords": [
                "login",
                "signin",
                "signup",
                "register",
                "auth",
                "password",
                "oauth",
                "sso",
            ],
            "capsules": [
                "auth-login",
                "auth-register",
                "auth-forgot-password",
                "auth-oauth",
                "auth-guard",
            ],
            "category": "Authentication",
        },
        "dashboard": {
            "keywords": ["dashboard", "admin", "panel", "analytics", "metrics", "kpi", "stats"],
            "capsules": [
                "dashboard-layout",
                "stats-card",
                "chart-line",
                "chart-bar",
                "chart-pie",
                "data-table",
            ],
            "category": "Dashboard",
        },
        "ecommerce": {
            "keywords": [
                "shop",
                "store",
                "cart",
                "checkout",
                "product",
                "payment",
                "order",
                "ecommerce",
            ],
            "capsules": [
                "product-card",
                "shopping-cart",
                "checkout-form",
                "payment-stripe",
                "order-summary",
            ],
            "category": "E-commerce",
        },
        "chat": {
            "keywords": ["chat", "message", "messenger", "conversation", "realtime", "inbox"],
            "capsules": [
                "chat-bubble",
                "chat-input",
                "chat-list",
                "message-thread",
                "typing-indicator",
            ],
            "category": "Chat",
        },
        "social": {
            "keywords": ["social", "feed", "post", "profile", "follow", "like", "comment", "share"],
            "capsules": [
                "post-card",
                "user-profile",
                "feed-list",
                "comment-section",
                "like-button",
            ],
            "category": "Social",
        },
        "forms": {
            "keywords": ["form", "input", "survey", "contact", "feedback", "submit"],
            "capsules": [
                "form-input",
                "form-select",
                "form-textarea",
                "form-checkbox",
                "form-submit",
            ],
            "category": "Forms",
        },
        "crud": {
            "keywords": ["crud", "create", "edit", "delete", "list", "table", "manage"],
            "capsules": ["data-table", "crud-form", "delete-dialog", "edit-modal", "pagination"],
            "category": "Data",
        },
        "media": {
            "keywords": ["image", "video", "gallery", "upload", "media", "player", "carousel"],
            "capsules": [
                "image-gallery",
                "video-player",
                "file-upload",
                "media-carousel",
                "lightbox",
            ],
            "category": "Media",
        },
        "navigation": {
            "keywords": ["menu", "navbar", "sidebar", "navigation", "breadcrumb", "tabs"],
            "capsules": ["navbar", "sidebar", "breadcrumb", "tabs", "mobile-nav", "footer"],
            "category": "Navigation",
        },
        "notifications": {
            "keywords": ["notification", "alert", "toast", "badge", "bell"],
            "capsules": ["toast", "alert-banner", "notification-badge", "notification-center"],
            "category": "Notifications",
        },
        "settings": {
            "keywords": ["settings", "preferences", "config", "options", "theme", "account"],
            "capsules": ["settings-form", "theme-toggle", "account-settings", "preferences-panel"],
            "category": "Settings",
        },
        "landing": {
            "keywords": ["landing", "hero", "features", "pricing", "testimonials", "cta"],
            "capsules": [
                "hero-section",
                "features-grid",
                "pricing-table",
                "testimonials",
                "cta-banner",
            ],
            "category": "Marketing",
        },
    }

    def __init__(self, config=None):
        """Initialize HubLab skill."""
        super().__init__(config)
        self._capsules_cache: Optional[list] = None
        self._categories_cache: Optional[dict] = None

    def get_tools(self) -> list[Tool]:
        return [
            Tool(
                name="hublab_compose",
                description="Generate a complete application from a description using HubLab capsules",
                parameters={
                    "type": "object",
                    "properties": {
                        "description": {
                            "type": "string",
                            "description": "Full description of the app to build",
                        },
                        "platform": {
                            "type": "string",
                            "description": "Target platform: web (default), mobile, desktop",
                        },
                        "output_dir": {
                            "type": "string",
                            "description": "Output directory for generated project",
                        },
                        "app_name": {
                            "type": "string",
                            "description": "Name of the application",
                        },
                    },
                    "required": ["description"],
                },
                handler=self.hublab_compose,
            ),
            Tool(
                name="hublab_search",
                description="Search HubLab capsules by name, category, or tags",
                parameters={
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Search query (name, tag, or description)",
                        },
                        "category": {
                            "type": "string",
                            "description": "Filter by category (e.g., UI, Layout, Form)",
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Max results (default: 20)",
                        },
                    },
                    "required": ["query"],
                },
                handler=self.hublab_search,
            ),
            Tool(
                name="hublab_capsule",
                description="Get details for a specific capsule",
                parameters={
                    "type": "object",
                    "properties": {
                        "capsule_id": {
                            "type": "string",
                            "description": "Capsule ID (e.g., button, card, form)",
                        },
                    },
                    "required": ["capsule_id"],
                },
                handler=self.hublab_capsule,
            ),
            Tool(
                name="hublab_categories",
                description="List all capsule categories with counts",
                parameters={
                    "type": "object",
                    "properties": {},
                },
                handler=self.hublab_categories,
            ),
            Tool(
                name="hublab_browse",
                description="Browse capsules by category",
                parameters={
                    "type": "object",
                    "properties": {
                        "category": {
                            "type": "string",
                            "description": "Category to browse",
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Max results (default: 30)",
                        },
                    },
                    "required": ["category"],
                },
                handler=self.hublab_browse,
            ),
            Tool(
                name="hublab_suggest",
                description="Suggest capsules for an app description",
                parameters={
                    "type": "object",
                    "properties": {
                        "description": {
                            "type": "string",
                            "description": "App or feature description",
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Max suggestions (default: 15)",
                        },
                    },
                    "required": ["description"],
                },
                handler=self.hublab_suggest,
            ),
            Tool(
                name="hublab_code",
                description="Get React/TypeScript code for a capsule",
                parameters={
                    "type": "object",
                    "properties": {
                        "capsule_id": {
                            "type": "string",
                            "description": "Capsule ID",
                        },
                        "platform": {
                            "type": "string",
                            "description": "Platform: react (default), swift, kotlin",
                        },
                    },
                    "required": ["capsule_id"],
                },
                handler=self.hublab_code,
            ),
            Tool(
                name="hublab_stats",
                description="Get HubLab catalog statistics",
                parameters={
                    "type": "object",
                    "properties": {},
                },
                handler=self.hublab_stats,
            ),
        ]

    def _load_capsules(self) -> list:
        """Load capsules from local metadata file."""
        if self._capsules_cache is not None:
            return self._capsules_cache

        metadata_path = Path(self.HUBLAB_PATH) / self.METADATA_FILE

        if metadata_path.exists():
            try:
                with open(metadata_path) as f:
                    self._capsules_cache = json.load(f)
                return self._capsules_cache
            except Exception:
                pass

        # Fallback to API
        try:
            import urllib.request

            req = urllib.request.Request(
                f"{self.API_BASE}/ai/capsules", headers={"User-Agent": "R-CLI/1.0"}
            )
            with urllib.request.urlopen(req, timeout=10) as response:
                data = json.loads(response.read().decode("utf-8"))
                self._capsules_cache = data.get("capsules", [])
                return self._capsules_cache
        except Exception:
            return []

    def _get_categories(self) -> dict:
        """Get category counts."""
        if self._categories_cache is not None:
            return self._categories_cache

        capsules = self._load_capsules()
        categories = {}

        for cap in capsules:
            cat = cap.get("category", "Other")
            categories[cat] = categories.get(cat, 0) + 1

        self._categories_cache = categories
        return categories

    def _match_score(self, capsule: dict, query: str) -> int:
        """Calculate match score for ranking."""
        query = query.lower()
        score = 0

        if capsule.get("id", "").lower() == query:
            score += 100

        name = capsule.get("name", "").lower()
        if query in name:
            score += 50
        if name.startswith(query):
            score += 30

        tags = [t.lower() for t in capsule.get("tags", [])]
        if query in tags:
            score += 40
        for tag in tags:
            if query in tag:
                score += 10

        desc = capsule.get("description", "").lower()
        if query in desc:
            score += 20

        if query in capsule.get("category", "").lower():
            score += 15

        return score

    def _detect_features(self, description: str) -> dict:
        """Detect app features from description."""
        description_lower = description.lower()
        detected = {}

        for feature, config in self.FEATURE_PATTERNS.items():
            score = 0
            matched_keywords = []

            for keyword in config["keywords"]:
                if keyword in description_lower:
                    score += 10
                    matched_keywords.append(keyword)

            if score > 0:
                detected[feature] = {
                    "score": score,
                    "keywords": matched_keywords,
                    "capsules": config["capsules"],
                    "category": config["category"],
                }

        return detected

    def _find_capsules_for_features(self, features: dict) -> list:
        """Find actual capsules for detected features."""
        capsules = self._load_capsules()
        selected = []
        seen_ids = set()

        for feature, config in features.items():
            # Search for each suggested capsule
            for suggested_id in config["capsules"]:
                # Try exact match
                for cap in capsules:
                    cap_id = cap.get("id", "").lower()
                    if suggested_id.lower() in cap_id or cap_id in suggested_id.lower():
                        if cap["id"] not in seen_ids:
                            selected.append(
                                {
                                    "id": cap["id"],
                                    "name": cap.get("name"),
                                    "category": cap.get("category"),
                                    "feature": feature,
                                    "priority": config["score"],
                                }
                            )
                            seen_ids.add(cap["id"])
                            break

            # Also search by category
            for cap in capsules:
                if cap.get("category", "").lower() == config["category"].lower():
                    if (
                        cap["id"] not in seen_ids
                        and len([s for s in selected if s["feature"] == feature]) < 5
                    ):
                        selected.append(
                            {
                                "id": cap["id"],
                                "name": cap.get("name"),
                                "category": cap.get("category"),
                                "feature": feature,
                                "priority": config["score"] - 5,
                            }
                        )
                        seen_ids.add(cap["id"])

        # Sort by priority
        selected.sort(key=lambda x: x["priority"], reverse=True)
        return selected

    def _generate_project_structure(
        self,
        app_name: str,
        platform: str,
        features: dict,
        capsules: list,
    ) -> dict:
        """Generate project structure."""
        template = self.APP_TEMPLATES.get(platform, self.APP_TEMPLATES["web"])

        # Group capsules by feature
        components_by_feature = {}
        for cap in capsules:
            feature = cap.get("feature", "core")
            if feature not in components_by_feature:
                components_by_feature[feature] = []
            components_by_feature[feature].append(cap)

        # Generate pages based on features
        pages = []
        if "auth" in features:
            pages.extend(
                [
                    {"path": "app/login/page.tsx", "feature": "auth"},
                    {"path": "app/register/page.tsx", "feature": "auth"},
                ]
            )
        if "dashboard" in features:
            pages.append({"path": "app/dashboard/page.tsx", "feature": "dashboard"})
        if "settings" in features:
            pages.append({"path": "app/settings/page.tsx", "feature": "settings"})
        if "ecommerce" in features:
            pages.extend(
                [
                    {"path": "app/products/page.tsx", "feature": "ecommerce"},
                    {"path": "app/cart/page.tsx", "feature": "ecommerce"},
                    {"path": "app/checkout/page.tsx", "feature": "ecommerce"},
                ]
            )
        if "chat" in features:
            pages.append({"path": "app/chat/page.tsx", "feature": "chat"})
        if "social" in features:
            pages.extend(
                [
                    {"path": "app/feed/page.tsx", "feature": "social"},
                    {"path": "app/profile/page.tsx", "feature": "social"},
                ]
            )

        # Generate component files
        component_files = []
        for cap in capsules[:20]:  # Limit for reasonable output
            component_name = "".join(word.title() for word in cap["name"].split())
            component_files.append(
                {
                    "path": f"components/{cap['feature']}/{component_name}.tsx",
                    "capsule": cap["id"],
                    "name": component_name,
                }
            )

        return {
            "app_name": app_name,
            "platform": platform,
            "framework": template["framework"],
            "styling": template["styling"],
            "base_structure": template["structure"],
            "pages": pages,
            "components": component_files,
            "features_detected": list(features.keys()),
            "total_capsules": len(capsules),
        }

    def _generate_component_code(self, capsule: dict, feature: str) -> str:
        """Generate component code for a capsule."""
        name = capsule.get("name", capsule["id"].title())
        component_name = "".join(word.title() for word in name.split())
        capsule_id = capsule["id"]

        return f"""// {name} Component
// Generated by R CLI using HubLab capsule: {capsule_id}
// Feature: {feature}

"use client";

import React from "react";
import {{ cn }} from "@/lib/utils";

interface {component_name}Props {{
  className?: string;
  children?: React.ReactNode;
}}

export function {component_name}({{ className, children }}: {component_name}Props) {{
  return (
    <div className={{cn("{capsule_id}", className)}}>
      {{children}}
    </div>
  );
}}

export default {component_name};
"""

    def _generate_page_code(self, page: dict, components: list) -> str:
        """Generate page code."""
        feature = page["feature"]
        page_name = page["path"].split("/")[-2].title()

        # Get components for this feature
        feature_components = [c for c in components if c.get("feature") == feature]

        imports = []
        component_usage = []

        for comp in feature_components[:5]:
            comp_name = comp["name"]
            imports.append(f'import {{ {comp_name} }} from "@/components/{feature}/{comp_name}";')
            component_usage.append(f"      <{comp_name} />")

        imports_str = "\n".join(imports) if imports else "// Add component imports"
        usage_str = (
            "\n".join(component_usage) if component_usage else "      {/* Add components */}"
        )

        return f"""// {page_name} Page
// Generated by R CLI using HubLab capsules
// Feature: {feature}

"use client";

import React from "react";
{imports_str}

export default function {page_name}Page() {{
  return (
    <main className="container mx-auto p-4">
      <h1 className="text-2xl font-bold mb-4">{page_name}</h1>
      <div className="space-y-4">
{usage_str}
      </div>
    </main>
  );
}}
"""

    def _generate_package_json(self, app_name: str) -> str:
        """Generate package.json."""
        return json.dumps(
            {
                "name": app_name.lower().replace(" ", "-"),
                "version": "0.1.0",
                "private": True,
                "scripts": {
                    "dev": "next dev",
                    "build": "next build",
                    "start": "next start",
                    "lint": "next lint",
                },
                "dependencies": {
                    "next": "14.0.0",
                    "react": "^18.2.0",
                    "react-dom": "^18.2.0",
                    "tailwindcss": "^3.3.0",
                    "clsx": "^2.0.0",
                    "tailwind-merge": "^2.0.0",
                },
                "devDependencies": {
                    "@types/node": "^20",
                    "@types/react": "^18",
                    "@types/react-dom": "^18",
                    "typescript": "^5",
                    "autoprefixer": "^10.0.0",
                    "postcss": "^8.0.0",
                },
            },
            indent=2,
        )

    def hublab_compose(
        self,
        description: str,
        platform: str = "web",
        output_dir: Optional[str] = None,
        app_name: Optional[str] = None,
    ) -> str:
        """Compose a full application from description."""
        # Detect features
        features = self._detect_features(description)

        if not features:
            # Fallback to basic app structure
            features = {
                "forms": {
                    "score": 5,
                    "keywords": ["app"],
                    "capsules": ["button", "input", "card"],
                    "category": "UI",
                },
            }

        # Find capsules for features
        capsules = self._find_capsules_for_features(features)

        # Generate app name if not provided
        if not app_name:
            words = description.split()[:3]
            app_name = "-".join(w.lower() for w in words if len(w) > 2)[:20] or "my-app"

        # Generate project structure
        structure = self._generate_project_structure(app_name, platform, features, capsules)

        # Generate files
        files = {}

        # package.json
        files["package.json"] = self._generate_package_json(app_name)

        # Layout
        files["app/layout.tsx"] = f"""import type {{ Metadata }} from "next";
import "./globals.css";

export const metadata: Metadata = {{
  title: "{app_name}",
  description: "Generated by R CLI with HubLab",
}};

export default function RootLayout({{
  children,
}}: {{
  children: React.ReactNode;
}}) {{
  return (
    <html lang="en">
      <body>{{children}}</body>
    </html>
  );
}}
"""

        # Main page
        files["app/page.tsx"] = f"""// {app_name} - Main Page
// Generated by R CLI using HubLab capsules

export default function Home() {{
  return (
    <main className="min-h-screen p-8">
      <h1 className="text-4xl font-bold mb-8">{app_name}</h1>
      <p className="text-gray-600">
        Features: {", ".join(features.keys())}
      </p>
    </main>
  );
}}
"""

        # Globals CSS
        files["app/globals.css"] = """@tailwind base;
@tailwind components;
@tailwind utilities;
"""

        # Utils
        files["lib/utils.ts"] = """import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}
"""

        # Generate page files
        for page in structure["pages"]:
            feature_caps = [c for c in capsules if c.get("feature") == page["feature"]]
            files[page["path"]] = self._generate_page_code(
                page, [{"name": c["name"], "feature": c["feature"]} for c in feature_caps]
            )

        # Generate component files (top 15)
        for cap in capsules[:15]:
            comp_name = "".join(word.title() for word in cap["name"].split())
            path = f"components/{cap['feature']}/{comp_name}.tsx"
            files[path] = self._generate_component_code(cap, cap["feature"])

        # Write files if output_dir specified
        written_files = []
        if output_dir:
            output_path = Path(output_dir).expanduser()
            output_path.mkdir(parents=True, exist_ok=True)

            for file_path, content in files.items():
                full_path = output_path / file_path
                full_path.parent.mkdir(parents=True, exist_ok=True)
                full_path.write_text(content)
                written_files.append(str(full_path))

        return json.dumps(
            {
                "success": True,
                "app_name": app_name,
                "platform": platform,
                "description": description[:200],
                "features_detected": {
                    name: {
                        "keywords": data["keywords"],
                        "capsule_count": len([c for c in capsules if c.get("feature") == name]),
                    }
                    for name, data in features.items()
                },
                "structure": {
                    "framework": structure["framework"],
                    "styling": structure["styling"],
                    "pages": len(structure["pages"]),
                    "components": len(structure["components"]),
                },
                "capsules_used": [
                    {"id": c["id"], "name": c["name"], "feature": c["feature"]}
                    for c in capsules[:20]
                ],
                "files_generated": list(files.keys()),
                "output_dir": output_dir,
                "files_written": len(written_files) if written_files else 0,
                "next_steps": [
                    f"cd {output_dir}" if output_dir else "Save files to a directory",
                    "npm install",
                    "npm run dev",
                    "Open http://localhost:3000",
                ],
                "generated_at": datetime.now().isoformat(),
            },
            indent=2,
        )

    def hublab_search(
        self,
        query: str,
        category: Optional[str] = None,
        limit: int = 20,
    ) -> str:
        """Search capsules."""
        capsules = self._load_capsules()

        if not capsules:
            return json.dumps(
                {
                    "error": "Could not load capsules. Check HUBLAB_PATH or API.",
                    "hint": f"Set HUBLAB_PATH env var (current: {self.HUBLAB_PATH})",
                },
                indent=2,
            )

        if category:
            capsules = [c for c in capsules if c.get("category", "").lower() == category.lower()]

        scored = []
        for cap in capsules:
            score = self._match_score(cap, query)
            if score > 0:
                scored.append((score, cap))

        scored.sort(key=lambda x: x[0], reverse=True)

        results = []
        for score, cap in scored[:limit]:
            results.append(
                {
                    "id": cap.get("id"),
                    "name": cap.get("name"),
                    "category": cap.get("category"),
                    "description": cap.get("description", "")[:150],
                    "tags": cap.get("tags", [])[:5],
                    "score": score,
                }
            )

        return json.dumps(
            {
                "query": query,
                "category_filter": category,
                "count": len(results),
                "total_searched": len(capsules),
                "results": results,
            },
            indent=2,
        )

    def hublab_capsule(self, capsule_id: str) -> str:
        """Get capsule details."""
        capsules = self._load_capsules()

        for cap in capsules:
            if cap.get("id", "").lower() == capsule_id.lower():
                return json.dumps(
                    {
                        "found": True,
                        "capsule": {
                            "id": cap.get("id"),
                            "name": cap.get("name"),
                            "category": cap.get("category"),
                            "description": cap.get("description"),
                            "tags": cap.get("tags", []),
                            "platform": cap.get("platform", "react"),
                        },
                        "usage": f"Import and use <{cap.get('name', capsule_id)} /> in your React app",
                        "docs_url": f"https://hublab.dev/capsules/{capsule_id}",
                    },
                    indent=2,
                )

        matches = []
        for cap in capsules:
            if capsule_id.lower() in cap.get("id", "").lower():
                matches.append(cap.get("id"))

        return json.dumps(
            {
                "found": False,
                "capsule_id": capsule_id,
                "similar": matches[:10] if matches else [],
                "hint": "Use hublab_search to find capsules",
            },
            indent=2,
        )

    def hublab_categories(self) -> str:
        """List all categories."""
        categories = self._get_categories()
        sorted_cats = sorted(categories.items(), key=lambda x: x[1], reverse=True)

        return json.dumps(
            {
                "total_categories": len(categories),
                "total_capsules": sum(categories.values()),
                "categories": [{"name": name, "count": count} for name, count in sorted_cats],
            },
            indent=2,
        )

    def hublab_browse(
        self,
        category: str,
        limit: int = 30,
    ) -> str:
        """Browse capsules by category."""
        capsules = self._load_capsules()

        results = []
        for cap in capsules:
            if cap.get("category", "").lower() == category.lower():
                results.append(
                    {
                        "id": cap.get("id"),
                        "name": cap.get("name"),
                        "description": cap.get("description", "")[:100],
                        "tags": cap.get("tags", [])[:3],
                    }
                )

                if len(results) >= limit:
                    break

        if not results:
            categories = self._get_categories()
            matches = [c for c in categories if category.lower() in c.lower()]

            return json.dumps(
                {
                    "category": category,
                    "count": 0,
                    "hint": f"Category not found. Similar: {matches[:5]}",
                    "all_categories_url": "Use hublab_categories to see all",
                },
                indent=2,
            )

        return json.dumps(
            {
                "category": category,
                "count": len(results),
                "capsules": results,
            },
            indent=2,
        )

    def hublab_suggest(
        self,
        description: str,
        limit: int = 15,
    ) -> str:
        """Suggest capsules for an app description."""
        capsules = self._load_capsules()

        words = description.lower().replace(",", " ").replace(".", " ").split()
        keywords = [w for w in words if len(w) > 2]

        term_map = {
            "login": ["auth", "login", "form", "input"],
            "signup": ["auth", "register", "form"],
            "dashboard": ["dashboard", "chart", "card", "stats"],
            "cart": ["cart", "ecommerce", "shopping"],
            "chat": ["chat", "message", "realtime"],
            "profile": ["profile", "avatar", "user"],
            "settings": ["settings", "form", "toggle"],
            "table": ["table", "data", "grid"],
            "list": ["list", "item", "collection"],
            "search": ["search", "filter", "input"],
            "payment": ["payment", "stripe", "checkout"],
            "upload": ["upload", "file", "media"],
            "notification": ["notification", "alert", "toast"],
            "modal": ["modal", "dialog", "popup"],
            "navigation": ["nav", "menu", "sidebar"],
            "form": ["form", "input", "validation"],
            "button": ["button", "cta", "action"],
        }

        expanded = set(keywords)
        for word in keywords:
            if word in term_map:
                expanded.update(term_map[word])

        scored = []
        for cap in capsules:
            score = 0
            cap_text = f"{cap.get('id', '')} {cap.get('name', '')} {cap.get('description', '')} {' '.join(cap.get('tags', []))}".lower()

            for kw in expanded:
                if kw in cap_text:
                    score += 10
                    if kw in cap.get("tags", []):
                        score += 5

            if score > 0:
                scored.append((score, cap))

        scored.sort(key=lambda x: x[0], reverse=True)

        suggestions = []
        seen_categories = {}

        for score, cap in scored:
            cat = cap.get("category", "Other")
            if seen_categories.get(cat, 0) >= 3:
                continue

            seen_categories[cat] = seen_categories.get(cat, 0) + 1
            suggestions.append(
                {
                    "id": cap.get("id"),
                    "name": cap.get("name"),
                    "category": cat,
                    "reason": f"Matches: {', '.join([k for k in expanded if k in cap.get('id', '').lower() or k in ' '.join(cap.get('tags', [])).lower()][:3])}",
                }
            )

            if len(suggestions) >= limit:
                break

        return json.dumps(
            {
                "description": description[:100],
                "keywords_detected": list(expanded)[:15],
                "suggestion_count": len(suggestions),
                "suggestions": suggestions,
                "next_step": "Use hublab_compose to generate a full application",
            },
            indent=2,
        )

    def hublab_code(
        self,
        capsule_id: str,
        platform: str = "react",
    ) -> str:
        """Get code for a capsule."""
        capsules = self._load_capsules()

        capsule = None
        for cap in capsules:
            if cap.get("id", "").lower() == capsule_id.lower():
                capsule = cap
                break

        if not capsule:
            return json.dumps(
                {
                    "error": f"Capsule not found: {capsule_id}",
                    "hint": "Use hublab_search to find valid capsule IDs",
                },
                indent=2,
            )

        name = capsule.get("name", capsule_id.title())
        component_name = "".join(word.title() for word in name.split())

        if platform == "react":
            example_code = f"""// {name} Component
// From HubLab: https://hublab.dev/capsules/{capsule_id}

"use client";

import React from "react";
import {{ cn }} from "@/lib/utils";

interface {component_name}Props {{
  className?: string;
  children?: React.ReactNode;
}}

export function {component_name}({{ className, children }}: {component_name}Props) {{
  return (
    <div className={{cn("{capsule_id}", className)}}>
      {{children}}
    </div>
  );
}}

export default {component_name};
"""
        elif platform == "swift":
            example_code = f"""// {name} Component (SwiftUI)
// From HubLab: https://hublab.dev/capsules/{capsule_id}

import SwiftUI

struct {component_name}: View {{
    var body: some View {{
        VStack {{
            Text("{name}")
        }}
    }}
}}

#Preview {{
    {component_name}()
}}
"""
        elif platform == "kotlin":
            example_code = f"""// {name} Component (Jetpack Compose)
// From HubLab: https://hublab.dev/capsules/{capsule_id}

import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.foundation.layout.Column
import androidx.compose.material3.Text

@Composable
fun {component_name}(
    modifier: Modifier = Modifier
) {{
    Column(modifier = modifier) {{
        Text("{name}")
    }}
}}
"""
        else:
            example_code = f"// Platform '{platform}' not supported. Use: react, swift, kotlin"

        return json.dumps(
            {
                "capsule_id": capsule_id,
                "name": name,
                "platform": platform,
                "code": example_code,
                "docs_url": f"https://hublab.dev/capsules/{capsule_id}",
            },
            indent=2,
        )

    def hublab_stats(self) -> str:
        """Get catalog statistics."""
        capsules = self._load_capsules()
        categories = self._get_categories()

        platforms = {}
        for cap in capsules:
            plat = cap.get("platform", "react")
            platforms[plat] = platforms.get(plat, 0) + 1

        all_tags = {}
        for cap in capsules:
            for tag in cap.get("tags", []):
                all_tags[tag] = all_tags.get(tag, 0) + 1

        top_tags = sorted(all_tags.items(), key=lambda x: x[1], reverse=True)[:20]

        return json.dumps(
            {
                "total_capsules": len(capsules),
                "total_categories": len(categories),
                "top_categories": sorted(categories.items(), key=lambda x: x[1], reverse=True)[:10],
                "platforms": platforms,
                "top_tags": top_tags,
                "compose_available": True,
                "source": "hublab.dev",
            },
            indent=2,
        )

    def execute(self, **kwargs) -> str:
        """Direct skill execution."""
        if "description" in kwargs and len(kwargs.get("description", "")) > 30:
            return self.hublab_compose(kwargs["description"])
        if "query" in kwargs:
            return self.hublab_search(kwargs["query"])
        return self.hublab_stats()
