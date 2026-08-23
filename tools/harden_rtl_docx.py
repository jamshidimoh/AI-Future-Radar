#!/usr/bin/env python3
"""Deterministic RTL hardening for generated DOCX files.

Inspired by the public MIT-licensed claude-arabic-docs project
(https://github.com/muhmoosa/claude-arabic-docs).

This local implementation keeps the build reproducible and avoids fetching
third-party code during CI. It applies the key OOXML layers needed by Word for
Persian/RTL documents: themeFontLang, section bidi, table bidiVisual,
paragraph bidi, run rtl, and RTL-aware paragraph alignment.
"""
from __future__ import annotations

import argparse
import shutil
import tempfile
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
NS = {"w": W}
ET.register_namespace("w", W)
RTL_LOCALE_DEFAULT = "fa-IR"
RTL_RANGES = (
    (0x0590, 0x05FF), (0x0600, 0x06FF), (0x0700, 0x074F),
    (0x0750, 0x077F), (0x0780, 0x07BF), (0x07C0, 0x07FF),
    (0x0800, 0x083F), (0x0840, 0x085F), (0x08A0, 0x08FF),
    (0xFB1D, 0xFDFF), (0xFE70, 0xFEFF),
)


def q(name: str) -> str:
    return f"{{{W}}}{name}"


def has_rtl(text: str) -> bool:
    return any(lo <= ord(ch) <= hi for ch in text for lo, hi in RTL_RANGES)


def ensure(parent: ET.Element, tag: str, *, before: str | None = None) -> ET.Element:
    node = parent.find(tag, NS)
    if node is not None:
        return node
    node = ET.Element(q(tag.split('}')[-1]))
    if before:
        for idx, child in enumerate(list(parent)):
            if child.tag == q(before):
                parent.insert(idx, node)
                return node
    parent.append(node)
    return node


def paragraph_text(p: ET.Element) -> str:
    return "".join((t.text or "") for t in p.findall(".//w:t", NS))


def harden_document(root: ET.Element) -> tuple[int, list[str]]:
    changes = 0
    issues: list[str] = []

    # Section-level direction.
    for sect in root.findall(".//w:sectPr", NS):
        if sect.find("w:bidi", NS) is None:
            # Schema-safe position: before rtlGutter/docGrid where present.
            node = ET.Element(q("bidi"))
            inserted = False
            for idx, child in enumerate(list(sect)):
                if child.tag in {q("rtlGutter"), q("docGrid"), q("printerSettings"), q("sectPrChange")}:
                    sect.insert(idx, node)
                    inserted = True
                    break
            if not inserted:
                sect.append(node)
            changes += 1

    # Paragraph/run direction.
    for p in root.findall(".//w:p", NS):
        text = paragraph_text(p)
        if not has_rtl(text):
            continue
        ppr = p.find("w:pPr", NS)
        if ppr is None:
            ppr = ET.Element(q("pPr"))
            p.insert(0, ppr)
        if ppr.find("w:bidi", NS) is None:
            node = ET.Element(q("bidi"))
            # bidi belongs before jc in the canonical ordering used here.
            jc = ppr.find("w:jc", NS)
            if jc is not None:
                ppr.insert(list(ppr).index(jc), node)
            else:
                ppr.append(node)
            changes += 1
        jc = ppr.find("w:jc", NS)
        if jc is None:
            jc = ET.Element(q("jc"))
            ppr.append(jc)
        if jc.get(q("val")) in (None, "right", "left"):
            jc.set(q("val"), "start")
            changes += 1

        for r in p.findall("w:r", NS):
            r_text = "".join((t.text or "") for t in r.findall("w:t", NS))
            if not has_rtl(r_text):
                continue
            rpr = r.find("w:rPr", NS)
            if rpr is None:
                rpr = ET.Element(q("rPr"))
                r.insert(0, rpr)
            if rpr.find("w:rtl", NS) is None:
                rpr.insert(0, ET.Element(q("rtl")))
                changes += 1

    # Table direction.
    for tblpr in root.findall(".//w:tbl/w:tblPr", NS):
        if tblpr.find("w:bidiVisual", NS) is None:
            node = ET.Element(q("bidiVisual"))
            for idx, child in enumerate(list(tblpr)):
                if child.tag in {q("tblW"), q("jc"), q("tblCellSpacing"), q("tblInd"), q("tblBorders"), q("tblLayout"), q("tblLook"), q("tblPrChange")}:
                    tblpr.insert(idx, node)
                    break
            else:
                tblpr.append(node)
            changes += 1

    return changes, issues


