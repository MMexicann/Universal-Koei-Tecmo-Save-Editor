"""Offline visualization of immutable display snapshots, without save access.

Reports contain only the supplied presentation data. They never retain source
paths, save bytes, backend objects or editable controls. Comparisons are selected
records in one snapshot and do not infer completion or calculate unlike totals.
"""

import html
import json
from pathlib import Path
import re

from koei_editor.shared.copy_storage import atomic_new


PAGE_SIZE = 24
MAX_REPORT_BYTES = 64 * 1024 * 1024


def render_report(dashboard, *, section_ids=None, comparison_ids=(), theme="auto"):
    """Return a self-contained HTML report of selected sections and records.

    Only ``DashboardMetric.fraction`` authorizes a chart. No numeric display
    string, storage ceiling, missing value or record count becomes a percentage.
    """
    if theme not in ("auto", "Light", "Dark"):
        raise ValueError("Choose Auto, Light or Dark report appearance.")
    selected = None if section_ids is None else set(section_ids)
    known = {section.id for section in dashboard.sections}
    if selected is not None and selected - known:
        raise ValueError("The report selection includes an unknown section.")
    sections, cards = [], []
    for section in dashboard.sections:
        if selected is not None and section.id not in selected:
            continue
        sections.append(dict(id=section.id, title=section.title, note=section.note,
                             count=len(section.cards)))
        for card in section.cards:
            cards.append(dict(id=card.id, title=card.title, subtitle=card.subtitle,
                              section=section.id, sectionTitle=section.title,
                              search=card.search_text,
                              metrics=[dict(id=m.id, label=m.label, value=m.value,
                                            unit=m.unit, note=m.note,
                                            fraction=m.fraction,
                                            atTarget=m.fraction is not None and m.current == m.total,
                                            atZero=m.fraction is not None and m.current == 0,
                                            current=str(m.current) if m.fraction is not None else None,
                                            total=str(m.total) if m.fraction is not None else None)
                                       for m in card.metrics]))
    comparisons = tuple(dict.fromkeys(comparison_ids))
    if len(comparisons) > 4 or set(comparisons) - {c["id"] for c in cards}:
        raise ValueError("Select up to four comparison records from included sections.")
    data = dict(sections=sections, cards=cards, comparisons=comparisons,
                pageSize=PAGE_SIZE, theme=theme)
    # JSON is inert data, but HTML's script parser recognizes closing tags even
    # inside JSON strings. Escape all HTML-significant characters before embedding.
    encoded = json.dumps(data, ensure_ascii=True, allow_nan=False)
    for char, replacement in (("&", "\\u0026"), ("<", "\\u003c"), (">", "\\u003e")):
        encoded = encoded.replace(char, replacement)
    parts = {"TITLE": html.escape(dashboard.title), "NOTE": html.escape(dashboard.note),
             "STYLE": _STYLE, "SCRIPT": _SCRIPT, "DATA": encoded}
    # Substitute once: presentation strings that resemble a template token
    # must remain literal display text rather than triggering another expansion.
    result = re.sub(r"__(TITLE|NOTE|STYLE|SCRIPT|DATA)__", lambda m: parts[m[1]], _HTML)
    if len(result.encode("utf-8")) > MAX_REPORT_BYTES:
        raise ValueError("Report exceeds 64 MiB; include fewer sections.")
    return result


def export_report(dashboard, destination, **options):
    """Create a new HTML report using the existing atomic copy helper."""
    destination = Path(destination)
    if destination.suffix.lower() not in (".html", ".htm"):
        raise ValueError("Choose a new .html report destination.")
    data = render_report(dashboard, **options).encode("utf-8")
    result = atomic_new(data, destination)
    with result.open("rb") as stream:
        if stream.read(len(data) + 1) != data:
            raise OSError("Report failed actual read-back verification.")
    return result


