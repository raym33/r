# R CLI 🚀

**Tu AI Operating System local** - 100% privado, 100% offline, 100% tuyo.

R CLI es un agente AI en terminal potenciado por LLMs open source locales (LM Studio, Ollama). Inspirado en el CEO CLI viral de Paul Klein, pero diseñado para funcionar **completamente offline**.

```
╔═══════════════════════════════════════════════════════════════╗
║     ██████╗        ██████╗██╗     ██╗                        ║
║     ██╔══██╗      ██╔════╝██║     ██║                        ║
║     ██████╔╝█████╗██║     ██║     ██║                        ║
║     ██╔══██╗╚════╝██║     ██║     ██║                        ║
║     ██║  ██║      ╚██████╗███████╗██║                        ║
║     ╚═╝  ╚═╝       ╚═════╝╚══════╝╚═╝                        ║
╚═══════════════════════════════════════════════════════════════╝
```

## ✨ Características

- 🔒 **100% Local** - Tus datos nunca salen de tu máquina
- 🚀 **Skills modulares** - PDF, SQL, código, resúmenes y más
- 🎮 **UI épica** - Animaciones estilo PS2/Matrix en terminal
- 🧠 **RAG integrado** - Base de conocimiento persistente
- 🔌 **Extensible** - Crea tus propios skills fácilmente
- 💰 **Gratis** - Sin APIs de pago ni suscripciones

## 🛠️ Requisitos

- Python 3.10+
- [LM Studio](https://lmstudio.ai/) o [Ollama](https://ollama.ai/)
- 16GB+ RAM (24GB VRAM recomendado para modelos grandes)

### Modelos recomendados

| Modelo | VRAM | Uso |
|--------|------|-----|
| Qwen2.5-7B | 8GB | Rápido, tareas simples |
| Qwen2.5-32B | 20GB | Equilibrado |
| Qwen2.5-72B (Q4) | 24GB | Máxima calidad |
| DeepSeek-Coder | 16GB | Especializado en código |

## 📦 Instalación

```bash
# Clonar el repositorio
git clone https://github.com/tuusuario/r-cli.git
cd r-cli

# Instalar con pip
pip install -e .

# O con uv (más rápido)
uv pip install -e .
```

## 🚀 Uso rápido

### 1. Inicia tu servidor LLM

**LM Studio:**
1. Abre LM Studio
2. Carga un modelo (ej: Qwen2.5-32B-Instruct)
3. Inicia el servidor local (puerto 1234)

**Ollama:**
```bash
ollama run qwen2.5:32b
```

### 2. Lanza R CLI

```bash
# Modo interactivo
r

# Chat directo
r chat "Explica qué es machine learning"

# Skills directos
r pdf "Mi informe sobre IA" --title "Informe Q4"
r sql ventas.csv "SELECT * FROM data WHERE año = 2024"
r resume documento.pdf --style detailed
r code "función para ordenar lista" --run
```

## 📚 Skills disponibles

| Skill | Descripción | Ejemplo |
|-------|-------------|---------|
| `pdf` | Genera documentos PDF | `r pdf "contenido" --template business` |
| `resume` | Resume documentos largos | `r resume archivo.pdf` |
| `sql` | Consultas SQL sobre CSVs/DBs | `r sql data.csv "SELECT *"` |
| `code` | Genera y ejecuta código | `r code "hola mundo" --run` |
| `fs` | Operaciones de archivos | `r ls --pattern "*.py"` |

## ⚙️ Configuración

Crea `~/.r-cli/config.yaml`:

```yaml
llm:
  provider: lm-studio  # o 'ollama'
  base_url: http://localhost:1234/v1
  model: local-model
  temperature: 0.7

ui:
  theme: ps2  # ps2, matrix, minimal, retro, cyberpunk

rag:
  enabled: true
  persist_directory: ~/.r-cli/vectordb
```

## 🎨 Temas

```bash
r --theme matrix   # Verde estilo Matrix
r --theme ps2      # Azul PlayStation 2
r --theme minimal  # Limpio y simple
r --theme retro    # CRT vintage
```

## 🔧 Crear tu propio Skill

```python
# ~/.r-cli/skills/mi_skill.py

from r_cli.core.agent import Skill
from r_cli.core.llm import Tool

class MiSkill(Skill):
    name = "mi_skill"
    description = "Mi skill personalizado"

    def get_tools(self) -> list[Tool]:
        return [
            Tool(
                name="mi_funcion",
                description="Hace algo útil",
                parameters={...},
                handler=self.mi_funcion,
            )
        ]

    def mi_funcion(self, arg1: str) -> str:
        return f"Resultado: {arg1}"
```

## 🗺️ Roadmap

- [x] Core agentic con LM Studio/Ollama
- [x] Skills: PDF, SQL, Code, Resume, Filesystem
- [x] UI con animaciones PS2/Matrix
- [x] RAG persistente
- [ ] Voice mode (Whisper + Piper TTS)
- [ ] Integración Stable Diffusion para diseño
- [ ] Multi-agent orchestration
- [ ] Plugin marketplace

## 🤝 Contribuir

¡Las contribuciones son bienvenidas!

1. Fork el repositorio
2. Crea una rama (`git checkout -b feature/nueva-funcionalidad`)
3. Commit tus cambios (`git commit -m 'Agrega nueva funcionalidad'`)
4. Push a la rama (`git push origin feature/nueva-funcionalidad`)
5. Abre un Pull Request

## 📄 Licencia

MIT License - Usa R CLI como quieras.

---

**R CLI** - Porque tu IA debería ser tuya. 🔒
