import os

def generate(prompt: str) -> str:
    """
    Generates a response from an LLM.
    If no API key is found, degrades gracefully to a template-based fallback.
    """
    openai_key = os.environ.get("OPENAI_API_KEY")
    anthropic_key = os.environ.get("ANTHROPIC_API_KEY")
    
    if not openai_key and not anthropic_key:
        return _fallback_generate(prompt)
        
    # Here we would initialize the OpenAI or Anthropic client.
    # For the hackathon, if keys are set but no client is implemented, just fallback.
    return _fallback_generate(prompt)

def _fallback_generate(prompt: str) -> str:
    """A deterministic fallback to ensure the demo is never blocked by API keys."""
    if "EXECUTIVE SUMMARY" in prompt:
        return "Based on the geometric analysis, the part contains some manufacturability issues that require attention. Please review the specific face-level findings."
    else:
        return "This feature violates standard DfM guidelines for injection molding. Consider revising the geometry to improve moldability."
