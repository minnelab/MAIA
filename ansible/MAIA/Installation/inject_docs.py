import re
from pathlib import Path
import pypandoc

RST_FILE = Path("docs/docsite/rst/main.rst")
RST_EXAMPLE_FILE = Path("docs/docsite/rst/example.rst")
README = Path("README.md")

md = pypandoc.convert_text(
    RST_FILE.read_text(),
    to="md",
    format="rst"
)

md_example = pypandoc.convert_text(
    RST_EXAMPLE_FILE.read_text(),
    to="md",
    format="rst"
)

readme = README.read_text()

new_readme = re.sub(
    r"<!-- DOCS-START -->.*<!-- DOCS-END -->",
    f"<!-- DOCS-START -->\n{md.strip()}\n<!-- DOCS-END -->",
    readme,
    flags=re.S,
)

README.write_text(new_readme)


readme = README.read_text()

new_readme = re.sub(
    r"<!-- DOCS-EXAMPLE-START -->.*<!-- DOCS-EXAMPLE-END -->",
    f"<!-- DOCS-EXAMPLE-START -->\n{md_example.strip()}\n<!-- DOCS-EXAMPLE-END -->",
    readme,
    flags=re.S,
)

README.write_text(new_readme)
print("Injected RST docs into README.md")