def harden_styles(root: ET.Element, locale: str) -> int:
    changes = 0
    doc_defaults = root.find(".//w:docDefaults", NS)
    if doc_defaults is None:
        doc_defaults = ET.Element(q("docDefaults"))
        root.append(doc_defaults)
    rpr_default = doc_defaults.find("w:rPrDefault", NS)
    if rpr_default is None:
        rpr_default = ET.Element(q("rPrDefault"))
        doc_defaults.insert(0, rpr_default)
    rpr = rpr_default.find("w:rPr", NS)
    if rpr is None:
        rpr = ET.Element(q("rPr"))
        rpr_default.append(rpr)
    lang = rpr.find("w:lang", NS)
    if lang is None:
        lang = ET.Element(q("lang"))
        rpr.append(lang)
        changes += 1
    if lang.get(q("bidi")) != locale:
        lang.set(q("bidi"), locale)
        changes += 1

    ppr_default = doc_defaults.find("w:pPrDefault", NS)
    if ppr_default is None:
        ppr_default = ET.Element(q("pPrDefault"))
        doc_defaults.append(ppr_default)
    ppr = ppr_default.find("w:pPr", NS)
    if ppr is None:
        ppr = ET.Element(q("pPr"))
        ppr_default.append(ppr)
    if ppr.find("w:bidi", NS) is None:
        ppr.insert(0, ET.Element(q("bidi")))
        changes += 1
    jc = ppr.find("w:jc", NS)
    if jc is None:
        jc = ET.Element(q("jc"))
        ppr.append(jc)
        changes += 1
    if jc.get(q("val")) != "start":
        jc.set(q("val"), "start")
        changes += 1

    return changes


def harden_settings(root: ET.Element, locale: str) -> int:
    changes = 0
    theme = root.find("w:themeFontLang", NS)
    if theme is None:
        theme = ET.Element(q("themeFontLang"))
        root.insert(0, theme)
        changes += 1
    if theme.get(q("bidi")) != locale:
        theme.set(q("bidi"), locale)
        changes += 1
    return changes


def process(src: Path, dst: Path, locale: str, validate: bool) -> int:
    with zipfile.ZipFile(src, "r") as zin:
        with tempfile.TemporaryDirectory() as td:
            temp = Path(td)
            for info in zin.infolist():
                out = temp / info.filename
                out.parent.mkdir(parents=True, exist_ok=True)
                out.write_bytes(zin.read(info.filename))

            changes = 0
            # settings.xml
            settings = temp / "word" / "settings.xml"
            if settings.exists():
                root = ET.parse(settings).getroot()
                changes += harden_settings(root, locale)
                ET.ElementTree(root).write(settings, encoding="utf-8", xml_declaration=True)

            # styles.xml
            styles = temp / "word" / "styles.xml"
            if styles.exists():
                root = ET.parse(styles).getroot()
                changes += harden_styles(root, locale)
                ET.ElementTree(root).write(styles, encoding="utf-8", xml_declaration=True)

            # document + headers/footers
            word_dir = temp / "word"
            targets = [word_dir / "document.xml", *sorted(word_dir.glob("header*.xml")), *sorted(word_dir.glob("footer*.xml"))]
            for path in targets:
                if not path.exists():
                    continue
                root = ET.parse(path).getroot()
                c, _ = harden_document(root)
                changes += c
                ET.ElementTree(root).write(path, encoding="utf-8", xml_declaration=True)

            if validate:
                settings_root = ET.parse(settings).getroot() if settings.exists() else None
                styles_root = ET.parse(styles).getroot() if styles.exists() else None
                if settings_root is not None and settings_root.find("w:themeFontLang", NS) is None:
                    raise SystemExit("RTL validation failed: settings.xml missing themeFontLang")
                if styles_root is not None and styles_root.find(".//w:lang[@w:bidi]", NS) is None:
                    raise SystemExit("RTL validation failed: styles.xml missing bidi language")

            dst.parent.mkdir(parents=True, exist_ok=True)
            with zipfile.ZipFile(dst, "w", compression=zipfile.ZIP_DEFLATED) as zout:
                for path in temp.rglob("*"):
                    if path.is_file():
                        zout.write(path, path.relative_to(temp).as_posix())

    print(f"RTL hardening: changes={changes}; locale={locale}; output={dst}")
    return changes


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("input")
    ap.add_argument("-o", "--output")
    ap.add_argument("--locale", default=RTL_LOCALE_DEFAULT)
    ap.add_argument("--validate", action="store_true")
    args = ap.parse_args()
    src = Path(args.input)
    dst = Path(args.output) if args.output else src.with_name(src.stem + ".rtl.docx")
    process(src, dst, args.locale, args.validate)
    if args.output and dst != src:
        shutil.move(dst, src)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
