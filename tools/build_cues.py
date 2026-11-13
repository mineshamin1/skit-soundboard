#!/usr/bin/env python3
"""Build cues.json and CUE_SHEET.md from a Word script plus a folder of sound files.

Usage:
    python tools/build_cues.py --script input/script.docx --sounds sounds

Script conventions:
  - Title: the first Heading 1 (or Title) paragraph.
  - Scenes: any paragraph starting with "SCENE <number>", e.g. "SCENE 3: Money or Intelligence?".
  - Dialogue: "NAME: words" (any case), optionally "Name (stage note): words".
  - Sound cues: [SFX: name], matched to sounds/<name>.mp3 (case, spaces, dashes, underscores ignored).
    Other bracket styles are auto-detected; force one with --pattern "<regex with one group>".
  - input/aliases.json can map a tag to a file when names differ: {"big laugh": "haha.mp3"}
  - input/labels.json can set a button name for a file: {"doordarshn-5secGap-masti.mp3": "Doordarshan"}
Files in the sounds folder starting with "_" are helpers and are ignored.
"""
import argparse
import difflib
import json
import os
import re
import sys

from docx import Document

AUDIO_EXT = {".mp3", ".m4a", ".wav", ".aac", ".ogg", ".caf"}

CANDIDATE_PATTERNS = [
    r"\[\s*(?:SFX|SOUND|SE|FX)\s*[:\-]?\s*([^\]]+?)\s*\]",   # [SFX: door slam]
    r"\(\s*(?:SFX|SOUND|SE|FX)\s*[:\-]?\s*([^)]+?)\s*\)",    # (SFX: door slam)
    r"\[\s*([^\]]+?)\s*\]",                                   # [door slam]
    r"\{\s*([^}]+?)\s*\}",                                    # {door slam}
    r"<\s*([^>]+?)\s*>",                                      # <door slam>
]

SCENE_RE = re.compile(r"^\s*SCENE\s*(\d+)\b\s*(.*)$", re.IGNORECASE)
SPEAKER_RE = re.compile(r"^\s*([A-Za-z][A-Za-z .'&\-]{0,30}?)\s*(\([^)]*\))?\s*:\s*(.*)$")


def norm(s):
    s = s.lower()
    s = re.sub(r"\.(mp3|m4a|wav|aac|ogg|caf)$", "", s)
    s = re.sub(r"(sfx|sound|effect|fx)", " ", s)
    s = re.sub(r"[^a-z0-9]+", " ", s)
    out = []
    for w in s.split():  # collapse "ha ha ha" -> "ha"
        if not out or out[-1] != w:
            out.append(w)
    return " ".join(out)


def slug(s):
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-") or "sound"


def pretty_label(stem):
    return re.sub(r"[-_]+", " ", stem).strip().capitalize()


def pick_pattern(texts, forced):
    if forced:
        return re.compile(forced)
    best, best_n = None, 0
    for pat in CANDIDATE_PATTERNS:
        rx = re.compile(pat, re.IGNORECASE)
        n = sum(len(rx.findall(t)) for t in texts)
        if n > best_n:
            best, best_n = rx, n
    return best


def load_sounds(folder):
    sounds = []
    for name in sorted(os.listdir(folder), key=str.lower):
        stem, ext = os.path.splitext(name)
        if ext.lower() in AUDIO_EXT and not name.startswith("_"):
            sounds.append({"id": slug(stem), "label": pretty_label(stem), "file": f"sounds/{name}", "_norm": norm(stem)})
    return sounds


def match_sound(placeholder, sounds, aliases):
    key = placeholder.strip()
    if key in aliases:
        target = aliases[key]
        for s in sounds:
            if s["file"].endswith(target) or s["id"] == slug(os.path.splitext(target)[0]):
                return s, "alias"
    n = norm(key)
    for s in sounds:
        if n == s["_norm"]:
            return s, "exact"
    for s in sounds:
        if n and (n in s["_norm"] or s["_norm"] in n):
            return s, "contains"
    close = difflib.get_close_matches(n, [s["_norm"] for s in sounds], n=1, cutoff=0.6)
    if close:
        for s in sounds:
            if s["_norm"] == close[0]:
                return s, "fuzzy"
    return None, "none"


