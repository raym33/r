# R CLI Troubleshooting Guide

## Common Issues

### 1. Context Length Exceeded

**Error:**
```
Error code: 400 - {'error': 'The number of tokens to keep from the initial prompt is greater than the context length'}
```

**Cause:** R CLI sends tool definitions to the LLM. With 74 skills (~480 tools), this can exceed small context windows.

**Solutions:**

#### Option A: Use Lite Mode
```bash
r --skills-mode lite chat "Hello"
```

#### Option B: Configure in config.yaml
```yaml
# ~/.r-cli/config.yaml
skills:
  mode: lite  # or: standard, auto
```

#### Option C: Whitelist Specific Skills
```yaml
skills:
  mode: whitelist
  enabled:
    - datetime
    - math
    - text
    - fs
    - code
```

#### Option D: Increase Context in LM Studio
1. Open LM Studio
2. Go to model settings
3. Increase "Context Length" to 16k or 32k

### 2. LLM Server Not Connected

**Error:**
```
No LLM server detected. Start LM Studio or Ollama.
```

**Solutions:**

1. **For LM Studio:**
   - Open LM Studio
   - Load a model
   - Click "Start Server"
   - Verify: `curl http://localhost:1234/v1/models`

2. **For Ollama:**
   - Start Ollama: `ollama serve`
   - Pull a model: `ollama pull qwen2.5:7b`
   - Verify: `curl http://localhost:11434/v1/models`

### 3. Timeout Errors

**Error:**
```
[WARNING] Attempt 1/4 failed: Request timed out.. Retrying in 1.0s...
```

**Cause:** The LLM is taking too long to respond.

**Solutions:**

1. **Use a smaller model** - 7B models are faster than 70B
2. **Increase timeout in config:**
   ```yaml
   llm:
     request_timeout: 120.0  # seconds
   ```
3. **Use lite mode** to send fewer tools

### 4. Missing Dependencies

**Error:**
```
[yellow]Missing dependency for PDFSkill: weasyprint not found[/yellow]
```

**Solution:** Install optional dependencies:
```bash
# PDF generation
pip install weasyprint

# Voice features
pip install faster-whisper piper-tts

# RAG features
pip install sentence-transformers chromadb

# All extras
pip install r-cli-ai[all]
```

### 5. Skill Loading Errors

**Error:**
```
Configuration error in SkillName: __init__() takes 1 positional argument but 2 were given
```

**Solution:** Update to v0.3.2+
```bash
pip install --upgrade r-cli-ai
```

### 6. API Server Issues

**Port already in use:**
```bash
# Find process using port 8765
lsof -i :8765

# Kill it
kill -9 <PID>

# Or use a different port
r serve --port 8766
```

## Debug Mode

For more verbose output:
```bash
# Show skill loading
r skills

# Check configuration
r config
```

## Getting Help

- [GitHub Issues](https://github.com/raym33/r/issues)
- [Quick Start Guide](QUICKSTART.md)
- [Full Documentation](COMPLETE_GUIDE.md)
