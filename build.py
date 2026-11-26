import argparse
from pathlib import Path
import re
import shutil
import subprocess
from urllib.parse import urlsplit

from jinja2 import Environment, FileSystemLoader, StrictUndefined, select_autoescape
import yaml


ROOT = Path(__file__).resolve().parent
PDF_FILES = {"links": "useful-links.pdf", "flyer": "current-flyer.pdf"}


class UniqueKeyLoader(yaml.SafeLoader):
    pass


def unique_mapping(loader, node):
    result = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node)
        if key in result:
            raise ValueError(f"Duplicate YAML key: {key}")
        result[key] = loader.construct_object(value_node)
    return result


UniqueKeyLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, unique_mapping
)


def text(value, location):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{location} must be a non-empty string")
    return value


def web_url(value, location):
    text(value, location)
    parsed = urlsplit(value)
    if (
        parsed.scheme != "https"
        or not parsed.netloc
        or parsed.username
        or parsed.password
        or any(char.isspace() for char in value)
    ):
        raise ValueError(f"{location} must be an HTTPS URL without credentials")


def load_data(root=ROOT):
    data = {}
    for name in PDF_FILES:
        path = root / "data" / f"{name}.yml"
        with path.open(encoding="utf-8") as stream:
            data[name] = yaml.load(stream, Loader=UniqueKeyLoader)
        if not isinstance(data[name], dict):
            raise ValueError(f"{path} must contain a mapping")
        for field in ("title", "contact_email", "pdf_label"):
            text(data[name].get(field), f"{name}.{field}")
        if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", data[name]["contact_email"]):
            raise ValueError(f"{name}.contact_email is not a valid email address")
    links, flyer = data["links"], data["flyer"]
    for field in ("subtitle", "organization", "department"):
        text(links.get(field), f"links.{field}")
    if not isinstance(links.get("items"), list) or not links["items"]:
        raise ValueError("links.items must be a non-empty list")
    for index, item in enumerate(links["items"]):
        if not isinstance(item, dict):
            raise ValueError(f"links.items[{index}] must be a mapping")
        text(item.get("title"), f"links.items[{index}].title")
        web_url(item.get("url"), f"links.items[{index}].url")
    for field in ("deadline", "apply_label", "contact_label"):
        text(flyer.get(field), f"flyer.{field}")
    web_url(flyer.get("apply_url"), "flyer.apply_url")
    webinar = flyer.get("webinar")
    if not isinstance(webinar, dict):
        raise ValueError("flyer.webinar must be a mapping")
    for field in ("title", "date", "timezone", "signup_label"):
        text(webinar.get(field), f"flyer.webinar.{field}")
    web_url(webinar.get("signup_url"), "flyer.webinar.signup_url")
    if not isinstance(webinar.get("times"), list) or not webinar["times"]:
        raise ValueError("flyer.webinar.times must be a non-empty list")
    for time in webinar["times"]:
        text(time, "flyer.webinar.times")
    if not isinstance(flyer.get("sections"), list) or not flyer["sections"]:
        raise ValueError("flyer.sections must be a non-empty list")
    for index, section in enumerate(flyer["sections"]):
        if not isinstance(section, dict):
            raise ValueError(f"flyer.sections[{index}] must be a mapping")
        text(section.get("title"), f"flyer.sections[{index}].title")
        if "introduction" in section:
            text(section["introduction"], f"flyer.sections[{index}].introduction")
        if not isinstance(section.get("items"), list) or not section["items"]:
            raise ValueError(f"flyer.sections[{index}].items must be a non-empty list")
        for item in section["items"]:
            text(item, f"flyer.sections[{index}].items")
        if "more" in section:
            if not isinstance(section["more"], dict):
                raise ValueError(f"flyer.sections[{index}].more must be a mapping")
            for field in ("prefix", "label"):
                text(section["more"].get(field), f"flyer.sections[{index}].more.{field}")
            web_url(section["more"].get("url"), f"flyer.sections[{index}].more.url")
    if not isinstance(flyer.get("images"), dict):
        raise ValueError("flyer.images must be a mapping")
    for position in ("header", "footer"):
        image = flyer["images"].get(position)
        if not isinstance(image, dict):
            raise ValueError(f"flyer.images.{position} must be a mapping")
        text(image.get("alt"), f"flyer.images.{position}.alt")
        relative = Path(text(image.get("src"), f"flyer.images.{position}.src"))
        source = (root / relative).resolve()
        if (
            relative.is_absolute()
            or not source.is_relative_to((root / "assets" / "images").resolve())
            or not source.is_file()
        ):
            raise ValueError(f"flyer.images.{position}.src must name an existing asset image")
    return data


def latex_escape(value):
    replacements = {
        "\\": r"\textbackslash{}",
        "&": r"\&",
        "%": r"\%",
        "$": r"\$",
        "#": r"\#",
        "_": r"\_",
        "{": r"\{",
        "}": r"\}",
        "~": r"\textasciitilde{}",
        "^": r"\textasciicircum{}",
    }
    return "".join(replacements.get(char, char) for char in str(value))


def render_html(data, output, root=ROOT):
    environment = Environment(
        loader=FileSystemLoader(root / "templates"),
        undefined=StrictUndefined,
        autoescape=select_autoescape(["html"]),
    )
    output.mkdir(parents=True, exist_ok=True)
    shutil.copytree(root / "assets", output / "assets", dirs_exist_ok=True)
    for page in ("index", "links", "flyer"):
        rendered = environment.get_template(f"{page}.html").render(
            **data, page=page, pdf_files=PDF_FILES
        )
        (output / f"{page}.html").write_text(rendered, encoding="utf-8")
    (output / ".nojekyll").touch()


def build(output=ROOT / "_site"):
    data = load_data()
    if not shutil.which("tectonic"):
        raise RuntimeError("Tectonic is required. Activate the Conda environment in README.md.")
    output = output.resolve()
    if output != ROOT / "_site":
        raise ValueError("The build output must be the repository's _site directory")
    # Delete only this build's known files, so removed content cannot survive a rebuild.
    for filename in ("index.html", "links.html", "flyer.html"):
        (output / filename).unlink(missing_ok=True)
    for filename in PDF_FILES.values():
        (output / "assets" / filename).unlink(missing_ok=True)
    render_html(data, output)
    environment = Environment(
        loader=FileSystemLoader(ROOT / "templates"),
        undefined=StrictUndefined,
        block_start_string="((*",
        block_end_string="*))",
        variable_start_string="((",
        variable_end_string="))",
        autoescape=False,
    )
    environment.filters["tex"] = latex_escape
    work = ROOT / ".build"
    work.mkdir(exist_ok=True)
    shutil.copytree(ROOT / "assets" / "images", work / "assets" / "images", dirs_exist_ok=True)
    for name, filename in PDF_FILES.items():
        source = work / f"{name}.tex"
        source.write_text(
            environment.get_template(f"{name}.tex").render(**data), encoding="utf-8"
        )
        subprocess.run(
            ["tectonic", "--keep-logs", "--outdir", str(work), str(source)],
            cwd=ROOT,
            check=True,
        )
        log = (work / f"{name}.log").read_text(encoding="utf-8")
        if "Overfull \\hbox" in log or "Overfull \\vbox" in log:
            raise RuntimeError(f"{name}.pdf has overflowing content; inspect {name}.log")
        shutil.copyfile(work / f"{name}.pdf", output / "assets" / filename)
    print(f"Built three pages and both PDFs in {output}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Build HTML and LaTeX PDFs from YAML.")
    parser.parse_args()
    build()
