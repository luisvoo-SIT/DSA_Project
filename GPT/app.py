"""Market Expand desktop inventory application."""
import csv
import sys
import pandas as pd
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure
from pathlib import Path
from PySide6.QtCore import Qt
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (QApplication,QComboBox,QDoubleSpinBox,QFileDialog,QHBoxLayout,QHeaderView,
    QLabel,QLineEdit,QMainWindow,QMessageBox,QPushButton,QTableWidget,QTableWidgetItem,QTabWidget,
    QVBoxLayout,QWidget,QSplitter)
from inventory import FIELDS, Tree, allocate, expiry_queue, linear_search, load_csv, recommendations

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__(); self.setWindowTitle('Market Expand — Inventory & Restocking'); self.resize(1400,850)
        self.files={}; self.rows=[]; self.updating=False; self.outlet='All outlets'
        toolbar=self.addToolBar('Data')
        for label,fn in [('Import monthly CSV',self.import_csv),('Save edited CSV',self.save_csv),('Export recommendations',self.export),('Open flowchart',self.open_flowchart)]:
            action=QAction(label,self); action.triggered.connect(fn); toolbar.addAction(action)
        central=QWidget(); layout=QVBoxLayout(central); self.setCentralWidget(central)
        controls=QHBoxLayout(); layout.addLayout(controls)
        self.location=QComboBox(); self.location.addItem('All outlets'); self.location.currentTextChanged.connect(self.render); controls.addWidget(QLabel('Outlet:')); controls.addWidget(self.location)
        self.search=QLineEdit(); self.search.setPlaceholderText('Search product name or ID'); self.search.textChanged.connect(self.render); controls.addWidget(self.search)
        self.budget=QDoubleSpinBox(); self.budget.setRange(0,100000000); self.budget.setDecimals(2); self.budget.setValue(100); self.budget.valueChanged.connect(self.recalculate); controls.addWidget(QLabel('Budget:')); controls.addWidget(self.budget)
        self.method=QComboBox(); self.method.addItems(['Greedy','Knapsack']); self.method.currentTextChanged.connect(self.recalculate); controls.addWidget(self.method)
        self.tabs=QTabWidget(); layout.addWidget(self.tabs)
        inventory_page=QWidget(); inventory_layout=QVBoxLayout(inventory_page)
        filters=QHBoxLayout(); inventory_layout.addLayout(filters)
        self.filter_column=QComboBox(); self.filter_column.addItems(['All columns','Outlet','Report month']+list(FIELDS)); filters.addWidget(QLabel('Filter column:')); filters.addWidget(self.filter_column)
        self.filter_text=QLineEdit(); self.filter_text.setPlaceholderText('Contains (case-insensitive)'); filters.addWidget(self.filter_text)
        self.sort_column=QComboBox(); self.sort_column.addItems(['Outlet','Report month']+list(FIELDS)); filters.addWidget(QLabel('Sort by:')); filters.addWidget(self.sort_column)
        self.sort_order=QComboBox(); self.sort_order.addItems(['Ascending','Descending']); filters.addWidget(self.sort_order)
        for widget in (self.filter_column,self.sort_column,self.sort_order): widget.currentIndexChanged.connect(self.render)
        self.filter_text.textChanged.connect(self.render)
        self.table=QTableWidget(); self.table.cellChanged.connect(self.edited); inventory_layout.addWidget(self.table); self.tabs.addTab(inventory_page,'Inventory (editable)')
        self.results=QTableWidget(); self.results.setEditTriggers(QTableWidget.NoEditTriggers)
        self.recommendation_figure=Figure(figsize=(8,4),layout='constrained'); self.recommendation_canvas=FigureCanvasQTAgg(self.recommendation_figure)
        recommendation_split=QSplitter(Qt.Vertical); recommendation_split.addWidget(self.recommendation_canvas); recommendation_split.addWidget(self.results); recommendation_split.setSizes([400,300]); self.tabs.addTab(recommendation_split,'Recommendations')
        self.expiry=QTableWidget(); self.expiry.setEditTriggers(QTableWidget.NoEditTriggers)
        self.expiry_figure=Figure(figsize=(8,4),layout='constrained'); self.expiry_canvas=FigureCanvasQTAgg(self.expiry_figure)
        expiry_split=QSplitter(Qt.Vertical); expiry_split.addWidget(self.expiry_canvas); expiry_split.addWidget(self.expiry); expiry_split.setSizes([400,300]); self.tabs.addTab(expiry_split,'Expiry queue')
        self.summary=QLabel('Import monthly CSV files to begin.'); self.summary.setWordWrap(True); layout.addWidget(self.summary)
        self.render()
    def import_csv(self):
        paths,_=QFileDialog.getOpenFileNames(self,'Import monthly inventory','','CSV files (*.csv)')
        if not paths:return
        # Validate every selected file before replacing any records.
        try:
            loaded=[(str(Path(p).resolve()),load_csv(p)) for p in paths]
            existing={(rows[0].location,rows[0].period):p for p,rows in self.files.items()}
            selected=set()
            for p,rows in loaded:
                key=(rows[0].location,rows[0].period)
                if key in selected: raise ValueError('Two selected files represent the same outlet and reporting month.')
                selected.add(key)
            replacements=[existing[k] for k in selected if k in existing]
            if replacements and QMessageBox.question(self,'Replace existing data','Replace imported records for the same outlet and reporting month?') != QMessageBox.Yes:return
            for p in replacements: self.files.pop(p)
            self.files.update(loaded); self.sync()
        except (ValueError,OSError) as e: QMessageBox.warning(self,'Import failed',str(e))
    def sync(self):
        self.rows=[r for records in self.files.values() for r in records]
        previous=self.location.currentText(); self.location.blockSignals(True); self.location.clear(); self.location.addItem('All outlets'); self.location.addItems(sorted({r.location for r in self.rows})); idx=self.location.findText(previous); self.location.setCurrentIndex(max(0,idx)); self.location.blockSignals(False); self.render()
    def filtered(self):
        rows=self.rows if self.location.currentText()=='All outlets' else [r for r in self.rows if r.location==self.location.currentText()]
        query=self.search.text().strip()
        if query:
            groups={}
            for r in rows: groups.setdefault(r.item_id,[]).append(r)
            exact=Tree(list(groups.items())).find(query)
            rows=exact if exact is not None else linear_search(rows,query)
        if not rows: return []
        frame=pd.DataFrame([{'Outlet':r.location,'Report month':r.period, **{f:getattr(r,f) for f in FIELDS}, '_record':r} for r in rows])
        term=self.filter_text.text().strip()
        if term:
            column=self.filter_column.currentText()
            columns=list(frame.columns.drop('_record')) if column=='All columns' else [column]
            mask=pd.Series(False,index=frame.index)
            for col in columns: mask |= frame[col].astype(str).str.contains(term,case=False,regex=False,na=False)
            frame=frame.loc[mask]
        frame=frame.sort_values(self.sort_column.currentText(),ascending=self.sort_order.currentText()=='Ascending',kind='stable')
        return frame['_record'].tolist()
    def draw_recommendations(self, rows):
        fig=self.recommendation_figure; fig.clear(); ax=fig.add_subplot(111)
        if not rows: ax.text(.5,.5,'No recommendations to display',ha='center',va='center',transform=ax.transAxes); ax.set_axis_off()
        else:
            frame=pd.DataFrame(rows).head(20).iloc[::-1]
            labels=[f"{r.location} · {r.item_id}" for r in frame.itertuples()]
            positions=list(range(len(frame)))
            ax.barh(positions,frame['need'],label='Indicative need',color='#dce5ec')
            ax.barh(positions,frame['qty'],label='Allocated',color='#218a72')
            ax.set_yticks(positions,labels); ax.set_xlabel('Units'); ax.set_title('Restocking need and allocated units (first 20 ranked products)'); ax.legend(loc='lower right')
        self.recommendation_canvas.draw_idle()
    def draw_expiry(self, rows):
        fig=self.expiry_figure; fig.clear(); ax=fig.add_subplot(111)
        if not rows: ax.text(.5,.5,'No batches to display',ha='center',va='center',transform=ax.transAxes); ax.set_axis_off()
        else:
            # Each point is a batch in an imported snapshot; historical snapshots are included.
            frame=pd.DataFrame([{'remaining':r.remaining,'stock':r.current_total_stock} for r in rows])
            buckets=pd.cut(frame['remaining'],[-float('inf'),-1,14,30,float('inf')],labels=['Expired','0–14 days','15–30 days','Over 30 days'])
            totals=frame.groupby(buckets,observed=False)['stock'].sum().reindex(['Expired','0–14 days','15–30 days','Over 30 days'],fill_value=0)
            ax.bar(totals.index,totals.values,color=['#c84949','#ef9857','#e8c35d','#3f9c83']); ax.set_ylabel('Units in snapshots'); ax.set_title('Batch expiry by report date — includes historical snapshots')
        self.expiry_canvas.draw_idle()
    def set_table(self,table,headers,rows,editable=False):
        table.setRowCount(len(rows)); table.setColumnCount(len(headers)); table.setHorizontalHeaderLabels(headers)
        for i,row in enumerate(rows):
            for j,value in enumerate(row):
                cell=QTableWidgetItem(str(value))
                if not editable or j<2: cell.setFlags(cell.flags() & ~Qt.ItemIsEditable)
                table.setItem(i,j,cell)
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
    def render(self,*_):
        if not hasattr(self,'table'): return
        self.updating=True; self.visible=self.filtered()
        self.set_table(self.table,['Outlet','Report month']+list(FIELDS),[[r.location,r.period.strftime('%Y-%m')]+[getattr(r,f) for f in FIELDS] for r in self.visible],True)
        expiry_rows=expiry_queue(self.visible)
        self.set_table(self.expiry,['Outlet','Report month','Product','Batch','Remaining days','Batch stock'],[[r.location,r.period.strftime('%Y-%m'),r.item_name,r.batch_no,r.remaining,r.current_total_stock] for r in expiry_rows])
        self.draw_expiry(expiry_rows)
        self.updating=False; self.recalculate()
    def edited(self,row,col):
        if self.updating or col<2:return
        from dataclasses import replace
        old=self.visible[row]; name=FIELDS[col-2]; value=self.table.item(row,col).text().strip()
        # Validate the complete modified monthly dataset through the same CSV parser.
        import tempfile
        try:
            source=next(p for p,records in self.files.items() if old in records)
            records=self.files[source]; field_index=records.index(old)
            import io
            buffer=io.StringIO(newline='')
            writer=csv.DictWriter(buffer,fieldnames=FIELDS); writer.writeheader()
            for i,r in enumerate(records):
                data={k:getattr(r,k) for k in FIELDS}
                if i==field_index or (name=='mth_purchase' and r.item_id==old.item_id):data[name]=value
                writer.writerow(data)
            self.files[source]=load_csv(source, buffer.getvalue())
            self.sync()
        except (ValueError,OSError) as e:
            QMessageBox.warning(self,'Invalid edit',str(e)); self.render()
    def recalculate(self,*_):
        if not hasattr(self,'results'):return
        try:
            # Search is a display filter; the shared budget is allocated across all selected outlets.
            rows=self.rows if self.location.currentText()=='All outlets' else [r for r in self.rows if r.location==self.location.currentText()]
            data=allocate(recommendations(rows),self.budget.value(),self.method.currentText()); self.all_results=data
            q=self.search.text().strip().casefold(); shown=[r for r in data if q in r['item_id'].casefold() or q in r['name'].casefold()]
            self.draw_recommendations(shown)
            self.set_table(self.results,['Outlet','ID','Product','Report','Forecast/month','Stock','Expiring ≤14d','Need','Unit cost','Unit margin','Allocate','Spend'],[[r['location'],r['item_id'],r['name'],r['period'].strftime('%Y-%m'),f"{r['forecast']:.1f}",r['stock'],r['expiring'],r['need'],r['cost'],r['margin'],r['qty'],f"{r['qty']*r['cost']:.2f}"] for r in shown])
            spend=sum(r['qty']*r['cost'] for r in data)
            self.summary.setText(f"{len(rows)} batch records · {len(data)} outlet/products · Allocated: {spend:.2f} of {self.budget.value():.2f}. Search filters the display; allocation uses all products in the selected outlets. See README for assumptions.")
        except ValueError as e:
            self.all_results=[]; self.results.setRowCount(0); self.draw_recommendations([]); self.summary.setText(str(e))
    def save_csv(self):
        if not self.files: return
        paths=list(self.files); labels=[Path(p).name for p in paths]
        from PySide6.QtWidgets import QInputDialog
        choice,ok=QInputDialog.getItem(self,'Save edited data','Choose imported month:',labels,0,False)
        if not ok:return
        source=paths[labels.index(choice)]
        path,_=QFileDialog.getSaveFileName(self,'Save CSV',source,'CSV files (*.csv)')
        if not path:return
        try:
            # Filename conveys metadata; reject mismatches before writing.
            if Path(path).stem != Path(source).stem: raise ValueError('Keep the same filename so outlet and reporting month remain correct.')
            with open(path,'w',encoding='utf-8',newline='') as f:
                writer=csv.DictWriter(f,fieldnames=FIELDS); writer.writeheader()
                for r in self.files[source]:writer.writerow({k:getattr(r,k) for k in FIELDS})
            self.statusBar().showMessage('Saved '+path,5000)
        except (OSError,ValueError) as e: QMessageBox.warning(self,'Save failed',str(e))
    def export(self):
        if not getattr(self,'all_results',[]):return
        path,_=QFileDialog.getSaveFileName(self,'Export recommendations','recommendations.csv','CSV files (*.csv)')
        if not path:return
        try:
            with open(path,'w',encoding='utf-8',newline='') as f:
                writer=csv.DictWriter(f,fieldnames=list(self.all_results[0])); writer.writeheader(); writer.writerows(self.all_results)
        except OSError as e: QMessageBox.warning(self,'Export failed',str(e))
    def open_flowchart(self):
        from flowchart import Window
        self.flowchart=Window(); self.flowchart.show()

def main():
    app=QApplication(sys.argv); window=MainWindow(); window.show(); sys.exit(app.exec())
if __name__=='__main__':main()