def show_report_dialog(master, dashboard, theme=None):
    """Choose included sections and up to four records, then export HTML."""
    import tkinter as tk
    from tkinter import filedialog, messagebox, ttk
    from koei_editor.shared.appearance import THEMES

    window = tk.Toplevel(master)
    palette = theme if isinstance(theme, dict) else THEMES.get(theme, THEMES["Light"])
    window.configure(background=palette["background"])
    window.title("Progression HTML report")
    window.geometry("720x600")
    window.minsize(520, 440)
    window.transient(master.winfo_toplevel())
    window.columnconfigure(0, weight=1)
    window.rowconfigure(4, weight=1)
    ttk.Label(window, text="Create a progression report", font=("Segoe UI", 16, "bold")).grid(
        row=0, column=0, sticky="w", padx=20, pady=(18, 6))
    ttk.Label(window, text="Opened snapshot only. Includes display values and evidence notes.\n"
              "The standalone report works offline and supports search, charts and both themes.",
              wraplength=650).grid(row=1, column=0, sticky="w", padx=20)
    ttk.Label(window, text="Include sections (Ctrl / Shift to select)").grid(
        row=2, column=0, sticky="w", padx=20, pady=(14, 4))
    section_list = tk.Listbox(window, selectmode="extended", exportselection=False, height=5)
    section_list.grid(row=3, column=0, sticky="ew", padx=20)
    for section in dashboard.sections:
        section_list.insert("end", f"{section.title}  ·  {len(section.cards):,} records")
    section_list.select_set(0, "end")
    frame = ttk.LabelFrame(window, text="Optional record comparison · select up to four", padding=8)
    frame.grid(row=4, column=0, sticky="nsew", padx=20, pady=14)
    frame.rowconfigure(1, weight=1)
    frame.columnconfigure(0, weight=1)
    query = tk.StringVar(window)
    ttk.Entry(frame, textvariable=query).grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 6))
    record_list = tk.Listbox(frame, selectmode="extended", exportselection=False)
    for widget in (section_list, record_list):
        widget.configure(background=palette["surface"], foreground=palette["text"],
                         selectbackground=palette["accent"], selectforeground="#ffffff",
                         highlightbackground=palette["border"], highlightcolor=palette["tab_text"])
    record_list.grid(row=1, column=0, sticky="nsew")
    scroll = ttk.Scrollbar(frame, command=record_list.yview)
    scroll.grid(row=1, column=1, sticky="ns")
    record_list.configure(yscrollcommand=scroll.set)
    all_records = [(s, c) for s in dashboard.sections for c in s.cards]
    visible, picked = [], set()

    def remember(_event=None):
        picked.difference_update(c.id for _s, c in visible)
        picked.update(visible[i][1].id for i in record_list.curselection())

    def filter_records(*_args):
        remember()
        include = {dashboard.sections[i].id for i in section_list.curselection()}
        tokens = query.get().casefold().split()
        visible[:] = [(s, c) for s, c in all_records if s.id in include and
                      all(t in (c.title + " " + c.subtitle + " " + c.search_text).casefold() for t in tokens)]
        picked.intersection_update(c.id for s, c in all_records if s.id in include)
        record_list.delete(0, "end")
        for i, (section, card) in enumerate(visible):
            record_list.insert("end", f"{section.title} / {card.title}")
            if card.id in picked:
                record_list.select_set(i)

    record_list.bind("<<ListboxSelect>>", remember)
    section_list.bind("<<ListboxSelect>>", filter_records)
    query.trace_add("write", filter_records)
    filter_records()
    actions = ttk.Frame(window, padding=(20, 0, 20, 18))
    actions.grid(row=5, column=0, sticky="ew")
    actions.columnconfigure(1, weight=1)
    initial_theme = theme if isinstance(theme, str) and theme in THEMES else next(
        (name for name, colors in THEMES.items() if colors == theme), "Auto")
    appearance = tk.StringVar(window, initial_theme)
    ttk.Combobox(actions, textvariable=appearance, values=("Auto", "Light", "Dark"),
                 state="readonly", width=8).grid(row=0, column=0)

    def save():
        remember()
        sections = tuple(dashboard.sections[i].id for i in section_list.curselection())
        if not sections or len(picked) > 4:
            messagebox.showerror("Report selection", "Include a section and select at most four comparison records.", parent=window)
            return
        path = filedialog.asksaveasfilename(parent=window, title="Save a new HTML report",
                    defaultextension=".html", filetypes=[("HTML report", "*.html")],
                    initialfile="ProgressionReport.html")
        if not path:
            return
        try:
            export_report(dashboard, path, section_ids=sections,
                          comparison_ids=tuple(c.id for _s, c in all_records if c.id in picked),
                          theme=appearance.get().lower() if appearance.get() == "Auto" else appearance.get())
        except (ValueError, OSError) as error:
            messagebox.showerror("Report could not be saved", str(error), parent=window)
            return
        messagebox.showinfo("Report saved", "The standalone HTML report is ready to open in a browser.", parent=window)
        window.destroy()

    ttk.Button(actions, text="Cancel", command=window.destroy).grid(row=0, column=2, padx=8)
    ttk.Button(actions, text="Save HTML report…", command=save).grid(row=0, column=3)
    return window


