"""
Design Skill for R CLI.

Generate images with Stable Diffusion locally.
Supports multiple backends: ComfyUI, Automatic1111, diffusers.

Requirements:
- diffusers (basic) or
- ComfyUI / Automatic1111 API (advanced)
- 8GB+ VRAM for SD 1.5
- 12GB+ VRAM for SDXL
"""

import base64
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

import requests

from r_cli.core.agent import Skill
from r_cli.core.llm import Tool

logger = logging.getLogger(__name__)


class DesignSkill(Skill):
    """Skill for image generation with Stable Diffusion."""

    name = "design"
    description = "Generate images with Stable Diffusion locally"

    # Popular models
    MODELS = {
        "sd-1.5": {
            "name": "Stable Diffusion 1.5",
            "repo": "runwayml/stable-diffusion-v1-5",
            "vram": "8GB",
        },
        "sd-2.1": {
            "name": "Stable Diffusion 2.1",
            "repo": "stabilityai/stable-diffusion-2-1",
            "vram": "8GB",
        },
        "sdxl": {
            "name": "Stable Diffusion XL",
            "repo": "stabilityai/stable-diffusion-xl-base-1.0",
            "vram": "12GB",
        },
        "sdxl-turbo": {
            "name": "SDXL Turbo (4 steps)",
            "repo": "stabilityai/sdxl-turbo",
            "vram": "12GB",
        },
    }

    # Predefined styles
    STYLES = {
        "photorealistic": "photorealistic, highly detailed, 8k uhd, professional photography",
        "anime": "anime style, studio ghibli, vibrant colors, detailed",
        "oil-painting": "oil painting, classical art, canvas texture, masterpiece",
        "watercolor": "watercolor painting, soft colors, artistic, flowing",
        "digital-art": "digital art, concept art, trending on artstation, highly detailed",
        "cyberpunk": "cyberpunk, neon lights, futuristic, sci-fi, blade runner style",
        "fantasy": "fantasy art, magical, ethereal, detailed illustration",
        "minimalist": "minimalist design, simple, clean lines, modern",
        "3d-render": "3d render, octane render, cinema 4d, highly detailed",
        "pixel-art": "pixel art, 16-bit, retro game style, detailed sprites",
    }

    # Common sizes
    SIZES = {
        "square": (512, 512),
        "square-hd": (1024, 1024),
        "portrait": (512, 768),
        "portrait-hd": (768, 1152),
        "landscape": (768, 512),
        "landscape-hd": (1152, 768),
        "wide": (896, 512),
        "ultrawide": (1024, 512),
    }

    # Supported backends
    BACKENDS = ["diffusers", "comfyui", "automatic1111"]

    # Memory thresholds (in GB)
    MIN_VRAM_REQUIRED = 4.0  # Minimum VRAM for SD 1.5
    RECOMMENDED_VRAM = 8.0  # Recommended for comfortable generation

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._diffusers_available = self._check_diffusers()
        self._comfyui_available = self._check_comfyui()
        self._a1111_available = self._check_a1111()
        self._active_backend = self._detect_backend()

        # Cached pipeline for diffusers (lazy loaded)
        self._pipeline = None
        self._pipeline_device = None

    def _get_gpu_memory_info(self) -> dict:
        """Gets GPU memory information if available."""
        info = {
            "device": "cpu",
            "total_vram_gb": 0.0,
            "free_vram_gb": 0.0,
            "used_vram_gb": 0.0,
        }

        try:
            import torch

            if torch.cuda.is_available():
                info["device"] = "cuda"
                props = torch.cuda.get_device_properties(0)
                info["total_vram_gb"] = props.total_memory / (1024**3)
                info["free_vram_gb"] = (props.total_memory - torch.cuda.memory_allocated(0)) / (
                    1024**3
                )
                info["used_vram_gb"] = torch.cuda.memory_allocated(0) / (1024**3)
            elif hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
                info["device"] = "mps"
                # MPS doesn't have detailed memory reporting
                info["total_vram_gb"] = -1  # Unknown
        except ImportError:
            logger.debug("torch not available for GPU memory check")
        except Exception as e:
            logger.debug(f"Failed to get GPU memory info: {e}")

        return info

    def _check_vram_available(self, required_gb: Optional[float] = None) -> tuple[bool, str]:
        """Checks if enough VRAM is available for generation."""
        if required_gb is None:
            required_gb = self.MIN_VRAM_REQUIRED

        info = self._get_gpu_memory_info()

        if info["device"] == "cpu":
            return True, "Using CPU (no GPU detected, generation will be slow)"

        if info["device"] == "mps":
            return True, "Using Apple Silicon GPU (MPS)"

        if info["free_vram_gb"] < required_gb:
            return False, (
                f"Insufficient VRAM: {info['free_vram_gb']:.1f}GB free, "
                f"{required_gb:.1f}GB required. "
                f"Try running unload_model() to free memory."
            )

        return True, f"CUDA GPU with {info['free_vram_gb']:.1f}GB free VRAM"

    def _cleanup_gpu_memory(self):
        """Cleans up GPU memory after generation."""
        try:
            import gc

            import torch

            if torch.cuda.is_available():
                torch.cuda.empty_cache()
                torch.cuda.synchronize()
            gc.collect()
            logger.debug("GPU memory cleaned up")
        except ImportError:
            pass
        except Exception as e:
            logger.debug(f"Failed to cleanup GPU memory: {e}")

    def unload_model(self) -> str:
        """Unloads the cached diffusers model to free GPU memory."""
        if self._pipeline is None:
            return "No model is currently loaded."

        try:
            import gc

            import torch

            # Delete the pipeline
            del self._pipeline
            self._pipeline = None
            self._pipeline_device = None

            # Clear GPU cache
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
                torch.cuda.synchronize()
            gc.collect()

            info = self._get_gpu_memory_info()
            return f"Model unloaded. Free VRAM: {info['free_vram_gb']:.1f}GB"
        except Exception as e:
            logger.warning(f"Failed to unload model: {e}")
            return f"Error unloading model: {e}"

    def get_vram_status(self) -> str:
        """Returns current GPU/VRAM status."""
        info = self._get_gpu_memory_info()

        if info["device"] == "cpu":
            return "No GPU detected. Using CPU for generation (slow)."

        if info["device"] == "mps":
            return "Apple Silicon GPU (MPS) detected. Memory management is automatic."

        model_status = "loaded" if self._pipeline is not None else "not loaded"
        return (
            f"GPU: CUDA\n"
            f"Total VRAM: {info['total_vram_gb']:.1f}GB\n"
            f"Used VRAM: {info['used_vram_gb']:.1f}GB\n"
            f"Free VRAM: {info['free_vram_gb']:.1f}GB\n"
            f"Model: {model_status}"
        )

    def _check_diffusers(self) -> bool:
        """Check if diffusers is available."""
        try:
            import diffusers
            import torch

            return True
        except ImportError:
            return False

    def _check_comfyui(self) -> bool:
        """Check if ComfyUI API is available."""
        try:
            response = requests.get("http://127.0.0.1:8188/history", timeout=2)
            return response.status_code == 200
        except Exception as e:
            logger.debug(f"ComfyUI not available: {e}")
            return False

    def _check_a1111(self) -> bool:
        """Check if Automatic1111 API is available."""
        try:
            response = requests.get("http://127.0.0.1:7860/sdapi/v1/sd-models", timeout=2)
            return response.status_code == 200
        except Exception as e:
            logger.debug(f"Automatic1111 not available: {e}")
            return False

    def _detect_backend(self) -> str:
        """Detect the best available backend."""
        if self._a1111_available:
            return "automatic1111"
        elif self._comfyui_available:
            return "comfyui"
        elif self._diffusers_available:
            return "diffusers"
        return "none"

    def get_tools(self) -> list[Tool]:
        return [
            Tool(
                name="generate_image",
                description="Generate an image from a prompt using Stable Diffusion",
                parameters={
                    "type": "object",
                    "properties": {
                        "prompt": {
                            "type": "string",
                            "description": "Description of the image to generate",
                        },
                        "negative_prompt": {
                            "type": "string",
                            "description": "What you DON'T want in the image",
                        },
                        "style": {
                            "type": "string",
                            "enum": list(self.STYLES.keys()),
                            "description": "Predefined style to apply",
                        },
                        "size": {
                            "type": "string",
                            "enum": list(self.SIZES.keys()),
                            "description": "Image size (default: square)",
                        },
                        "steps": {
                            "type": "integer",
                            "description": "Inference steps (default: 30)",
                        },
                        "cfg_scale": {
                            "type": "number",
                            "description": "Guidance scale (default: 7.5)",
                        },
                        "seed": {
                            "type": "integer",
                            "description": "Seed for reproducibility (-1 = random)",
                        },
                        "output_path": {
                            "type": "string",
                            "description": "Path where to save the image",
                        },
                    },
                    "required": ["prompt"],
                },
                handler=self.generate_image,
            ),
            Tool(
                name="img2img",
                description="Generate variations of an existing image",
                parameters={
                    "type": "object",
                    "properties": {
                        "image_path": {
                            "type": "string",
                            "description": "Path to the base image",
                        },
                        "prompt": {
                            "type": "string",
                            "description": "Description of modifications",
                        },
                        "strength": {
                            "type": "number",
                            "description": "Transformation strength (0.0-1.0, default: 0.75)",
                        },
                        "output_path": {
                            "type": "string",
                            "description": "Path where to save the image",
                        },
                    },
                    "required": ["image_path", "prompt"],
                },
                handler=self.img2img,
            ),
            Tool(
                name="upscale_image",
                description="Increase the resolution of an image",
                parameters={
                    "type": "object",
                    "properties": {
                        "image_path": {
                            "type": "string",
                            "description": "Path to the image to upscale",
                        },
                        "scale": {
                            "type": "number",
                            "description": "Scale factor (2, 4, default: 2)",
                        },
                        "output_path": {
                            "type": "string",
                            "description": "Path where to save the image",
                        },
                    },
                    "required": ["image_path"],
                },
                handler=self.upscale_image,
            ),
            Tool(
                name="list_styles",
                description="List available predefined styles",
                parameters={"type": "object", "properties": {}},
                handler=self.list_styles,
            ),
            Tool(
                name="list_models",
                description="List available Stable Diffusion models",
                parameters={"type": "object", "properties": {}},
                handler=self.list_models,
            ),
            Tool(
                name="backend_status",
                description="Show generation backend status",
                parameters={"type": "object", "properties": {}},
                handler=self.backend_status,
            ),
            Tool(
                name="vram_status",
                description="Show current GPU/VRAM memory status",
                parameters={"type": "object", "properties": {}},
                handler=self.get_vram_status,
            ),
            Tool(
                name="unload_design_model",
                description="Unload model from GPU memory to free VRAM",
                parameters={"type": "object", "properties": {}},
                handler=self.unload_model,
            ),
        ]

    def generate_image(
        self,
        prompt: str,
        negative_prompt: str = "",
        style: Optional[str] = None,
        size: str = "square",
        steps: int = 30,
        cfg_scale: float = 7.5,
        seed: int = -1,
        output_path: Optional[str] = None,
    ) -> str:
        """Generate an image with Stable Diffusion."""
        # Apply style if specified
        if style and style in self.STYLES:
            prompt = f"{prompt}, {self.STYLES[style]}"

        # Get dimensions
        width, height = self.SIZES.get(size, (512, 512))

        # Default negative prompt
        if not negative_prompt:
            negative_prompt = "blurry, bad quality, distorted, ugly, deformed"

        # Determine output path
        if output_path:
            out_path = Path(output_path)
        else:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            out_path = Path(self.output_dir) / f"image_{timestamp}.png"

        out_path.parent.mkdir(parents=True, exist_ok=True)

        # Generate according to available backend
        if self._active_backend == "automatic1111":
            return self._generate_a1111(
                prompt, negative_prompt, width, height, steps, cfg_scale, seed, out_path
            )
        elif self._active_backend == "comfyui":
            return self._generate_comfyui(
                prompt, negative_prompt, width, height, steps, cfg_scale, seed, out_path
            )
        elif self._active_backend == "diffusers":
            return self._generate_diffusers(
                prompt, negative_prompt, width, height, steps, cfg_scale, seed, out_path
            )
        else:
            return "Error: No generation backend available.\n\nOptions:\n1. Install diffusers: pip install diffusers torch\n2. Run Automatic1111 on localhost:7860\n3. Run ComfyUI on localhost:8188"

    def _generate_diffusers(
        self,
        prompt: str,
        negative_prompt: str,
        width: int,
        height: int,
        steps: int,
        cfg_scale: float,
        seed: int,
        out_path: Path,
    ) -> str:
        """Genera imagen usando diffusers with GPU memory management."""
        try:
            import torch
            from diffusers import DPMSolverMultistepScheduler, StableDiffusionPipeline

            # Check VRAM availability
            vram_ok, vram_msg = self._check_vram_available()
            if not vram_ok:
                return f"Error: {vram_msg}"

            logger.info(f"Generation starting: {vram_msg}")

            # Determine device
            if torch.cuda.is_available():
                device = "cuda"
            elif torch.backends.mps.is_available():
                device = "mps"
            else:
                device = "cpu"

            # Use cached pipeline or load new one
            if self._pipeline is None or self._pipeline_device != device:
                logger.info("Loading Stable Diffusion model...")
                model_id = "runwayml/stable-diffusion-v1-5"
                self._pipeline = StableDiffusionPipeline.from_pretrained(
                    model_id,
                    torch_dtype=torch.float16 if device == "cuda" else torch.float32,
                )
                self._pipeline = self._pipeline.to(device)
                self._pipeline_device = device

                # Use faster scheduler
                self._pipeline.scheduler = DPMSolverMultistepScheduler.from_config(
                    self._pipeline.scheduler.config
                )
                logger.info(f"Model loaded on {device}")

            # Configure seed
            generator = None
            if seed != -1:
                generator = torch.Generator(device).manual_seed(seed)

            # Generate
            logger.info(f"Generating image: {width}x{height}, {steps} steps")
            image = self._pipeline(
                prompt=prompt,
                negative_prompt=negative_prompt,
                width=width,
                height=height,
                num_inference_steps=steps,
                guidance_scale=cfg_scale,
                generator=generator,
            ).images[0]

            # Save
            image.save(str(out_path))

            # Cleanup intermediate GPU memory (but keep model loaded)
            self._cleanup_gpu_memory()

            return f"Image generated: {out_path}\nPrompt: {prompt}\nSize: {width}x{height}"

        except Exception as e:
            # On error, cleanup and report
            self._cleanup_gpu_memory()
            logger.error(f"Error generating image: {e}")
            return f"Error generating image with diffusers: {e}"

    def _generate_a1111(
        self,
        prompt: str,
        negative_prompt: str,
        width: int,
        height: int,
        steps: int,
        cfg_scale: float,
        seed: int,
        out_path: Path,
    ) -> str:
        """Genera imagen usando Automatic1111 API."""
        try:
            payload = {
                "prompt": prompt,
                "negative_prompt": negative_prompt,
                "width": width,
                "height": height,
                "steps": steps,
                "cfg_scale": cfg_scale,
                "seed": seed,
                "sampler_name": "DPM++ 2M Karras",
            }

            response = requests.post(
                "http://127.0.0.1:7860/sdapi/v1/txt2img",
                json=payload,
                timeout=300,
            )

            if response.status_code != 200:
                return f"Error A1111 API: {response.status_code}"

            result = response.json()
            image_data = base64.b64decode(result["images"][0])

            with open(out_path, "wb") as f:
                f.write(image_data)

            info = json.loads(result.get("info", "{}"))
            actual_seed = info.get("seed", seed)

            return f"Image generated: {out_path}\nPrompt: {prompt}\nSize: {width}x{height}\nSeed: {actual_seed}"

        except Exception as e:
            return f"Error generating image with A1111: {e}"

    def _generate_comfyui(
        self,
        prompt: str,
        negative_prompt: str,
        width: int,
        height: int,
        steps: int,
        cfg_scale: float,
        seed: int,
        out_path: Path,
    ) -> str:
        """Generate image using ComfyUI API."""
        try:
            # Basic workflow for ComfyUI
            workflow = {
                "3": {
                    "class_type": "KSampler",
                    "inputs": {
                        "seed": seed if seed != -1 else 0,
                        "steps": steps,
                        "cfg": cfg_scale,
                        "sampler_name": "dpmpp_2m",
                        "scheduler": "karras",
                        "denoise": 1,
                        "model": ["4", 0],
                        "positive": ["6", 0],
                        "negative": ["7", 0],
                        "latent_image": ["5", 0],
                    },
                },
                "4": {
                    "class_type": "CheckpointLoaderSimple",
                    "inputs": {"ckpt_name": "sd_v1.5.safetensors"},
                },
                "5": {
                    "class_type": "EmptyLatentImage",
                    "inputs": {"width": width, "height": height, "batch_size": 1},
                },
                "6": {
                    "class_type": "CLIPTextEncode",
                    "inputs": {"text": prompt, "clip": ["4", 1]},
                },
                "7": {
                    "class_type": "CLIPTextEncode",
                    "inputs": {"text": negative_prompt, "clip": ["4", 1]},
                },
                "8": {
                    "class_type": "VAEDecode",
                    "inputs": {"samples": ["3", 0], "vae": ["4", 2]},
                },
                "9": {
                    "class_type": "SaveImage",
                    "inputs": {"filename_prefix": "r_cli", "images": ["8", 0]},
                },
            }

            # Send workflow
            response = requests.post(
                "http://127.0.0.1:8188/prompt",
                json={"prompt": workflow},
                timeout=300,
            )

            if response.status_code != 200:
                return f"Error ComfyUI API: {response.status_code}"

            # ComfyUI saves to its output directory
            # For simplicity, we inform where to look
            return f"Image generating in ComfyUI...\nPrompt: {prompt}\nLook for: ComfyUI/output/r_cli_*.png"

        except Exception as e:
            return f"Error generating image with ComfyUI: {e}"

    def img2img(
        self,
        image_path: str,
        prompt: str,
        strength: float = 0.75,
        output_path: Optional[str] = None,
    ) -> str:
        """Generate variations of an existing image."""
        input_path = Path(image_path)
        if not input_path.exists():
            return f"Error: Image not found: {image_path}"

        # Determine output path
        if output_path:
            out_path = Path(output_path)
        else:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            out_path = Path(self.output_dir) / f"img2img_{timestamp}.png"

        out_path.parent.mkdir(parents=True, exist_ok=True)

        if self._active_backend == "automatic1111":
            return self._img2img_a1111(input_path, prompt, strength, out_path)
        elif self._active_backend == "diffusers":
            return self._img2img_diffusers(input_path, prompt, strength, out_path)
        else:
            return "Error: img2img requires Automatic1111 or diffusers"

    def _img2img_diffusers(
        self,
        input_path: Path,
        prompt: str,
        strength: float,
        out_path: Path,
    ) -> str:
        """img2img using diffusers."""
        try:
            import torch
            from diffusers import StableDiffusionImg2ImgPipeline
            from PIL import Image

            # Determine device
            if torch.cuda.is_available():
                device = "cuda"
            elif torch.backends.mps.is_available():
                device = "mps"
            else:
                device = "cpu"

            # Load model
            model_id = "runwayml/stable-diffusion-v1-5"
            pipe = StableDiffusionImg2ImgPipeline.from_pretrained(
                model_id,
                torch_dtype=torch.float16 if device == "cuda" else torch.float32,
            )
            pipe = pipe.to(device)

            # Load image
            init_image = Image.open(input_path).convert("RGB")
            init_image = init_image.resize((512, 512))

            # Generate
            image = pipe(
                prompt=prompt,
                image=init_image,
                strength=strength,
                guidance_scale=7.5,
            ).images[0]

            # Save
            image.save(str(out_path))

            return f"Image generated: {out_path}\nBase: {input_path}\nStrength: {strength}"

        except Exception as e:
            return f"Error in img2img: {e}"

    def _img2img_a1111(
        self,
        input_path: Path,
        prompt: str,
        strength: float,
        out_path: Path,
    ) -> str:
        """img2img using Automatic1111 API."""
        try:
            # Read image and convert to base64
            with open(input_path, "rb") as f:
                image_b64 = base64.b64encode(f.read()).decode()

            payload = {
                "init_images": [image_b64],
                "prompt": prompt,
                "denoising_strength": strength,
                "steps": 30,
                "cfg_scale": 7.5,
            }

            response = requests.post(
                "http://127.0.0.1:7860/sdapi/v1/img2img",
                json=payload,
                timeout=300,
            )

            if response.status_code != 200:
                return f"Error A1111 API: {response.status_code}"

            result = response.json()
            image_data = base64.b64decode(result["images"][0])

            with open(out_path, "wb") as f:
                f.write(image_data)

            return f"Image generated: {out_path}\nBase: {input_path}\nStrength: {strength}"

        except Exception as e:
            return f"Error in img2img: {e}"

    def upscale_image(
        self,
        image_path: str,
        scale: float = 2,
        output_path: Optional[str] = None,
    ) -> str:
        """Increase the resolution of an image."""
        input_path = Path(image_path)
        if not input_path.exists():
            return f"Error: Image not found: {image_path}"

        # Determine output path
        if output_path:
            out_path = Path(output_path)
        else:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            out_path = Path(self.output_dir) / f"upscaled_{timestamp}.png"

        out_path.parent.mkdir(parents=True, exist_ok=True)

        # Use A1111 if available (has better upscalers)
        if self._active_backend == "automatic1111":
            return self._upscale_a1111(input_path, scale, out_path)
        else:
            # Fallback: simple upscale with PIL
            return self._upscale_pil(input_path, scale, out_path)

    def _upscale_pil(
        self,
        input_path: Path,
        scale: float,
        out_path: Path,
    ) -> str:
        """Basic upscale with PIL."""
        try:
            from PIL import Image

            img = Image.open(input_path)
            new_size = (int(img.width * scale), int(img.height * scale))
            upscaled = img.resize(new_size, Image.Resampling.LANCZOS)
            upscaled.save(str(out_path))

            return f"Image upscaled: {out_path}\nOriginal: {img.width}x{img.height}\nNew: {new_size[0]}x{new_size[1]}"

        except Exception as e:
            return f"Error upscaling image: {e}"

    def _upscale_a1111(
        self,
        input_path: Path,
        scale: float,
        out_path: Path,
    ) -> str:
        """Upscale using Automatic1111 API."""
        try:
            with open(input_path, "rb") as f:
                image_b64 = base64.b64encode(f.read()).decode()

            payload = {
                "image": image_b64,
                "upscaler_1": "R-ESRGAN 4x+",
                "upscaling_resize": scale,
            }

            response = requests.post(
                "http://127.0.0.1:7860/sdapi/v1/extra-single-image",
                json=payload,
                timeout=300,
            )

            if response.status_code != 200:
                return self._upscale_pil(input_path, scale, out_path)

            result = response.json()
            image_data = base64.b64decode(result["image"])

            with open(out_path, "wb") as f:
                f.write(image_data)

            return f"Image upscaled (R-ESRGAN): {out_path}\nFactor: {scale}x"

        except Exception:
            return self._upscale_pil(input_path, scale, out_path)

    def list_styles(self) -> str:
        """List predefined styles."""
        result = ["Available styles:\n"]

        for style, desc in self.STYLES.items():
            result.append(f"  - {style}: {desc[:50]}...")

        result.append("\nAvailable sizes:")
        for size, (w, h) in self.SIZES.items():
            result.append(f"  - {size}: {w}x{h}")

        result.append("\nUsage: generate_image(prompt, style='cyberpunk', size='landscape')")

        return "\n".join(result)

    def list_models(self) -> str:
        """List Stable Diffusion models."""
        result = ["Stable Diffusion Models:\n"]

        for model_id, info in self.MODELS.items():
            result.append(f"  - {model_id}: {info['name']} ({info['vram']} VRAM)")

        result.append("\nSupported backends:")
        result.append("  - diffusers: pip install diffusers torch")
        result.append("  - automatic1111: Run on localhost:7860")
        result.append("  - comfyui: Run on localhost:8188")

        return "\n".join(result)

    def backend_status(self) -> str:
        """Show backend status."""
        result = ["Generation backends status:\n"]

        # Update status
        self._diffusers_available = self._check_diffusers()
        self._comfyui_available = self._check_comfyui()
        self._a1111_available = self._check_a1111()
        self._active_backend = self._detect_backend()

        status = {
            "diffusers": self._diffusers_available,
            "automatic1111": self._a1111_available,
            "comfyui": self._comfyui_available,
        }

        for backend, available in status.items():
            icon = "OK" if available else "NO"
            active = " (active)" if backend == self._active_backend else ""
            result.append(f"  - {backend}: {icon}{active}")

        if self._active_backend == "none":
            result.append("\nNo backend available. Options:")
            result.append("  1. pip install diffusers torch")
            result.append("  2. Run Automatic1111 WebUI")
            result.append("  3. Run ComfyUI")

        return "\n".join(result)

    def execute(self, **kwargs) -> str:
        """Direct skill execution."""
        prompt = kwargs.get("prompt")
        image_path = kwargs.get("image")
        upscale = kwargs.get("upscale")

        if prompt and image_path:
            # img2img
            return self.img2img(
                image_path=image_path,
                prompt=prompt,
                strength=kwargs.get("strength", 0.75),
                output_path=kwargs.get("output"),
            )
        elif prompt:
            # txt2img
            return self.generate_image(
                prompt=prompt,
                negative_prompt=kwargs.get("negative", ""),
                style=kwargs.get("style"),
                size=kwargs.get("size", "square"),
                steps=kwargs.get("steps", 30),
                cfg_scale=kwargs.get("cfg", 7.5),
                seed=kwargs.get("seed", -1),
                output_path=kwargs.get("output"),
            )
        elif upscale:
            return self.upscale_image(
                image_path=upscale,
                scale=kwargs.get("scale", 2),
                output_path=kwargs.get("output"),
            )
        else:
            return "Error: Specify --prompt to generate, --image --prompt for img2img, or --upscale to upscale"
