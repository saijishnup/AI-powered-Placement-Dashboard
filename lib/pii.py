"""Scrub contact details from free text before it reaches any LLM prompt."""
import re

PATTERNS = [
    (re.compile(r"https?://\S+|www\.\S+|\b(?:[a-z0-9-]+\.)*linkedin\.com/\S*", re.I), "[link]"),
    (re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+"), "[email]"),
    (re.compile(r"(?<!\d)(?:\+?91[\s-]?)?[6-9]\d{4}[\s-]?\d{5}(?!\d)"), "[phone]"),  # Indian mobile numbers
]


def scrub(text, names=()):
    """Remove links, emails, phone numbers, and any given names (author's own name) from text."""
    text = text or ""
    for rx, repl in PATTERNS:
        text = rx.sub(repl, text)
    for n in names:
        for part in (n or "").split():
            if len(part) > 2:
                text = re.sub(rf"\b{re.escape(part)}\b", "[name]", text, flags=re.I)
    return text


if __name__ == "__main__":
    s = scrub("mail me at a.b@nitk.edu.in or +91 98765 43210, linkedin.com/in/xyz. Ravi Kumar here", ["Ravi Kumar"])
    assert "@" not in s and "98765" not in s and "linkedin" not in s and "Ravi" not in s, s
    print(s)
