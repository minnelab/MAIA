import os


def find_notebooks(directory):
    notebooks = []
    for root, _, files in os.walk(directory):
        for file in files:
            if file.endswith(".ipynb") or file.endswith(".md") or file.endswith(".rst"):
                notebooks.append(os.path.relpath(os.path.join(root, file), directory))
    return notebooks


def generate_rst(notebooks, output_file):
    grouped_notebooks = {}
    for notebook in notebooks:
        subfolder = os.path.dirname(notebook)
        if subfolder not in grouped_notebooks:
            grouped_notebooks[subfolder] = []
        grouped_notebooks[subfolder].append(notebook)

    with open(output_file, 'w') as f:
        f.write("Tutorials\n")
        f.write("=========\n\n")
        for subfolder, notebooks in grouped_notebooks.items():
            if subfolder:
                last_subfolder = subfolder.split("/")[-1]
                f.write(f"{last_subfolder}\n")
                f.write(f"{'-' * len(last_subfolder)}\n\n")
            f.write(".. toctree::\n")
            f.write("   :maxdepth: 1\n\n")
            readme_found = False
            for notebook in notebooks:
                if "README.md" in notebook:
                    # title = os.path.splitext(os.path.basename(notebook))[0]
                    f.write(f"   tutorials/{notebook}\n")
                    readme_found = True
                    break
            if not readme_found:
                for notebook in notebooks:
                    # title = os.path.splitext(os.path.basename(notebook))[0]
                    f.write(f"   tutorials/{notebook}\n")
            f.write("\n")


if __name__ == "__main__":
    tutorial_dir = os.path.join(os.path.dirname(__file__), '..', 'source', 'apidocs', 'tutorials')
    output_file = os.path.join(os.path.dirname(__file__), '..', 'source', 'apidocs', 'tutorials.rst')
    notebooks = find_notebooks(tutorial_dir)
    generate_rst(notebooks, output_file)