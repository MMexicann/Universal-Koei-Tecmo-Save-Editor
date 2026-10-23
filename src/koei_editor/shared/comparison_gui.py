"""Retained copied-save comparison; workers never access Tk objects."""
from pathlib import Path
import queue
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from koei_editor.shared import save_comparison as backend
from koei_editor.shared import save_transfer
from koei_editor.shared.appearance import ui_font
from koei_editor.shared.scrollable_panel import ScrollablePanel
from koei_editor.games.dw3.models import SaveError

STATUS_LABELS = {'value_changed': 'Value changed', 'definition_changed': 'Record definition changed',
                 'available_in_first': 'Available in first', 'available_in_second': 'Available in second'}


class ComparisonWorkspace:
    def __init__(self, root, parent, *, scrollable=True, initial_game_id=None,
                 initial_first=None, target_editor=None):
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
        self.target_editor = target_editor
        self.last_transfer_dialog = None
        self._games = {game.title + ' · ' + game.subtitle + ' [' + game.platform + ']': game.id
                       for game in backend.COMPARABLE_GAMES}
        target_game_id = getattr(getattr(target_editor, 'adapter', None), 'game_id', None)
        if target_editor is not None:
            document = getattr(target_editor, 'document', None)
            if document is None or target_game_id not in self._games.values():
                raise SaveError('Open a registered scalar save copy before comparing for selective transfer.')
            if initial_game_id is not None and initial_game_id != target_game_id:
                raise SaveError('The comparison profile must match the active editor profile.')
            initial_game_id = target_game_id
            initial_first = initial_first or document.source
        initial_label = next((label for label, game_id in self._games.items()
                              if game_id == initial_game_id), None)
        if initial_game_id is not None and initial_label is None:
            raise SaveError('Choose a registered scalar profile for comparison.')
        ttk.Label(body, text='COMPARE SAVES', font=(ui_font(root), 23, 'bold')).pack(anchor='w')
        ttk.Label(body, text='See what changed between two copies of the same game/platform.',
                  style='Muted.TLabel', wraplength=980).pack(anchor='w', pady=(4, 14))
        form = ttk.Frame(body); form.pack(fill='x'); form.columnconfigure(1, weight=1)
        self.game = tk.StringVar(root, value=initial_label or next(iter(self._games)))
        self.first, self.second = tk.StringVar(root, value=str(initial_first) if initial_first else ''), tk.StringVar(root)
        self.controls=[]
        ttk.Label(form, text='Game and platform').grid(row=0, column=0, sticky='w', padx=(0,14))
        self.selector = ttk.Combobox(form, textvariable=self.game, values=tuple(self._games), state='readonly',width=1)
        self.selector.grid(row=0, column=1, columnspan=2, sticky='ew', pady=8)
        if target_editor is not None:
            self.selector.configure(state='disabled')
        self.controls.append(self.selector)
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
        self.transfer_button = ttk.Button(actions, text='Open Selective Transfer…',
                                          command=self.open_selective_transfer, state='disabled')
        self.status=tk.StringVar(root,value='Choose two separate copied saves and their exact profile.')
        ttk.Label(body,textvariable=self.status,wraplength=980).pack(anchor='w',pady=(14,8))
        search=ttk.Frame(body);search.pack(fill='x',pady=(4,8))
        ttk.Label(search,text='Find differences').pack(side='left',padx=(0,12))
        self.search=tk.StringVar(root)
        self.search_entry=ttk.Entry(search,textvariable=self.search,width=1)
        self.search_entry.pack(side='left',fill='x',expand=True)
        self.controls.append(self.search_entry)
        self.filter=tk.StringVar(root,value='All differences')
        self.filter_selector=ttk.Combobox(search,textvariable=self.filter,values=('All differences','Value changed','Record definition changed','Available in first','Available in second'),state='readonly',width=24)
        self.filter_selector.pack(side='left',padx=10)
        self.controls.append(self.filter_selector)
        table=ttk.Frame(body);table.pack(fill='both',expand=True)
        self.table=ttk.Treeview(table,columns=('record','field','first','second','status'),show='headings',height=15,selectmode='extended')
        for key,title,width in (('record','Record',200),('field','Field',240),('first','First copy',130),
                                ('second','Second copy',130),('status','Difference',200)):
            self.table.heading(key,text=title);self.table.column(key,width=width,minwidth=80)
        scrollbar=ttk.Scrollbar(table,orient='vertical',command=self.table.yview)
        horizontal=ttk.Scrollbar(table,orient='horizontal',command=self.table.xview)
        self.table.configure(yscrollcommand=scrollbar.set,xscrollcommand=horizontal.set)
        scrollbar.pack(side='right',fill='y');horizontal.pack(side='bottom',fill='x')
        self.table.pack(fill='both',expand=True)
        self.table.bind('<<TreeviewSelect>>', self._selection_changed)
        self.guidance_label = ttk.Label(body, text='', style='Muted.TLabel', wraplength=980)
        self.guidance_label.pack(anchor='w', pady=(12, 0))
        for variable in (self.game,self.first,self.second):variable.trace_add('write',self.invalidate)
        for variable in (self.search,self.filter):variable.trace_add('write',self.refilter)
        paging=self.paging
        self.previous=ttk.Button(paging,text='Previous',command=lambda:self.change_page(-1),state='disabled');self.previous.grid(row=0,column=0,sticky='w')
        self.next=ttk.Button(paging,text='Next',command=lambda:self.change_page(1),state='disabled');self.next.grid(row=0,column=1,sticky='w',padx=10)
        self.page_info=tk.StringVar(root,value='No comparison yet');ttk.Label(paging,textvariable=self.page_info,wraplength=700).grid(row=1,column=0,columnspan=3,sticky='w')

        body.bind('<Configure>',self._resize_guidance,add='+')
        self._bound_document = getattr(target_editor, 'document', None)
        self._binding_update = False
        self._set_target_guidance()

    def _resize_guidance(self, event):
        for widget in self._comparison_body.winfo_children():
            if isinstance(widget, ttk.Label):
                widget.configure(wraplength=max(1, event.width - 8))


    def apply_theme(self, palette):
        if self._comparison_viewport is not None:
            self._comparison_viewport.apply_theme(palette)

    def invalidate(self,*_args):
        if self._binding_update:
            return
        self._revision+=1;self.prepared=None;self.page=0;self.export_button.configure(state='disabled');self.refresh()
        if not self.busy:self.status.set('Selections changed. Compare the copies again.')
        self._update_transfer_button()

    def _selection_changed(self, _event=None):
        self._update_transfer_button()

    def _set_target_guidance(self):
        transfer_supported = (self.target_editor is not None
                              and save_transfer.supports_transfer(self.target_editor.adapter))
        if transfer_supported:
            self.guidance_label.configure(
                text=('Selected comparison rows can only suggest fields to the existing selective transfer. '
                      'That workflow rechecks semantic identity, ownership and exclusions, then shows a complete preview.'))
            self.transfer_button.pack(side='left', padx=4)
        elif self.target_editor is not None:
            self.guidance_label.configure(
                text=('Comparison is pinned to the active editor save. Selective transfer is not qualified for this profile.'))
            self.transfer_button.pack_forget()
        else:
            self.guidance_label.configure(
                text=('Fields align by this profile’s field IDs. Conditional records may differ. '
                      'A comparison report does not authorize additional gameplay edits.'))
            self.transfer_button.pack_forget()

    def bind_target_editor(self, editor):
        """Bind the reusable comparison to the current scalar editor session, if any."""
        document = getattr(editor, 'document', None) if editor is not None else None
        game_id = getattr(getattr(editor, 'adapter', None), 'game_id', None) if editor is not None else None
        if editor is not None and (document is None or game_id not in self._games.values()):
            editor = None
            document = None
            game_id = None
        changed = editor is not self.target_editor or document is not self._bound_document
        self.target_editor = editor
        self._bound_document = document
        self._binding_update = True
        try:
            if editor is None:
                self.selector.configure(state='disabled' if self.busy else 'readonly')
            else:
                label = next(label for label, profile in self._games.items() if profile == game_id)
                self.selector.configure(state='disabled')
                self.game.set(label)
                self.first.set(str(document.source))
        finally:
            self._binding_update = False
        self._set_target_guidance()
        if changed:
            self._revision += 1
            self.prepared = None
            self.page = 0
            self.export_button.configure(state='disabled')
            self.refresh()
            self.status.set('Destination editor session changed. Compare the copies again.')
        self._update_transfer_button()

    def _update_transfer_button(self):
        self.transfer_button.configure(state='normal' if self.target_editor is not None
                                       and save_transfer.supports_transfer(self.target_editor.adapter)
                                       and self.prepared is not None and not self.busy
                                       else 'disabled')

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
        self._update_transfer_button()

    def _start(self,operation,kind):
        if self.busy:return
        self.busy=True;revision=self._revision
        for control in self.controls:control.configure(state='disabled')
        self.table.state(('disabled',))
        self.export_button.configure(state='disabled')
        if self.transfer_button is not None:
            self.transfer_button.configure(state='disabled')
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
        for control in self.controls:
            state = ('disabled' if control is self.selector and self.target_editor is not None else
                     'readonly' if control is self.selector or control is self.filter_selector else 'normal')
            control.configure(state=state)
        self.table.state(('!disabled',))
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
        self._update_transfer_button()

    def compare(self):
        if self.busy:return
        game_id=self._games.get(self.game.get())
        if not game_id or not self.first.get() or not self.second.get():
            messagebox.showinfo('Compare Saves','Choose a game/platform and both copied saves.',parent=self.root);return
        first,second=self.first.get(),self.second.get()
        self.prepared=None;self.refresh()
        self._start(lambda:backend.prepare(game_id,first,second),'compare')

    def open_selective_transfer(self):
        """Open the registered semantic transfer flow using this comparison's second copy."""
        if self.busy or self.prepared is None:
            return None
        if self.target_editor is None:
            self.status.set('Open comparison from an active scalar editor to use selective transfer.')
            return None
        try:
            editor = self.target_editor
            adapter = getattr(editor, 'adapter', None)
            document = getattr(editor, 'document', None)
            if adapter is None or document is None:
                raise SaveError('The destination editor session is no longer open.')
            if not save_transfer.supports_transfer(adapter):
                raise SaveError('Selective transfer is not qualified for this game/platform profile.')
            game_id = self._games.get(self.game.get())
            if adapter.game_id != self.prepared.game_id or adapter.game_id != game_id:
                raise SaveError('The comparison and active destination use different game/platform profiles.')
            if document.sha256 != self.prepared.left.sha256:
                raise SaveError('The comparison first copy must match the exact save snapshot open in the destination editor.')
            # Revalidate both selected paths before handing the second one to the
            # transfer dialog. Its catalogue then performs its own source and
            # destination checks before displaying any available choices.
            backend.validate_sources(self.prepared)
            selected_rows = tuple(self.table.selection())
            candidate_ids = []
            skipped_rows = []
            for identity in selected_rows:
                try:
                    row = self.prepared.rows[int(identity)]
                except (ValueError, IndexError):
                    raise SaveError('A selected comparison row is no longer available. Compare the copies again.')
                # A field-level value difference is only a suggestion. The
                # semantic transfer catalogue remains authoritative for which
                # IDs and source/target identities are portable.
                if row.status == 'value_changed':
                    candidate_ids.append(row.id)
                else:
                    skipped_rows.append((row.id, row.status))
            from koei_editor.shared.transfer_gui import open_transfer
            dialog = open_transfer(editor, source_path=self.prepared.right.source,
                                   selected_ids=tuple(dict.fromkeys(candidate_ids)),
                                   comparison_selection_count=len(selected_rows),
                                   comparison_skipped_rows=tuple(skipped_rows),
                                   expected_source_sha256=self.prepared.right.sha256)
            if dialog is not None:
                self.last_transfer_dialog = dialog
                if dialog.source is None:
                    self.status.set('Selective transfer did not load the reviewed second copy. Compare the copies again.')
                else:
                    self.status.set('Selective transfer opened with the second copy as its source. '
                                    'Review catalogue exclusions and the complete transfer preview before staging.')
            return dialog
        except Exception as error:
            self.status.set('Selective transfer was not opened. ' + str(error))
            messagebox.showerror('Open Selective Transfer', str(error), parent=self.root)
            return None

    def export(self):
        if self.busy or self.prepared is None:return
        path=filedialog.asksaveasfilename(parent=self.root,title='Export a new comparison report',
              defaultextension='.json',filetypes=[('Comparison report','*.json')],initialfile='SaveComparison.json')
        if path:
            prepared=self.prepared
            self._start(lambda:backend.export(prepared,path),'export')
