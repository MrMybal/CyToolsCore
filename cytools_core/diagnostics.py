"""Plain-text diagnostics utilities, without UI or model imports."""
import re

def redact(text):
    text=re.sub(r'\bhf_[A-Za-z0-9]{8,}\b','[REDACTED]',str(text))
    text=re.sub(r'(?i)(bearer\s+)[^\s,;\"\']+',r'\1[REDACTED]',text)
    return re.sub(r'''(?i)((?:["']?)(?:access_token|api_key|apikey|password|authorization|token|secret)(?:["']?)\s*[:=]\s*)(?:"[^"]*"|'[^']*'|[^\s,;}]+)''',r'\1[REDACTED]',text)
