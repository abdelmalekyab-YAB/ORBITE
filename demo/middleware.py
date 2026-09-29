"""Make rendered pages work inside the demo shell's iframe.

Static files are inlined (the iframe has no server to fetch them from) and a small bridge
script hands links, forms and fetch() calls back to the shell, which runs them through Django.
"""
import re
from pathlib import Path

from django.conf import settings

STATIC_DIR = Path(settings.BASE_DIR) / "static"
_cache = {}

BRIDGE = """<script>
(function () {
  var shell = window.parent && window.parent.orbitShell;
  if (!shell) return;
  window.fetch = function (url, init) { return shell.fetch(String(url), init || {}); };
  HTMLFormElement.prototype.submit = function () { shell.submit(this, null); };
  document.addEventListener("click", function (e) {
    var a = e.target.closest && e.target.closest("a[href]");
    if (!a || e.defaultPrevented) return;
    var href = a.getAttribute("href");
    if (!href || href.charAt(0) === "#" || /^(mailto|tel):/.test(href)) return;
    e.preventDefault();
    shell.link(href, a);
  });
  document.addEventListener("submit", function (e) {
    var form = e.target;
    if (e.defaultPrevented || (form.getAttribute("method") || "").toLowerCase() === "dialog") return;
    e.preventDefault();
    shell.submit(form, e.submitter || null);
  });
  shell.pageReady(document);
})();
</script>"""


def _static(path):
    if path not in _cache:
        text = (STATIC_DIR / path).read_text(encoding="utf-8")
        # There is nothing to reload in the iframe: ask the shell to render the page again.
        text = text.replace("location.reload()", "window.parent.orbitShell.reload()")
        _cache[path] = text.replace("</script", "<\\/script")
    return _cache[path]


def _inline(html):
    html = re.sub(r'<link rel="stylesheet" href="/static/([^"]+)">',
                  lambda m: f"<style>{_static(m.group(1))}</style>", html)
    html = re.sub(r'<script src="/static/([^"]+)"></script>',
                  lambda m: f"<script>{_static(m.group(1))}</script>", html)
    return html.replace("<head>", "<head>" + BRIDGE.replace("shell.pageReady(document);", ""), 1).replace(
        "</body>", "<script>window.parent.orbitShell && window.parent.orbitShell.pageReady(document);</script></body>", 1)


class DemoPageMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if response.get("Content-Type", "").startswith("text/html") and not response.streaming:
            response.content = _inline(response.content.decode("utf-8")).encode("utf-8")
        return response


def demo_context(request):
    return {"orbit_demo": True}