_HTML = '''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; base-uri 'none'; form-action 'none'">
<title>__TITLE__ · Progression report</title><style>__STYLE__</style></head>
<body><main><header><div><p class="eyebrow">PROGRESSION ATLAS <span>OPENED SNAPSHOT · READ ONLY</span></p>
<h1>__TITLE__</h1><p class="intro">__NOTE__</p></div><label>Appearance <select id="theme" aria-label="Appearance"><option value="auto">System</option><option>Light</option><option>Dark</option></select></label></header>
<section id="summary" class="summary" aria-label="Snapshot overview"></section>
<p class="scope">Charts show explicitly mapped ranges only. Each range describes its own metric; it is not an overall game completion score. Missing ranges remain uncharted.</p>
<section class="controls" aria-label="Report filters"><label class="search">Search records<input id="query" type="search" placeholder="Character, weapon, attribute, resource…"></label>
<label>Section<select id="section"><option value="">All included sections</option></select></label>
<label>Range status<select id="status"><option value="">All records</option><option value="ranged">Has mapped ranges</option><option value="complete">Has a full mapped range</option><option value="partial">Has an unfinished mapped range</option><option value="unknown">No mapped range</option></select></label>
<label>Sort<select id="sort"><option value="source">Source order</option><option value="name">Name A–Z</option><option value="ranges">Mapped range count</option></select></label>
<button id="reset">Reset filters</button></section>
<p id="context" class="scope"></p><div class="resultbar"><h2 id="results" aria-live="polite"></h2><p>Select up to four records to compare below.</p></div>
<section id="cards" class="cards" aria-label="Progression records"></section>
<nav class="pager" aria-label="Record pages"><button id="previous">← Previous</button><span id="page" aria-live="polite"></span><button id="next">Next →</button></nav>
<section id="comparison" class="comparison" aria-label="Selected record comparison"></section>
<footer>Standalone display report · No save bytes or source paths are added by the report generator. Values reflect the opened snapshot; pending edits are excluded. Only included sections are embedded.</footer>
<noscript>Enable JavaScript to browse the embedded snapshot. This report uses no network services.</noscript>
</main><script id="snapshot" type="application/json">__DATA__</script><script>__SCRIPT__</script></body></html>'''