def last_words(text, k=8):
    words = [w for w in re.sub(r"\s+", " ", text).strip().split(" ") if w]
    if not words:
        return ""
    return ("..." if len(words) > k else "") + " ".join(words[-k:])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--script", required=True)
    ap.add_argument("--sounds", default="sounds")
    ap.add_argument("--title", default=None)
    ap.add_argument("--pattern", default=None, help="regex with one capture group for the sound name")
    ap.add_argument("--aliases", default="input/aliases.json")
    ap.add_argument("--out", default="cues.json")
    ap.add_argument("--sheet", default="CUE_SHEET.md")
    args = ap.parse_args()

    doc = Document(args.script)
    paras = [(p.text.strip(), p.style.name if p.style is not None else "") for p in doc.paragraphs]
    paras = [(t, st) for t, st in paras if t]

    title = args.title
    if title is None:
        for i, (t, st) in enumerate(paras):
            if st.startswith("Heading 1") or st == "Title":
                title = t
                paras.pop(i)
                break
    title = title or "Skit"

    rx = pick_pattern([t for t, _ in paras], args.pattern)
    if rx is None:
        sys.exit("No sound placeholders found. Pass --pattern with a regex that has one capture group.")

    aliases = {}
    if os.path.exists(args.aliases):
        with open(args.aliases, encoding="utf-8") as f:
            aliases = json.load(f)

    sounds = load_sounds(args.sounds)
    if not sounds:
        sys.exit(f"No audio files found in {args.sounds}")
    labels_path = os.path.join(os.path.dirname(args.aliases) or ".", "labels.json")
    if os.path.exists(labels_path):
        with open(labels_path, encoding="utf-8") as f:
            labels = json.load(f)
        for s in sounds:
            name = os.path.basename(s["file"])
            if name in labels:
                s["label"] = labels[name]
    sound_by_id = {s["id"]: s for s in sounds}

    setting = []
    scenes, lines, cues = [], [], []
    unmatched, used = [], set()
    last_item = None  # within the current scene: ("cue", cue) or ("text", speaker, text)

    for text, _style in paras:
        sm = SCENE_RE.match(text)
        if sm:
            number = int(sm.group(1))
            rest = sm.group(2).strip().rstrip("*").strip()
            extra, _, stitle = rest.partition(":") if ":" in rest else ("", "", rest)
            extra, stitle = extra.strip(), stitle.strip()
            if not stitle:
                stitle, extra = extra, ""
            if extra:
                stitle = f"{stitle} ({extra.lower()})"
            scenes.append({"n": len(scenes) + 1, "number": number, "title": stitle, "cueIds": [], "soundIds": []})
            last_item = None
            continue
        if not re.search(r"[A-Za-z0-9\[]", text):
            continue  # separators like ******
        if not scenes:
            setting.append(text)
            continue
        scene = scenes[-1]

        m = SPEAKER_RE.match(text)
        if m and not rx.match(text):
            speaker = m.group(1).strip().upper()
            note = (m.group(2) or "").strip()
            body = m.group(3).strip()
        else:
            speaker, note, body = "", "", text

        segments, pos, spoken = [], 0, ""
        for pm in rx.finditer(body):
            before = body[pos:pm.start()]
            if before.strip():
                segments.append({"type": "text", "text": before})
                spoken += before
                last_item = ("text", speaker, spoken, len(lines), len(segments) - 1)
            name = pm.group(1).strip()
            sound, how = match_sound(name, sounds, aliases)
            n = len(cues) + 1
            if last_item is None:
                trigger = {"kind": "scene_start", "speaker": "", "words": ""}
            elif last_item[0] == "cue":
                prev = last_item[1]
                plabel = sound_by_id[prev["soundId"]]["label"] if prev["soundId"] else prev["placeholder"]
                trigger = {"kind": "after_cue", "cueN": prev["n"], "label": plabel}
            else:
                trigger = {"kind": "after_words", "speaker": last_item[1], "words": last_words(last_item[2]),
                           "lineIndex": last_item[3], "segIndex": last_item[4]}
            cue = {"n": n, "placeholder": name, "soundId": sound["id"] if sound else None, "match": how,
                   "lineIndex": len(lines), "scene": scene["n"], "trigger": trigger}
            cues.append(cue)
            scene["cueIds"].append(n)
            if sound:
                used.add(sound["id"])
                if sound["id"] not in scene["soundIds"]:
                    scene["soundIds"].append(sound["id"])
            else:
                unmatched.append(cue)
            segments.append({"type": "cue", "n": n})
            last_item = ("cue", cue)
            pos = pm.end()
        rest = body[pos:]
        if rest.strip():
            segments.append({"type": "text", "text": rest})
            spoken += rest
            last_item = ("text", speaker, spoken, len(lines), len(segments) - 1)
        if not segments and not speaker:
            continue
        lines.append({"speaker": speaker, "note": note, "scene": scene["n"], "segments": segments})

    # scene-start cues: name who speaks first after the cue
    for c in cues:
        if c["trigger"]["kind"] == "scene_start":
            first = next((l["speaker"] for l in lines[c["lineIndex"] + 1:]
                          if l["scene"] == c["scene"] and l["speaker"]), "")
            c["trigger"]["speaker"] = first

    for s in scenes:
        idx = [i for i, l in enumerate(lines) if l["scene"] == s["n"]]
        s["firstLine"], s["lastLine"] = (idx[0], idx[-1]) if idx else (None, None)

    def trigger_text(c):
        t = c["trigger"]
        if t["kind"] == "scene_start":
            sc = scenes[c["scene"] - 1]
            return f"At the start of Scene {sc['number']}" + (f", before {t['speaker']} speaks" if t["speaker"] else "")
        if t["kind"] == "after_cue":
            return f"Right after cue {t['cueN']} ({t['label']})"
        who = t["speaker"] or "the stage action"
        return f"{who}: \"{t['words']}\""

    out = {
        "title": title,
        "setting": " ".join(setting),
        "scenes": scenes,
        "lines": lines,
        "cues": cues,
        "sounds": [{k: v for k, v in s.items() if not k.startswith("_")} for s in sounds],
    }
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)

    with open(args.sheet, "w", encoding="utf-8") as f:
        f.write(f"# Cue sheet: {title}\n\n")
        f.write(f"Placeholder pattern used: `{rx.pattern}`\n\n")
        f.write("| # | Sound file | Play when | How matched |\n|---|---|---|---|\n")
        for s in scenes:
            f.write(f"| | **Scene {s['number']}: {s['title']}** | {len(s['cueIds'])} cue(s) | |\n")
            for n in s["cueIds"]:
                c = cues[n - 1]
                snd = sound_by_id.get(c["soundId"])
                fname = snd["file"].split("/")[-1] if snd else f"**MISSING** ({c['placeholder']})"
                f.write(f"| {c['n']} | {fname} | {trigger_text(c)} | {c['match']} |\n")
        if unmatched:
            f.write("\n## Placeholders with no matching sound file\n\n")
            for c in unmatched:
                f.write(f"- Cue {c['n']}: `{c['placeholder']}`\n")
            f.write("\nFix by renaming the MP3, or add an entry to input/aliases.json.\n")
        unused = [s for s in sounds if s["id"] not in used]
        if unused:
            f.write("\n## Sound files never used by the script\n\n")
            for s in unused:
                f.write(f"- {s['file'].split('/')[-1]}\n")
        f.write(f"\n{len(cues)} cues, {len(scenes)} scenes, {len(lines)} script lines, {len(sounds)} sound files.\n")

    print(f"{len(cues)} cues, {len(scenes)} scenes, {len(lines)} lines, "
          f"{len(unmatched)} unmatched, {len([s for s in sounds if s['id'] not in used])} unused -> {args.out}, {args.sheet}")
    for c in unmatched:
        print(f"  WARNING cue {c['n']}: no sound for '{c['placeholder']}'")


if __name__ == "__main__":
    main()
