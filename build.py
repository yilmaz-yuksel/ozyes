"""template.html + app.js + data.json -> ozyes-analizor.html

Builds the Turkish-language browser viewer as a single, self-contained HTML file that can be
opened locally or placed on a web server. The data are embedded in the page.
"""
from pathlib import Path

root = Path(__file__).parent
data = (root / "data.json").read_text(encoding="utf-8")
js = (root / "app.js").read_text(encoding="utf-8").replace("__DATA__", data, 1)
body = (root / "template.html").read_text(encoding="utf-8").rstrip() + "\n\n<script>\n" + js + "</script>\n"

standalone = (
    "<!doctype html>\n"
    '<html lang="tr">\n<head>\n'
    '<meta charset="utf-8">\n'
    '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">\n'
    + body.replace("</style>", "</style>\n</head>\n<body>", 1)
    + "</body>\n</html>\n"
)
(root / "ozyes-analizor.html").write_text(standalone, encoding="utf-8")
print("written: ozyes-analizor.html", len(standalone.encode("utf-8")), "bytes")