_STYLE = '''
:root{color-scheme:light;--bg:#eef2f7;--surface:#fff;--soft:#f3f6fb;--text:#18253b;--muted:#53647c;--line:#d8e1ed;--accent:#315cd8;--tint:#e8efff;--green:#197568;--shadow:0 8px 30px #1e385309}
:root[data-theme=Dark]{color-scheme:dark;--bg:#0d1422;--surface:#172236;--soft:#1e2d44;--text:#e9eff9;--muted:#a8b8cf;--line:#30435e;--accent:#92b2ff;--tint:#253e65;--green:#77d6bd;--shadow:0 8px 30px #0002}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--text);font:15px/1.5 system-ui,-apple-system,Segoe UI,sans-serif}main{max-width:1560px;margin:auto;padding:42px 36px}header{display:flex;justify-content:space-between;gap:28px;align-items:start}header>div{max-width:1080px}h1{font-size:clamp(26px,3vw,42px);letter-spacing:-1.3px;line-height:1.15;margin:14px 0}h2{font-size:20px;letter-spacing:-.4px}.eyebrow{font-size:11px;font-weight:750;letter-spacing:2px;color:var(--accent)}.eyebrow span{display:inline-block;margin-left:18px;letter-spacing:1px;color:var(--muted)}.intro,.scope,footer{color:var(--muted);white-space:pre-wrap}.intro{max-width:1000px}.scope{font-size:12px}.summary{display:grid;grid-template-columns:repeat(auto-fit,minmax(175px,1fr));gap:12px;margin:26px 0 12px}.stat{padding:18px 22px;border:1px solid var(--line);background:var(--surface);border-radius:16px}.stat strong{display:block;font-size:29px;font-weight:750;letter-spacing:-1px}.stat span{color:var(--muted);font-size:12px}.controls{display:flex;flex-wrap:wrap;gap:12px;align-items:end;padding:18px;background:var(--surface);border:1px solid var(--line);border-radius:16px;margin-top:24px}label{display:flex;flex-direction:column;gap:6px;font-size:12px;color:var(--muted);font-weight:600}.search{flex:1;min-width:220px}input,select,button{font:inherit;color:var(--text);background:var(--soft);border:1px solid var(--line);border-radius:9px;padding:10px 12px}input{width:100%}button{cursor:pointer;font-size:12px;font-weight:650}button:hover{border-color:var(--accent);color:var(--accent)}button:disabled{opacity:.4;cursor:default}input:focus-visible,select:focus-visible,button:focus-visible,summary:focus-visible{outline:3px solid var(--accent);outline-offset:3px}.resultbar{display:flex;align-items:center;justify-content:space-between;gap:16px}.resultbar p{font-size:12px;color:var(--muted)}.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,300px),1fr));gap:18px}.card{background:var(--surface);border:1px solid var(--line);border-radius:18px;padding:22px;box-shadow:var(--shadow);overflow:hidden;min-width:0;position:relative}.card.picked{border-color:var(--accent);box-shadow:0 0 0 1px var(--accent)}.cardhead{display:flex;gap:13px;align-items:center}.avatar{display:grid;place-items:center;flex-shrink:0;width:46px;height:46px;background:var(--tint);color:var(--accent);font-size:18px;font-weight:750;border-radius:14px}.card h3{font-size:18px;line-height:1.25;margin:4px 0;overflow-wrap:anywhere}.kicker{font-size:10px;text-transform:uppercase;letter-spacing:1px;color:var(--accent);font-weight:700}.subtitle{font-size:12px;color:var(--muted);white-space:pre-wrap;overflow-wrap:anywhere}.metrics{display:grid;grid-template-columns:1fr 1fr;gap:9px;margin:18px 0}.metric{background:var(--soft);border-radius:10px;padding:11px;min-width:0}.metric.ranged{grid-column:1/-1}.metric-label{display:block;font-size:11px;color:var(--muted);overflow-wrap:anywhere}.metric-value{display:block;font-size:18px;font-weight:700;overflow-wrap:anywhere}.track{height:7px;background:var(--line);border-radius:5px;overflow:hidden;margin:9px 0 5px}.fill{height:100%;background:var(--accent);border-radius:5px}.range-caption{display:flex;justify-content:space-between;gap:8px;font-size:11px;color:var(--muted)}.note{font-size:11px;color:var(--muted);white-space:pre-wrap;overflow-wrap:anywhere}details{margin:12px 0}summary{cursor:pointer;color:var(--accent);font-size:12px;font-weight:650}details .metric{margin:8px 0}.card>button{width:100%;margin-top:8px;color:var(--accent);background:var(--tint)}.pager{display:flex;align-items:center;justify-content:center;gap:18px;margin:25px 0;color:var(--muted);font-size:12px}.comparison{margin-top:36px;border-top:1px solid var(--line);padding-top:20px}.table-scroll{overflow:auto;border:1px solid var(--line);border-radius:14px}table{border-collapse:collapse;width:100%;font-size:13px;background:var(--surface)}th,td{text-align:left;padding:13px 16px;vertical-align:top;border-bottom:1px solid var(--line);min-width:155px;white-space:pre-wrap;overflow-wrap:anywhere}th{background:var(--soft);font-weight:650}th:first-child{min-width:190px}td .note{display:block;margin-top:4px}.empty{grid-column:1/-1;text-align:center;padding:50px;color:var(--muted);border:1px dashed var(--line);border-radius:16px}footer{border-top:1px solid var(--line);padding-top:20px;margin-top:36px;font-size:11px}
@media(max-width:680px){main{padding:22px 16px}header{flex-direction:column;gap:8px}.eyebrow span{margin:8px 0 0;display:block}.controls>label{flex:1;min-width:140px}.resultbar{display:block}.summary{grid-template-columns:1fr 1fr}.stat{padding:14px}.stat strong{font-size:25px}header>label{width:100%}.card{padding:18px}}
@media print{body{background:white;color:black}main{padding:0}header>label,.controls,.pager,button{display:none!important}.cards{grid-template-columns:1fr 1fr}.card{break-inside:avoid;box-shadow:none}details{display:block}footer{color:#444}.table-scroll{overflow:visible}.comparison{break-before:page}*{print-color-adjust:exact}}
'''


