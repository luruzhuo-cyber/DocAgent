"""复现固定提交的官方语料；不会悄悄跟随 master 更新评测输入。"""

import base64
import hashlib
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "corpus"
COMMIT = "05e6df7e906c3decba377c37548019973f40bf15"
PAGES = [
    "first-steps",
    "path-params",
    "query-params",
    "body",
    "response-status-code",
    "handling-errors",
    "dependencies/index",
    "security/first-steps",
]


def get(url):
    return subprocess.check_output(
        [
            "curl.exe",
            "--fail",
            "-L",
            "-sS",
            "--retry",
            "2",
            "--connect-timeout",
            "10",
            "--max-time",
            "45",
            url,
        ]
    )


ROOT.mkdir(parents=True, exist_ok=True)
files = []
for page in PAGES:
    path = "docs/zh/docs/tutorial/" + page + ".md"
    url = f"https://raw.githubusercontent.com/fastapi/fastapi/{COMMIT}/{path}"
    name = page.replace("/", "-") + ".md"
    response = json.loads(
        get(
            f"https://api.github.com/repos/fastapi/fastapi/contents/{path}?ref={COMMIT}"
        )
    )
    data = base64.b64decode(response["content"])
    (ROOT / name).write_bytes(data)
    files.append(
        {
            "file": name,
            "source": url,
            "path": path,
            "sha256": hashlib.sha256(data).hexdigest(),
        }
    )
license_data = json.loads(
    get(f"https://api.github.com/repos/fastapi/fastapi/contents/LICENSE?ref={COMMIT}")
)
(ROOT / "LICENSE.fastapi").write_bytes(base64.b64decode(license_data["content"]))
(ROOT / "provenance.json").write_text(
    json.dumps(
        {
            "repository": "https://github.com/fastapi/fastapi",
            "commit": COMMIT,
            "license": "MIT",
            "authored_synthetic": False,
            "files": files,
        },
        ensure_ascii=False,
        indent=2,
    ),
    encoding="utf-8",
)
print(COMMIT, len(files))
