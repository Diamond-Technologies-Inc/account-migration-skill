#!/usr/bin/env python3
"""extract_export.py - Claude export splitter.

Reads a Claude personal-account data export, splits its conversations.json
into one transcript per conversation, and builds manifest CSVs that
downstream scripts (parse_allchats.py, reconstruct.py, reshape_and_extract.py)
consume.
"""

import argparse, csv, json, os, re, sys

def slugify(text, maxlen=60):
    text = (text or "").strip().lower()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_-]+", "-", text).strip("-")
    if not text:
        text = "untitled"
    return text[:maxlen].strip("-")

def short(uuid):
    return (uuid or "00000000")[:8]

def datestr(iso):
    if not iso:
        return "0000-00-00_0000"
    return iso[:10] + "_" + iso[11:13] + iso[14:16]

def truncate(s, n):
    s = s or ""
    s = s.replace("\n", " ").replace("\r", " ")
    return s if len(s) <= n else s[:n] + "..."

def render_block(block, include_thinking):
    if not isinstance(block, dict):
        return ""
    btype = block.get("type")
    if btype == "text":
        return block.get("text", "") or ""
    if btype == "thinking":
        if not include_thinking:
            return ""
        body = block.get("thinking", "") or block.get("text", "") or ""
        return ("<details>\n<summary>thinking</summary>\n\n"
                + body + "\n\n</details>")
    if btype == "tool_use":
        name = block.get("name", "?")
        inp = json.dumps(block.get("input", {}), ensure_ascii=False)
        return f"`[tool_use: {name}]` input: {truncate(inp, 500)}"
    if btype == "tool_result":
        content = block.get("content", "")
        if isinstance(content, (list, dict)):
            content = json.dumps(content, ensure_ascii=False)
        return f"`[tool_result]` {truncate(str(content), 800)}"
    if btype == "token_budget":
        return ""
    return f"`[{btype}]` " + truncate(json.dumps(block, ensure_ascii=False), 400)

def render_message(msg, include_thinking):
    sender = msg.get("sender", "?")
    ts = msg.get("created_at", "")
    lines = [f"### {sender}  ·  {ts}", ""]
    blocks = msg.get("content", []) or []
    rendered = []
    for b in blocks:
        r = render_block(b, include_thinking)
        if r:
            rendered.append(r)
    if not rendered and msg.get("text"):
        rendered.append(msg["text"])
    lines.append("\n\n".join(rendered) if rendered else "_(empty message)_")
    for att in msg.get("attachments", []) or []:
        fn = att.get("file_name") or "(unnamed)"
        ft = att.get("file_type", "")
        fsz = att.get("file_size", "")
        ec = att.get("extracted_content", "")
        lines.append("")
        lines.append(f"<details>\n<summary>attachment: {fn} "
                     f"({ft}, {fsz} bytes)</summary>\n\n{ec}\n\n</details>")
    for f in msg.get("files", []) or []:
        fn = f.get("file_name", "(unnamed)")
        fu = f.get("file_uuid", "")
        lines.append("")
        lines.append(f"> file attached: `{fn}` (uuid `{fu}`) - binary not included in export")
    lines.append("")
    return "\n".join(lines)

