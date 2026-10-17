"""Retained copied-save comparison; workers never access Tk objects."""
from pathlib import Path
import queue
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from koei_editor.shared import save_comparison as backend
from koei_editor.shared.appearance import ui_font
from koei_editor.shared.scrollable_panel import ScrollablePanel

STATUS_LABELS = {'value_changed': 'Value changed', 'definition_changed': 'Record definition changed',
                 'available_in_first': 'Available in first', 'available_in_second': 'Available in second'}


class ComparisonWorkspace:
    def __init__(self, root, parent, *, scrollable=True):
        self.root, self.frame = root, ttk.Frame(parent, padding=(28, 16))
        self.paging = ttk.Frame(self.frame)
        self.paging.pack(side='bottom', fill='x', pady=(8, 0))
        # Research Lab supplies its own viewport around this entire form.
        self._comparison_viewport = ScrollablePanel(self.frame) if scrollable else None
        if self._comparison_viewport is not None:
            self.viewport = self._comparison_viewport
            self.viewport.frame.pack(fill='both', expand=True)
        body = self._comparison_viewport.content if scrollable else self.frame
        self._comparison_body = body
        self.busy, self.prepared, self._revision = False, None, 0
        self.page, self.page_size = 0, 250
        self._results = queue.SimpleQueue()
        self._games = {game.title + ' · ' + game.subtitle + ' [' + game.platform + ']': game.id
                       for game in backend.COMPARABLE_GAMES}
        ttk.Label(body, text='COMPARE SAVES', font=(ui_font(root), 23, 'bold')).pack(anchor='w')
        ttk.Label(body, text='See what changed between two copies of the same game/platform.',
                  style='Muted.TLabel', wraplength=980).pack(anchor='w', pady=(4, 14))
        form = ttk.Frame(body); form.pack(fill='x'); form.columnconfigure(1, weight=1)
        self.game = tk.StringVar(root, value=next(iter(self._games)))
        self.first, self.second = tk.StringVar(root), tk.StringVar(root)
        self.controls=[]
        ttk.Label(form, text='Game and platform').grid(row=0, column=0, sticky='w', padx=(0,14))
        self.selector = ttk.Combobox(form, textvariable=self.game, values=tuple(self._games), state='readonly',width=1)
        self.selector.grid(row=0, column=1, columnspan=2, sticky='ew', pady=8); self.controls.append(self.selector)
        for row, label, variable in ((1,'First copy',self.first),(2,'Second copy',self.second)):
            ttk.Label(form,text=label).grid(row=row,column=0,sticky='w',padx=(0,14))
            entry=ttk.Entry(form,textvariable=variable,width=1);entry.grid(row=row,column=1,sticky='ew',pady=8)
            button=ttk.Button(form,text='Browse…',command=lambda v=variable:self.browse(v))
            button.grid(row=row,column=2,padx=(10,0));self.controls.extend((entry,button))
        ttk.Label(body,text='Keep each copy’s required original console metadata beside it. '
                  'The comparison reads mapped fields and counts other payload differences.',
                  style='Muted.TLabel',wraplength=980).pack(anchor='w',pady=(8,12))
        actions=ttk.Frame(body);actions.pack(fill='x')
        self.compare_button=ttk.Button(actions,text='Compare copies',command=self.compare)
        self.compare_button.pack(side='left');self.controls.append(self.compare_button)
        self.export_button=ttk.Button(actions,text='Export report…',command=self.export,state='disabled')
        self.export_button.pack(side='left',padx=10)
        self.status=tk.StringVar(root,value='Choose two separate copied saves and their exact profile.')
        ttk.Label(body,textvariable=self.status,wraplength=980).pack(anchor='w',pady=(14,8))
        search=ttk.Frame(body);search.pack(fill='x',pady=(4,8))
        ttk.Label(search,text='Find differences').pack(side='left',padx=(0,12))
        self.search=tk.StringVar(root);ttk.Entry(search,textvariable=self.search,width=1).pack(side='left',fill='x',expand=True)
        self.filter=tk.StringVar(root,value='All differences')
        ttk.Combobox(search,textvariable=self.filter,values=('All differences','Value changed','Record definition changed','Available in first','Available in second'),state='readonly',width=24).pack(side='left',padx=10)
        table=ttk.Frame(body);table.pack(fill='both',expand=True)
        self.table=ttk.Treeview(table,columns=('record','field','first','second','status'),show='headings',height=15)
        for key,title,width in (('record','Record',200),('field','Field',240),('first','First copy',130),
                                ('second','Second copy',130),('status','Difference',200)):
            self.table.heading(key,text=title);self.table.column(key,width=width,minwidth=80)
        scrollbar=ttk.Scrollbar(table,orient='vertical',command=self.table.yview)
        horizontal=ttk.Scrollbar(table,orient='horizontal',command=self.table.xview)
        self.table.configure(yscrollcommand=scrollbar.set,xscrollcommand=horizontal.set)
        scrollbar.pack(side='right',fill='y');horizontal.pack(side='bottom',fill='x')
        self.table.pack(fill='both',expand=True)
        ttk.Label(body,text='Fields align by this profile’s field IDs. Conditional records may differ. '
                  'A comparison report does not authorize additional gameplay edits.',
                  style='Muted.TLabel',wraplength=980).pack(anchor='w',pady=(12,0))
        for variable in (self.game,self.first,self.second):variable.trace_add('write',self.invalidate)
        for variable in (self.search,self.filter):variable.trace_add('write',self.refilter)
        paging=self.paging
        self.previous=ttk.Button(paging,text='Previous',command=lambda:self.change_page(-1),state='disabled');self.previous.grid(row=0,column=0,sticky='w')
        self.next=ttk.Button(paging,text='Next',command=lambda:self.change_page(1),state='disabled');self.next.grid(row=0,column=1,sticky='w',padx=10)
        self.page_info=tk.StringVar(root,value='No comparison yet');ttk.Label(paging,textvariable=self.page_info,wraplength=700).grid(row=1,column=0,columnspan=3,sticky='w')

        body.bind('<Configure>',self._resize_guidance,add='+')

    def _resize_guidance(self, event):
        for widget in self._comparison_body.winfo_children():
            if isinstance(widget, ttk.Label):
                widget.configure(wraplength=max(1, event.width - 8))


    def apply_theme(self, palette):
        if self._comparison_viewport is not None:
            self._comparison_viewport.apply_theme(palette)

    def invalidate(self,*_args):
        self._revision+=1;self.prepared=None;self.page=0;self.export_button.configure(state='disabled');self.refresh()
        if not self.busy:self.status.set('Selections changed. Compare the copies again.')

    def browse(self,variable):
        game_id=self._games.get(self.game.get())
        if not game_id:return
        extension=backend.adapter_for(game_id).extension
        path=filedialog.askopenfilename(parent=self.root,title='Choose a separate save copy',
             filetypes=[('Game save','*'+extension),('All files','*')] if extension else [('All files','*')])
        if path:variable.set(path)

    def refilter(self,*_args):
        self.page=0;self.refresh()

    def change_page(self,direction):
        self.page=max(0,self.page+direction);self.refresh()

    def refresh(self):
        self.table.delete(*self.table.get_children())
        rows=() if self.prepared is None else self.prepared.rows
        query=self.search.get().casefold().strip();filtered=[]
        for index,row in enumerate(rows):
            status=STATUS_LABELS[row.status]
            if self.filter.get()!='All differences' and self.filter.get()!=status:continue
            values=(row.record,row.label,'Unavailable' if row.left is None else str(row.left),
                    'Unavailable' if row.right is None else str(row.right),status)
            if query and query not in (' '.join(values)+' '+row.group+' '+row.id).casefold():continue
            filtered.append((index,values))
        self.page=min(self.page,max(0,(len(filtered)-1)//self.page_size))
        start=self.page*self.page_size;end=min(len(filtered),start+self.page_size)
        for index,values in filtered[start:end]:self.table.insert('', 'end',iid=str(index),values=values)
        self.previous.configure(state='normal' if self.page else 'disabled')
        self.next.configure(state='normal' if end<len(filtered) else 'disabled')
        self.page_info.set(f'{start+1 if filtered else 0:,}–{end:,} of {len(filtered):,} matching differences')

    def _start(self,operation,kind):
        if self.busy:return
        self.busy=True;revision=self._revision
        for control in self.controls:control.configure(state='disabled')
        self.export_button.configure(state='disabled')
        self.status.set('Comparing copied saves…' if kind=='compare' else 'Writing a new comparison report…')
        def worker():
            try:self._results.put((revision,kind,operation(),None))
            except Exception as error:self._results.put((revision,kind,None,error))
        threading.Thread(target=worker,daemon=True).start()
        self.root.after(30,self._poll)

    def _poll(self):
        try:revision,kind,result,error=self._results.get_nowait()
        except queue.Empty:
            self.root.after(30,self._poll);return
        self.busy=False
        for control in self.controls:control.configure(state='readonly' if control is self.selector else 'normal')
        if revision!=self._revision:
            self.status.set('Selections changed. Compare the copies again.');return
        if error is not None:
            self.prepared=None;self.refresh();self.status.set('Comparison failed: '+str(error))
            messagebox.showerror('Compare Saves',str(error),parent=self.root);return
        if kind=='compare':
            self.prepared=result;self.refresh()
            self.status.set(f'{len(result.rows):,} field differences; {result.unchanged_fields:,} unchanged fields. '
                 f'{result.changed_payload_bytes:,} payload bytes differ; {result.outside_field_bytes:,} outside editable storage spans.')
        else:self.status.set('Comparison report saved: '+Path(result).name)
        self.export_button.configure(state='normal' if self.prepared else 'disabled')

    def compare(self):
        if self.busy:return
        game_id=self._games.get(self.game.get())
        if not game_id or not self.first.get() or not self.second.get():
            messagebox.showinfo('Compare Saves','Choose a game/platform and both copied saves.',parent=self.root);return
        first,second=self.first.get(),self.second.get()
        self.prepared=None;self.refresh()
        self._start(lambda:backend.prepare(game_id,first,second),'compare')

    def export(self):
        if self.busy or self.prepared is None:return
        path=filedialog.asksaveasfilename(parent=self.root,title='Export a new comparison report',
              defaultextension='.json',filetypes=[('Comparison report','*.json')],initialfile='SaveComparison.json')
        if path:
            prepared=self.prepared
            self._start(lambda:backend.export(prepared,path),'export')
