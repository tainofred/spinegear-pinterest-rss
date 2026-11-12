#!/usr/bin/env python3
"""Convert Spinegear's public Shopify Atom feed into Pinterest-compatible RSS 2.0."""
import datetime as dt
import email.utils
import html
import re
import urllib.request
import xml.etree.ElementTree as ET
from html.parser import HTMLParser
from pathlib import Path
from xml.sax.saxutils import escape

SOURCE = "https://spinegear.co.uk/blogs/health-advice.atom"
ATOM = "{http://www.w3.org/2005/Atom}"
OUTPUT = Path("docs/feed.xml")

class Extract(HTMLParser):
    def __init__(self):
        super().__init__()
        self.images = []
        self.text = []
        self.skip = 0
    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag in ("script", "style"):
            self.skip += 1
        if tag == "img":
            url = a.get("src") or a.get("data-src") or ""
            if url.startswith("//"):
                url = "https:" + url
            if url.startswith("https://"):
                self.images.append(url)
    def handle_endtag(self, tag):
        if tag in ("script", "style") and self.skip:
            self.skip -= 1
    def handle_data(self, data):
        if not self.skip:
            self.text.append(data)

def tag(name, value):
    return "<" + name + ">" + escape(value or "") + "</" + name + ">"

def main():
    req = urllib.request.Request(SOURCE, headers={"User-Agent": "SpinegearPinterestFeed/1.0"})
    with urllib.request.urlopen(req, timeout=35) as response:
        data = response.read()
    root = ET.fromstring(data)
    items = []
    for entry in root.findall(ATOM + "entry"):
        title = (entry.findtext(ATOM + "title") or "").strip()
        link = next((node.attrib.get("href", "") for node in entry.findall(ATOM + "link")
                     if node.attrib.get("rel", "alternate") == "alternate"), "")
        if not link.startswith("https://spinegear.co.uk/blogs/health-advice/"):
            continue
        raw = (entry.findtext(ATOM + "content") or entry.findtext(ATOM + "summary") or "")
        parser = Extract()
        parser.feed(html.unescape(raw))
        image = next((u for u in parser.images if "cdn.shopify.com" in u), "")
        # Some Shopify feeds include an image in the summary rather than content.
        if not image:
            summary = entry.findtext(ATOM + "summary") or ""
            p2 = Extract()
            p2.feed(html.unescape(summary))
            image = next((u for u in p2.images if "cdn.shopify.com" in u), "")
        if not image:
            print("Skipping entry without a Shopify image:", link)
            continue
        words = re.sub(r"\\s+", " ", " ".join(parser.text)).strip()
        description = words[:390].rsplit(" ", 1)[0] + ("…" if len(words) > 390 else "")
        if not description:
            description = title + " — read the full guide on Spinegear UK."
        updated = entry.findtext(ATOM + "published") or entry.findtext(ATOM + "updated") or ""
        try:
            stamp = dt.datetime.fromisoformat(updated.replace("Z", "+00:00"))
            pub = email.utils.format_datetime(stamp)
        except ValueError:
            pub = email.utils.format_datetime(dt.datetime.now(dt.timezone.utc))
        # Escape image URL and text for XML; HTML image makes the image discoverable.
        desc_html = '<img src="' + html.escape(image, quote=True) + '" alt="' + html.escape(title, quote=True) + '" /> ' + html.escape(description)
        item = "<item>\n" + tag("title", title) + "\n" + tag("link", link) + "\n"
        item += tag("guid", link) + "\n" + tag("pubDate", pub) + "\n"
        item += tag("description", desc_html) + "\n"
        item += '<media:content url="' + html.escape(image, quote=True) + '" medium="image" />\n'
        item += "</item>"
        items.append(item)
    if not items:
        raise RuntimeError("No image-bearing Spinegear Health Advice articles found; refusing to overwrite existing feed")
    now = email.utils.format_datetime(dt.datetime.now(dt.timezone.utc))
    rss = '<?xml version="1.0" encoding="UTF-8"?>\n'
    rss += '<rss version="2.0" xmlns:media="http://search.yahoo.com/mrss/">\n<channel>\n'
    rss += tag("title", "Spinegear Health Advice & Wellness Tips") + "\n"
    rss += tag("link", "https://spinegear.co.uk/blogs/health-advice") + "\n"
    rss += tag("description", "UK home health, posture, comfort and wellbeing guides from Spinegear.") + "\n"
    rss += tag("lastBuildDate", now) + "\n" + "\n".join(items) + "\n</channel>\n</rss>\n"
    ET.fromstring(rss.encode("utf-8"))
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(rss, encoding="utf-8")
    print("Created", OUTPUT, "with", len(items), "image-bearing articles")

if __name__ == "__main__":
    main()
