# University of Houston Economics PhD applicant information

Site: https://fanwangecon.github.io/UHouston-EconPhD/

The homepage, Links tab, Flyer tab, and two downloadable PDFs are built from
the same YAML revision. Edit program information only in:

- [`data/links.yml`](data/links.yml): applicant links, labels, and contact details.
- [`data/flyer.yml`](data/flyer.yml): flyer sections, deadline, links, and image references.

The initial content faithfully follows the supplied 2026 applicant-links document
and 2027 flyer. Dates and factual claims are not automatically updated.
The supplied flyer imagery is included with the content owner's authorization.

## Local build in WSL2

For a new environment, from the repository directory:

```bash
conda env create -f environment.yml
conda activate uh-econ-pages
python build.py
python -m unittest discover -s tests -v
python -m http.server 8000 --directory _site
```

For the existing `wk_pyfan` environment:

```bash
conda activate wk_pyfan
conda install -c conda-forge tectonic=0.17.0 --freeze-installed
python -m pip install -r requirements-test.txt
python build.py
python -m unittest discover -s tests -v
python -m http.server 8000 --directory _site
```

Open http://localhost:8000/. Stop the preview with Ctrl+C when finished.
Tectonic (a LaTeX engine) downloads its required TeX packages on the first build,
so initial compilation needs internet access. No program content is uploaded
for PDF conversion: compilation runs locally or on the GitHub Actions runner.

The generated site is in `_site/`, including:

- `index.html`, `links.html`, and `flyer.html`.
- `assets/useful-links.pdf` and `assets/current-flyer.pdf`.

Local PDFs and intermediate LaTeX files stay in ignored `_site/` and `.build/`
directories. Do not commit generated outputs or the original source documents.
HTML and PDF templates in `templates/` control presentation, not the program facts.
The flyer uses Carlito, an open font metrically compatible with the original
Calibri, and the original photo crops to approximate the supplied PDF layout.
All page links are relative, so the build works both as this personal-account
project site and after a future transfer to an organization Pages repository.

## Deployment

In repository **Settings > Pages**, select **GitHub Actions** as the source.
Every push to `main` builds and tests HTML plus both LaTeX PDFs, uploads the complete
`_site` artifact, and deploys it to Pages. Pull requests build and test without
deploying. A failed build or validation does not replace the last successful site.
The PDFs are generated at build time, not on each visitor request.

## Git identity

This checkout uses a repository-local `FanWangEcon` commit author and GitHub
username, with the existing WSL Git credential helper. Those settings do not
change other repositories. Commit identity does not grant push permissions:
the helper must authenticate an account with access to the remote repository.
If its cached authentication expires, authenticate again using your existing
WSL GitHub credential setup; do not put tokens in files, URLs, or Git configuration.

WSL GitHub CLI is authorized as `FanWangEcon` with `repo` and `workflow`
permissions and configured as the GitHub credential helper. To renew that
authorization in an interactive WSL terminal, use
`gh auth refresh --hostname github.com --scopes workflow`, then
`gh auth setup-git --hostname github.com`. This changes GitHub authentication
for WSL generally; repository-local commit identities remain unchanged.