_SCRIPT = r'''
"use strict";
const data=JSON.parse(document.getElementById("snapshot").textContent);
const $=id=>document.getElementById(id), el=(tag,text,cls)=>{const n=document.createElement(tag);if(text!==undefined)n.textContent=text;if(cls)n.className=cls;return n};
const state={page:0,filtered:[],picked:new Set(data.comparisons)};
const media=window.matchMedia("(prefers-color-scheme: dark)");
function applyTheme(){const value=$("theme").value;document.documentElement.dataset.theme=value==="auto"?(media.matches?"Dark":"Light"):value}
$("theme").value=data.theme;$("theme").addEventListener("change",applyTheme);media.addEventListener("change",applyTheme);applyTheme();
const value=m=>m.value+(m.unit?" "+m.unit:"");
function percent(m){if(m.atTarget)return "100%";if(m.atZero)return "0%";const n=(m.fraction*100).toFixed(2);return n==="100.00"?"<100%":n==="0.00"?"<0.01%":n.replace(/\.?0+$/,"")+"%"}
function metric(m){const n=el("div",undefined,"metric"+(m.fraction!==null?" ranged":""));n.append(el("span",m.label,"metric-label"),el("strong",value(m),"metric-value"));if(m.fraction!==null){const track=el("div",undefined,"track");track.setAttribute("role","meter");track.setAttribute("aria-label",m.label);track.setAttribute("aria-valuemin","0");track.setAttribute("aria-valuemax","100");track.setAttribute("aria-valuenow",String(m.fraction*100));track.setAttribute("aria-valuetext",m.current+" / "+m.total);const fill=el("div",undefined,"fill");fill.style.width=(m.fraction*100)+"%";track.append(fill);const caption=el("div",undefined,"range-caption");caption.append(el("span",m.current+" / "+m.total),el("strong",percent(m)));n.append(track,caption)}if(m.note)n.append(el("p",m.note,"note"));return n}
const rangeCount=data.cards.reduce((n,c)=>n+c.metrics.filter(m=>m.fraction!==null).length,0);
for(const [number,label] of [[data.cards.length,"Included records"],[data.sections.length,"Included sections"],[data.cards.reduce((n,c)=>n+c.metrics.length,0),"Mapped display values"],[rangeCount,"Explicit metric ranges"]]){const n=el("div",undefined,"stat");n.append(el("strong",number.toLocaleString()),el("span",label));$("summary").append(n)}
for(const s of data.sections){const option=el("option",s.title+" ("+s.count.toLocaleString()+")");option.value=s.id;$("section").append(option)}
function update(){const tokens=$("query").value.toLocaleLowerCase().split(/\s+/).filter(Boolean),section=$("section").value,status=$("status").value;state.filtered=data.cards.filter(c=>{if(section&&c.section!==section)return false;const hay=[c.title,c.subtitle,c.search,...c.metrics.map(m=>m.label+" "+value(m))].join(" ").toLocaleLowerCase();if(!tokens.every(t=>hay.includes(t)))return false;const ranges=c.metrics.filter(m=>m.fraction!==null);return !status||(status==="ranged"&&ranges.length>0)||(status==="complete"&&ranges.some(m=>m.atTarget))||(status==="partial"&&ranges.some(m=>!m.atTarget))||(status==="unknown"&&!ranges.length)});if($("sort").value==="name")state.filtered.sort((a,b)=>a.title.localeCompare(b.title));if($("sort").value==="ranges")state.filtered.sort((a,b)=>b.metrics.filter(m=>m.fraction!==null).length-a.metrics.filter(m=>m.fraction!==null).length);state.page=0;$("context").textContent=(data.sections.find(s=>s.id===section)||{}).note||"";render()}
function card(c){const n=el("article",undefined,"card"+(state.picked.has(c.id)?" picked":""));const head=el("div",undefined,"cardhead"),avatar=el("div",c.title.slice(0,1).toLocaleUpperCase(),"avatar"),title=el("div");avatar.setAttribute("aria-hidden","true");title.append(el("span",c.sectionTitle,"kicker"),el("h3",c.title));head.append(avatar,title);n.append(head);if(c.subtitle)n.append(el("p",c.subtitle,"subtitle"));const metrics=el("div",undefined,"metrics");c.metrics.slice(0,6).forEach(m=>metrics.append(metric(m)));n.append(metrics);if(c.metrics.length>6){const details=el("details");details.append(el("summary","Explore all "+c.metrics.length+" mapped values"));c.metrics.slice(6).forEach(m=>details.append(metric(m)));n.append(details)}const pick=el("button",state.picked.has(c.id)?"Remove from comparison":"+ Compare record");pick.setAttribute("aria-pressed",String(state.picked.has(c.id)));pick.disabled=!state.picked.has(c.id)&&state.picked.size>=4;pick.addEventListener("click",()=>{state.picked.has(c.id)?state.picked.delete(c.id):state.picked.add(c.id);render();renderComparison()});n.append(pick);return n}
function render(){const start=state.page*data.pageSize,total=state.filtered.length;$("cards").replaceChildren();state.filtered.slice(start,start+data.pageSize).forEach(c=>$("cards").append(card(c)));if(!total)$("cards").append(el("p","No matching records. Try another section or reset the filters.","empty"));$("results").textContent=total.toLocaleString()+" matching records";$("page").textContent=total?"Showing "+(start+1)+"–"+Math.min(start+data.pageSize,total)+" of "+total.toLocaleString():"No records";$("previous").disabled=state.page===0;$("next").disabled=start+data.pageSize>=total}
function renderComparison(){const box=$("comparison");box.replaceChildren(el("h2","Selected record comparison"));const selected=data.cards.filter(c=>state.picked.has(c.id));if(!selected.length){box.append(el("p","Choose up to four character, equipment or resource records. Values are shown side by side without inferred totals or completion.","scope"));return}box.append(el("p","Same-label values are shown as supplied by each record. Missing values are labelled explicitly; different game mechanics are not combined.","scope"));const scroll=el("div",undefined,"table-scroll"),table=el("table"),head=el("thead"),header=el("tr");header.append(el("th","Mapped value"));for(const c of selected){const th=el("th",c.title);th.scope="col";const remove=el("button","Remove");remove.setAttribute("aria-label","Remove "+c.title+" from comparison");remove.addEventListener("click",()=>{state.picked.delete(c.id);render();renderComparison()});th.append(el("p",c.sectionTitle,"note"),remove);header.append(th)}head.append(header);const body=el("tbody"),keys=new Map();for(const c of selected)for(const m of c.metrics)keys.set(JSON.stringify([m.label,m.unit]),[m.label,m.unit]);for(const [key,[label,unit]] of keys){const row=el("tr"),th=el("th",label+(unit?" ("+unit+")":""));th.scope="row";row.append(th);for(const c of selected){const cell=el("td"),matches=c.metrics.filter(m=>JSON.stringify([m.label,m.unit])===key);if(!matches.length)cell.textContent="Not mapped for this record";for(const m of matches){cell.append(el("div",value(m)));if(m.fraction!==null)cell.append(el("span",m.current+" / "+m.total+" · "+percent(m),"note"));if(m.note)cell.append(el("span",m.note,"note"))}row.append(cell)}body.append(row)}table.append(head,body);scroll.append(table);box.append(scroll)}
let timer;$("query").addEventListener("input",()=>{clearTimeout(timer);timer=setTimeout(update,100)});for(const id of ["section","status","sort"])$(id).addEventListener("change",update);$("reset").addEventListener("click",()=>{for(const id of ["query","section","status"])$(id).value="";$("sort").value="source";clearTimeout(timer);update()});$("previous").addEventListener("click",()=>{state.page--;render()});$("next").addEventListener("click",()=>{state.page++;render()});update();renderComparison();
'''
