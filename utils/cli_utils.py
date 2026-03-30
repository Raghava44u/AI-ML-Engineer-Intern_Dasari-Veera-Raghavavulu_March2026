import sys
import platform
import re

# Config flag to toggle emoji usage globally
USE_EMOJIS = True

def setup_terminal():
    """
    Recommended for Windows: Forces UTF-8 encoding on standard output.
    Helps resolve 'charmap' and UnicodeEncodeErrors in PowerShell/CMD.
    """
    if platform.system() == "Windows":
        try:
            # sys.stdout.reconfigure is available in Python 3.7+
            sys.stdout.reconfigure(encoding='utf-8')
            sys.stderr.reconfigure(encoding='utf-8')
        except (AttributeError, Exception):
            # Fallback if reconfigure fails (e.g. older env or specific stubs)
            pass

# Initialize once on import
setup_terminal()

def strip_emojis(text: str) -> str:
    """Removes or replaces known high-Unicode characters with ASCII equivalents."""
    # This is a basic emoji/special character stripper for terminal compatibility
    # Matches common Unicode emojis in the range \U00010000-\U0010ffff
    return re.sub(r'[\U00010000-\U0010ffff]', '', text)

def safe_print(text: str, **kwargs):
    """
    Prints content safely across all platforms.
    
    1. Respects USE_EMOJIS flag.
    2. Gracefully falls back to ASCII if a terminal cannot handle specific characters.
    """
    # 1. Option: Global disable
    if not USE_EMOJIS:
        text = strip_emojis(text)
        # Optional: Replace common icons with ASCII equivalents
        text = text.replace("🎓", "[GRAD]").replace("🔨", "[BUILD]").replace("✓", "[OK]")
        text = text.replace("🎯", "[GOAL]").replace("📋", "[PLAN]").replace("⚠", "[WARN]")
    
    try:
        # Standard attempt
        print(text, flush=True, **kwargs)
    except UnicodeEncodeError:
        # 2. Resilient Fallback: Strip anything that isn't ASCII
        # This prevents the CLI from crashing even if terminal is severely restricted
        safe_text = text.encode('ascii', 'ignore').decode('ascii')
        print(safe_text, flush=True, **kwargs)

# Sample of Safe ASCII Mappings (Tier 3 fallback)
ASCII_EMOJI_MAP = {
    "🎓": "[RAG]",
    "🔨": "[B]",
    "✓": "[OK]",
    "🎯": "[D]",
    "📋": "[P]",
    "⚠️": "[W]",
    "✅": "[V]",
    "❌": "[X]",
    "💬": "[C]",
    "📊": "[E]",
    "🔨": "[BUILD]"
}

def smart_print(text: str, **kwargs):
    """Tiered approach for interview-ready production CLI."""
    if not USE_EMOJIS:
        # Tier 1: User-selected override
        for emoji, label in ASCII_EMOJI_MAP.items():
            text = text.replace(emoji, label)
        text = strip_emojis(text)
        print(text, **kwargs)
        return

    try:
        # Tier 2: Try native UTF-8 (reconfigured in setup_terminal)
        print(text, **kwargs)
    except UnicodeException:
        # Tier 3: Immediate ASCII fallback if stdout still chokes
        temp_text = text
        for emoji, label in ASCII_EMOJI_MAP.items():
            temp_text = temp_text.replace(emoji, label)
        # Strip remains
        final_text = temp_text.encode('ascii', 'ignore').decode('ascii')
        print(final_text, **kwargs)
