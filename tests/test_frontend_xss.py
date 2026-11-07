"""Frontend XSS guards (chat.js / shell.js), run in node against the real sources."""
import json
import re
import shutil
import subprocess
import unittest
from pathlib import Path

STATIC = Path(__file__).resolve().parent.parent / "static"
NODE = shutil.which("node")


def _function(src: str, name: str) -> str:
    """Cut one top-level `function name(...) {...}` out of a script by brace matching."""
    start = src.index(f"function {name}(")
    i = src.index("{", start)
    depth = 0
    while True:
        c = src[i]
        depth += c == "{"
        depth -= c == "}"
        i += 1
        if depth == 0:
            return src[start:i]


def _node(script: str):
    r = subprocess.run([NODE, "-e", script], capture_output=True, text=True, timeout=30)
    if r.returncode != 0:
        raise AssertionError(r.stderr)
    return json.loads(r.stdout)


# Enough of `document` for escapeHtml and the entity decoder in isSafeMarkdownUrl.
_DOC = r"""
const document = { createElement() { return { set innerHTML(v) { this.value = v
  .replace(/&#x([0-9a-f]+);?/gi, (_, h) => String.fromCharCode(parseInt(h, 16)))
  .replace(/&#(\d+);?/g, (_, d) => String.fromCharCode(+d))
  .replace(/&colon;/gi, ':').replace(/&amp;/g, '&'); },
  set textContent(v) { this._html = String(v).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;'); },
  get innerHTML() { return this._html; } }; } };
"""


@unittest.skipUnless(NODE, "node is not installed")
class ChatMarkdownTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        src = (STATIC / "chat.js").read_text("utf-8")
        cls.prelude = (f"const {{marked}} = require({json.dumps(str(STATIC / 'marked.min.js'))});\n" + _DOC
                       + _function(src, "escapeHtml") + "\n" + _function(src, "isSafeMarkdownUrl") + "\n"
                       + _function(src, "hatImgHtml") + "\n")
        init = _function(src, "init")
        cls.use = init[init.index("marked.use("):init.index("});", init.index("marked.use(")) + 3]

    def test_url_filter(self):
        urls = ["https://a.b/c", "http://x", "mailto:a@b.c", "/rel/path", "page.html", "#top", "?q=1",
                "javascript:alert(1)", " JaVaScRiPt:alert(1)", "java\tscript:x", "javascript&#58;x",
                "javascript&colon;x", "data:text/html,x", "vbscript:x", "file:///etc/passwd"]
        got = _node(self.prelude + f"console.log(JSON.stringify({json.dumps(urls)}.map(u => isSafeMarkdownUrl(u, false))))")
        self.assertEqual(got, [True] * 7 + [False] * 8)
        img = _node(self.prelude + "console.log(JSON.stringify([isSafeMarkdownUrl('mailto:a@b', true), "
                                   "isSafeMarkdownUrl('https://a/b.png', true)]))")
        self.assertEqual(img, [False, True])

    def test_marked_drops_unsafe_links_and_images(self):
        md = "[a **b**](javascript:alert(1)) [ok](https://x.y) ![pic &](javascript:x) ![j](https://a/b.png) [m](mailto:q@r.s)"
        html = _node(self.prelude + self.use + f"\nconsole.log(JSON.stringify(marked.parse({json.dumps(md)})))")
        self.assertNotIn("javascript", html)
        self.assertIn("a <strong>b</strong>", html)
        self.assertIn('<a href="https://x.y">ok</a>', html)
        self.assertIn('<img src="https://a/b.png" alt="j">', html)
        self.assertIn('href="mailto:q@r.s"', html)
        self.assertIn("pic &amp;", html)

    def test_hat_is_an_img_data_url(self):
        svg = '<svg viewBox="0 0 2 1"><script>alert(1)</script><rect onload="x()" width="2" height="1"/></svg>'
        html = _node(self.prelude + f"console.log(JSON.stringify(hatImgHtml({json.dumps(svg)})))")
        self.assertTrue(html.startswith('<img class="hat-img" src="data:image/svg+xml;charset=utf-8,%3Csvg%20xmlns'))
        self.assertNotIn("<script", html)
        self.assertNotIn('"x()"', html)
        self.assertEqual(html.count('"'), 10)  # every attribute value stays quoted

    def test_no_hat_svg_is_put_into_innerhtml_raw(self):
        src = (STATIC / "chat.js").read_text("utf-8")
        self.assertFalse(re.search(r"innerHTML\s*=\s*(newHat|svg)\s*;", src))
        self.assertNotIn("${hatSvg}", src)


@unittest.skipUnless(NODE, "node is not installed")
class ShellEscapeTests(unittest.TestCase):
    def test_esc_and_safe_color(self):
        src = (STATIC / "shell.js").read_text("utf-8")
        esc = re.search(r"^  const esc = .*$", src, re.M).group(0)
        color = src[src.index("  const safeColor"):src.index(": fallback;", src.index("  const safeColor")) + 11]
        got = _node(esc + "\n" + color + "\nconsole.log(JSON.stringify(["
                    "esc(`<a href=\"x\" title='y'>&`), esc(undefined),"
                    "safeColor('#7c5cff'), safeColor('rgb(1, 2, 3)'), safeColor('red;\" onload=\"x', '#888'),"
                    "safeColor('url(javascript:x)'), safeColor('#12345678'), safeColor('#1234567890')]))")
        self.assertEqual(got, ["&lt;a href=&quot;x&quot; title=&#39;y&#39;&gt;&amp;", "",
                               "#7c5cff", "rgb(1, 2, 3)", "#888", "", "#12345678", ""])
        self.assertIn("safeColor(a.color, '#888')", src)


if __name__ == "__main__":
    unittest.main()