def render_transcript(conv, include_thinking):
    name = conv.get("name") or "(untitled)"
    head = [
        f"# {name}",
        "",
        f"- conversation uuid: `{conv.get('uuid','')}`",
        f"- created: {conv.get('created_at','')}",
        f"- updated: {conv.get('updated_at','')}",
        f"- messages: {len(conv.get('chat_messages', []))}",
    ]
    summ = (conv.get("summary") or "").strip()
    if summ:
        head.append(f"- summary: {summ}")
    head.append("")
    head.append("> Source: Claude personal-account data export.")
    head.append("")
    head.append("---")
    head.append("")
    body = [render_message(m, include_thinking) for m in conv.get("chat_messages", [])]
    return "\n".join(head) + "\n".join(body)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--export", required=True)
    ap.add_argument("--outdir", default="./extracted")
    ap.add_argument("--no-thinking", action="store_true")
    ap.add_argument("--no-raw", action="store_true")
    args = ap.parse_args()

    include_thinking = not args.no_thinking
    conv_path = os.path.join(args.export, "conversations.json")
    proj_dir = os.path.join(args.export, "projects")

    if not os.path.isfile(conv_path):
        sys.exit(f"conversations.json not found in {args.export}")

    tdir = os.path.join(args.outdir, "transcripts")
    rdir = os.path.join(args.outdir, "raw")
    os.makedirs(tdir, exist_ok=True)
    if not args.no_raw:
        os.makedirs(rdir, exist_ok=True)

    print("loading conversations.json ...")
    with open(conv_path, encoding="utf-8") as fh:
        conversations = json.load(fh)
    print(f"  {len(conversations)} conversations")

    conv_rows = []
    used_names = {}
    n_msgs = 0
    for conv in conversations:
        uuid = conv.get("uuid", "")
        msgs = conv.get("chat_messages", []) or []
        n_msgs += len(msgs)
        human = sum(1 for m in msgs if m.get("sender") == "human")
        asst = sum(1 for m in msgs if m.get("sender") == "assistant")
        att_names, file_names = [], []
        has_pks = False
        for m in msgs:
            for a in m.get("attachments", []) or []:
                if a.get("file_name"):
                    att_names.append(a["file_name"])
            for f in m.get("files", []) or []:
                if f.get("file_name"):
                    file_names.append(f["file_name"])
            for b in m.get("content", []) or []:
                if (isinstance(b, dict) and b.get("type") == "tool_use"
                        and b.get("name") == "project_knowledge_search"):
                    has_pks = True

        base = f"{datestr(conv.get('created_at'))}_{slugify(conv.get('name'))}_{short(uuid)}"
        if base in used_names:
            used_names[base] += 1
            base = f"{base}-{used_names[base]}"
        else:
            used_names[base] = 0

        with open(os.path.join(tdir, base + ".md"), "w", encoding="utf-8") as fh:
            fh.write(render_transcript(conv, include_thinking))
        if not args.no_raw:
            with open(os.path.join(rdir, uuid + ".json"), "w", encoding="utf-8") as fh:
                json.dump(conv, fh, ensure_ascii=False, indent=2)

        conv_rows.append({
            "uuid": uuid,
            "name": conv.get("name", ""),
            "created_at": conv.get("created_at", ""),
            "updated_at": conv.get("updated_at", ""),
            "messages": len(msgs),
            "human_msgs": human,
            "assistant_msgs": asst,
            "has_attachments": "yes" if att_names else "",
            "has_files": "yes" if file_names else "",
            "uses_project_knowledge_search": "yes" if has_pks else "",
            "attachment_names": "; ".join(sorted(set(att_names))),
            "file_names": "; ".join(sorted(set(file_names))),
            "summary": truncate(conv.get("summary", ""), 300),
            "transcript_file": "transcripts/" + base + ".md",
            "project_assignment": "",
        })

    conv_rows.sort(key=lambda r: (r["created_at"] or ""))
    cm_path = os.path.join(args.outdir, "conversations_manifest.csv")
    with open(cm_path, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(conv_rows[0].keys()))
        w.writeheader()
        w.writerows(conv_rows)

    proj_rows = []
    if os.path.isdir(proj_dir):
        for pf in sorted(os.listdir(proj_dir)):
            if not pf.endswith(".json"):
                continue
            path = os.path.join(proj_dir, pf)
            if os.path.getsize(path) == 0:
                proj_rows.append({"file": pf, "uuid": "", "name": "(empty file)",
                                  "is_starter": "", "is_private": "",
                                  "instructions_chars": "", "doc_count": "",
                                  "doc_chars": "", "doc_filenames": "",
                                  "description": ""})
                continue
            d = json.load(open(path, encoding="utf-8"))
            docs = d.get("docs", []) or []
            proj_rows.append({
                "file": pf,
                "uuid": d.get("uuid", ""),
                "name": d.get("name", ""),
                "is_starter": d.get("is_starter_project", ""),
                "is_private": d.get("is_private", ""),
                "instructions_chars": len(d.get("prompt_template", "") or ""),
                "doc_count": len(docs),
                "doc_chars": sum(len(x.get("content", "") or "") for x in docs),
                "doc_filenames": "; ".join(x.get("filename", "") for x in docs),
                "description": truncate(d.get("description", ""), 300),
            })
    pm_path = os.path.join(args.outdir, "projects_manifest.csv")
    if proj_rows:
        with open(pm_path, "w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=list(proj_rows[0].keys()))
            w.writeheader()
            w.writerows(proj_rows)

    empty = sum(1 for r in conv_rows if r["messages"] == 0)
    with_att = sum(1 for r in conv_rows if r["has_attachments"])
    with_files = sum(1 for r in conv_rows if r["has_files"])
    with_pks = sum(1 for r in conv_rows if r["uses_project_knowledge_search"])
    lines = [
        "CLAUDE EXPORT EXTRACTION - SUMMARY",
        "=" * 40,
        f"conversations          : {len(conv_rows)}",
        f"  with messages        : {len(conv_rows) - empty}",
        f"  empty                : {empty}",
        f"total messages         : {n_msgs}",
        f"  with attachments     : {with_att}",
        f"  with files           : {with_files}",
        f"  uses project_knowledge_search : {with_pks}",
        f"projects               : {len(proj_rows)}",
        "",
        f"transcripts written to : {tdir}",
        f"raw json written to    : {'(skipped)' if args.no_raw else rdir}",
        f"conversation manifest  : {cm_path}",
        f"project manifest       : {pm_path}",
    ]
    summary = "\n".join(lines)
    with open(os.path.join(args.outdir, "SUMMARY.txt"), "w", encoding="utf-8") as fh:
        fh.write(summary + "\n")
    print()
    print(summary)


if __name__ == "__main__":
    main()
