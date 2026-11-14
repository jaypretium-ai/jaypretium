"""template.html + data.json -> index.html (single self-contained page)."""
from pathlib import Path
here = Path(__file__).parent
data = (here / "data.json").read_text(encoding="utf-8").replace("</", "<\\/")
(here / "index.html").write_text((here / "template.html").read_text(encoding="utf-8").replace("__DATA__", data), encoding="utf-8")
print("wrote index.html")
