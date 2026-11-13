import json
import math
import sys
from pathlib import Path

from PySide6.QtCore import Qt, QPointF, QRectF, QDate
from PySide6.QtGui import QAction, QBrush, QColor, QFont, QPainter, QPainterPath, QPen, QPolygonF
from PySide6.QtWidgets import (QApplication, QComboBox, QFileDialog, QFormLayout, QGraphicsItem,
    QGraphicsPathItem, QGraphicsPolygonItem, QGraphicsRectItem, QGraphicsScene, QGraphicsTextItem,
    QGraphicsView, QHBoxLayout, QInputDialog, QLabel, QMainWindow, QMessageBox, QPushButton,
    QSplitter, QToolBar, QVBoxLayout, QWidget, QDockWidget, QDoubleSpinBox, QSpinBox, QTextEdit, QDateEdit)

FIELDS = ('location, item_id, item_name, category, unit_cost, unit_sell, current_total_stock, '
          'mth_purchase, lead_time, shelf_life, batch_no, expiry_duration, qty_expiry, supplier_rating')

# Coordinates are deliberately editable; links describe the directional process in the diagrams.
def initial_graph():
    nodes = []
    edges = []
    def add(key, text, x, y, group='Operations', shape='process'):
        nodes.append(dict(id=key, text=text, x=x, y=y, group=group, shape=shape))
    def link(a, b): edges.append([a, b])
    for args in [
        ('start','Start',0,0),('login','Login',0,110),('location','Select location',0,220),
        ('a','Outlet A',240,150),('b','Outlet B',240,220),('c','Outlet C',240,290),
        ('options','Options',0,390),('purchase','Purchase',0,510),('update','View & update',0,630),('end','End',0,750),
        ('past','Past data retrieval',300,400),('past_view','View past data',560,350),('past_edit','Edit past data',560,450),('past_summary','Summary',800,350),
        ('current','Current data',300,620),('current_edit','Edit current data',560,560),('current_view','View current data',560,650),('current_summary','Summary',800,650),('current_purchase','Purchase',1040,650),
        ('upload','Upload data',300,880),('upload_view','View upload',560,810),('upload_edit','Edit upload',560,900),('replace','Existing current data?\nReplace or keep',560,990),('sort','Sort',800,990),('recommend','Recommend',1040,990),('proceed','Proceed to purchase',1280,990),
        ('shipment','Shipment status',300,1190),('check','Check status',560,1190),('status','Update status',800,1190),('rating','Adjust rating\n(auto / manual)',1040,1190),('return','Return to options',1280,1190)]: add(*args)
    for a,b in [('start','login'),('login','location'),('location','a'),('location','b'),('location','c'),('location','options'),('options','purchase'),('purchase','update'),('update','end'),('options','past'),('past','past_view'),('past','past_edit'),('past_edit','past_view'),('past_view','past_summary'),('past_summary','return'),('options','current'),('current','current_edit'),('current','current_view'),('current_edit','current_view'),('current_view','current_summary'),('current_summary','current_purchase'),('current_summary','return'),('current_purchase','return'),('options','upload'),('upload','upload_view'),('upload','upload_edit'),('upload','replace'),('replace','sort'),('sort','recommend'),('recommend','upload_edit'),('recommend','proceed'),('recommend','return'),('options','shipment'),('shipment','check'),('check','status'),('status','rating'),('rating','check'),('check','return')]: link(a,b)
    g='Sorting & recommendation'
    for key, label, x, y in [
        ('s_sort','Sort',0,0),('prep','Data preparation',0,120),('lookup','Product lookup',300,0),('tree','Binary search tree',590,0),('linear','Linear search',590,90),
        ('trend','Trend analysis',300,190),('month','Get mth_purchase',590,160),('total','Get total purchase / month',590,250),('regression','Past data → linear regression',890,200),
        ('expiry','Expiring stock',300,400),('batch','Get batch_no',590,350),('duration','Get expiry_duration',590,440),('stock','Get current_total_stock and qty_expiry',590,530),('queue','Priority queue by expiry',890,440),
        ('profit','Cost-profit ratio',300,700),('cost','Get unit_cost',590,650),('sell','Get unit_sell',590,740),('profit_batch','Get batch_no for cost changes',590,830),('merge','(sell − cost) / cost\nMerge sort high to low',890,740),
        ('score','Score matrix',0,940),('allocate','Greedy / dynamic programming knapsack',300,940),('s_recommend','Recommend',590,940)]: add(key,label,x,y,g)
    for a,b in [('s_sort','prep'),('prep','lookup'),('lookup','tree'),('lookup','linear'),('prep','trend'),('trend','month'),('trend','total'),('month','regression'),('total','regression'),('prep','expiry'),('expiry','batch'),('expiry','duration'),('expiry','stock'),('batch','queue'),('duration','queue'),('stock','queue'),('prep','profit'),('profit','cost'),('profit','sell'),('profit','profit_batch'),('cost','merge'),('sell','merge'),('profit_batch','merge'),('prep','score'),('score','allocate'),('allocate','s_recommend')]: link(a,b)
    return {'nodes':nodes,'edges':edges}

class Node(QGraphicsRectItem):
    def __init__(self, data, scene):
        super().__init__(0,0,200,64)
        self.data = data
        self.owner = scene
        self.setBrush(QBrush(QColor('#ff914d')))
        self.setPen(QPen(QColor('#d66c2d'), 1.5))
        self.setFlags(QGraphicsItem.ItemIsMovable | QGraphicsItem.ItemIsSelectable | QGraphicsItem.ItemSendsGeometryChanges)
        self.label = QGraphicsTextItem(self)
        self.label.setDefaultTextColor(QColor('#17212b'))
        self.label.setFont(QFont('Segoe UI', 10))
        self.set_text(data['text'])
        self.setPos(data['x'],data['y'])
    def set_text(self, text):
        self.data['text'] = text
        self.label.setPlainText(text + ('\n' + self.owner.live.get(self.data['id'], '') if self.owner.live.get(self.data['id']) else ''))
        self.label.setTextWidth(188)
        self.label.setPos(6, max(0,(64-self.label.boundingRect().height())/2))
    def itemChange(self, change, value):
        if change == QGraphicsItem.ItemPositionHasChanged and hasattr(self,'owner'):
            self.data['x'], self.data['y'] = value.x(), value.y()
            self.owner.update_edges()
        return super().itemChange(change,value)
    def mouseDoubleClickEvent(self, event):
        text, ok = QInputDialog.getMultiLineText(None, 'Edit step', 'Step text:', self.data['text'])
        if ok and text.strip(): self.set_text(text.strip())
        super().mouseDoubleClickEvent(event)

class Diagram(QGraphicsScene):
    def __init__(self, graph, group, live=None):
        super().__init__()
        self.graph, self.group = graph, group
        self.live = live or {}
        self.nodes = {}
        self.edge_items = []
        self.setBackgroundBrush(QColor('#f7f9fc'))
        for data in graph['nodes']:
            if data['group'] == group:
                node=Node(data,self); self.addItem(node); self.nodes[data['id']]=node
        self.update_edges()
    def update_edges(self):
        for item in self.edge_items: self.removeItem(item)
        self.edge_items=[]
        for a,b in self.graph['edges']:
            if a not in self.nodes or b not in self.nodes: continue
            one,two=self.nodes[a],self.nodes[b]
            p1=one.sceneBoundingRect().center(); p2=two.sceneBoundingRect().center()
            dx,dy=p2.x()-p1.x(),p2.y()-p1.y()
            if not dx and not dy: continue
            scale1=min(100/abs(dx) if dx else float('inf'),32/abs(dy) if dy else float('inf'))
            start=QPointF(p1.x()+dx*scale1,p1.y()+dy*scale1)
            end=QPointF(p2.x()-dx*scale1,p2.y()-dy*scale1)
            path=QPainterPath(start); path.lineTo(end)
            line=QGraphicsPathItem(path); line.setPen(QPen(QColor('#8295a6'),2)); line.setZValue(-1); self.addItem(line)
            angle=math.atan2(dy,dx); size=10
            arrow=QPolygonF([end,QPointF(end.x()-size*math.cos(angle-0.45),end.y()-size*math.sin(angle-0.45)),QPointF(end.x()-size*math.cos(angle+0.45),end.y()-size*math.sin(angle+0.45))])
            tip=QGraphicsPolygonItem(arrow); tip.setBrush(QColor('#8295a6')); tip.setPen(QPen(Qt.NoPen)); tip.setZValue(-1); self.addItem(tip)
            self.edge_items.extend([line,tip])
        self.setSceneRect(self.itemsBoundingRect().adjusted(-100,-100,100,100))
    def selected_nodes(self): return [n for n in self.selectedItems() if isinstance(n,Node)]

class View(QGraphicsView):
    def __init__(self):
        super().__init__(); self.setRenderHint(QPainter.Antialiasing); self.setDragMode(QGraphicsView.RubberBandDrag)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
    def wheelEvent(self,event):
        if event.modifiers() & Qt.ControlModifier:
            factor=1.15 if event.angleDelta().y()>0 else 1/1.15
            self.scale(factor,factor); event.accept()
        else: super().wheelEvent(event)

class Window(QMainWindow):
    def __init__(self):
        super().__init__(); self.graph=initial_graph(); self.path=None
        self.setWindowTitle('Market Expand — Editable Flowchart'); self.resize(1350,800)
        toolbar=QToolBar('Flowchart'); self.addToolBar(toolbar)
        self.group=QComboBox(); self.group.addItems(['Operations','Sorting & recommendation']); self.group.currentTextChanged.connect(self.refresh); toolbar.addWidget(self.group)
        for title,fn in [('Add step',self.add_node),('Connect selected',self.connect_nodes),('Remove connection',self.remove_connection),('Delete selected',self.delete_nodes),('Fit diagram',self.fit),('Open',self.open_file),('Save',self.save),('Save as',self.save_as),('Reset',self.reset)]:
            action=QAction(title,self); action.triggered.connect(fn); toolbar.addAction(action)
        self.view=View(); self.setCentralWidget(self.view)
        self.statusBar().showMessage('Drag steps to move; double-click to edit; Ctrl+wheel to zoom. Select two steps with Ctrl to connect.')
        self.setup_preview()
        self.refresh()
    def refresh(self, *_):
        self.scene=Diagram(self.graph,self.group.currentText(), self.preview_values()); self.view.setScene(self.scene); self.fit()
    def setup_preview(self):
        dock = QDockWidget('Live calculation preview', self)
        dock.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)
        panel = QWidget(); layout = QVBoxLayout(panel)
        intro = QLabel('Edit one product’s values to see the example calculation update. Switch to Sorting & recommendation to see values on the chart.')
        intro.setWordWrap(True); layout.addWidget(intro)
        form = QFormLayout(); self.inputs = {}
        specifications = [('unit_cost', 2.0, 2), ('unit_sell', 3.0, 2),
            ('current_total_stock', 20, 0), ('mth_purchase', 60, 0),
            ('lead_time', 7, 0), ('shelf_life', 90, 0),
            ('supplier_rating', 4, 1), ('budget', 100, 2)]
        for name, default, decimals in specifications:
            spin = QDoubleSpinBox(); spin.setDecimals(decimals)
            spin.setRange(0, 5 if name == 'supplier_rating' else 1000000)
            spin.setValue(default); spin.valueChanged.connect(self.update_preview)
            self.inputs[name] = spin; form.addRow(name.replace('_', ' '), spin)
        for name, date in [('batch_month', QDate(2026, 5, 1)), ('report_month', QDate(2026, 6, 1))]:
            field = QDateEdit(date); field.setDisplayFormat('MM/yyyy'); field.dateChanged.connect(self.update_preview)
            self.inputs[name] = field; form.addRow(name.replace('_', ' '), field)
        layout.addLayout(form)
        self.preview_output = QLabel(); self.preview_output.setWordWrap(True)
        self.preview_output.setTextInteractionFlags(Qt.TextSelectableByMouse)
        layout.addWidget(self.preview_output); layout.addStretch()
        dock.setWidget(panel); self.addDockWidget(Qt.RightDockWidgetArea, dock)
        self.update_preview()
    def input_values(self):
        v = {name: field.value() for name, field in self.inputs.items() if isinstance(field, QDoubleSpinBox)}
        batch = self.inputs['batch_month'].date()
        report = self.inputs['report_month'].date()
        delivered = QDate(batch.year(), batch.month(), batch.daysInMonth()).addDays(int(v['lead_time']))
        report_date = QDate(report.year(), report.month(), report.daysInMonth())
        v['expiry_duration'] = v['shelf_life'] - delivered.daysTo(report_date)
        v['delivery_date'] = delivered
        v['report_date'] = report_date
        return v
    def preview_values(self):
        v = self.input_values()
        v['qty_expiry'] = v['current_total_stock'] if v['expiry_duration'] <= 14 else 0
        demand = v['mth_purchase'] / 30
        # Illustrative target: cover delivery lead time plus 30 days of sales.
        target = math.ceil(demand * (v['lead_time'] + 30))
        usable = max(0, v['current_total_stock'] - v['qty_expiry'])
        need = max(0, target - usable)
        affordable = math.floor(v['budget'] / v['unit_cost']) if v['unit_cost'] > 0 else 0
        qty = min(need, affordable)
        ratio = (v['unit_sell'] - v['unit_cost']) / v['unit_cost'] if v['unit_cost'] > 0 else None
        fmt = lambda n: f'{n:g}'
        return {'month': f"Purchases: {fmt(v['mth_purchase'])} units/month",
            'duration': f"Remaining: {fmt(v['expiry_duration'])} days",
            'stock': f"Stock: {fmt(v['current_total_stock'])}; expiring: {fmt(v['qty_expiry'])}",
            'cost': f"Cost: {v['unit_cost']:.2f}", 'sell': f"Sell: {v['unit_sell']:.2f}",
            'merge': 'Ratio: ' + (f'{ratio:.2%}' if ratio is not None else 'undefined (zero cost)'),
            's_recommend': f'Illustrative quantity: {qty}'}
    def update_preview(self, *_):
        if not hasattr(self, 'preview_output'): return
        v = self.input_values()
        v['qty_expiry'] = v['current_total_stock'] if v['expiry_duration'] <= 14 else 0
        demand = v['mth_purchase'] / 30
        target = math.ceil(demand * (v['lead_time'] + 30))
        usable = max(0, v['current_total_stock'] - v['qty_expiry'])
        need = max(0, target - usable)
        qty = min(need, math.floor(v['budget'] / v['unit_cost'])) if v['unit_cost'] else 0
        ratio = (v['unit_sell'] - v['unit_cost']) / v['unit_cost'] if v['unit_cost'] else None
        warning = ''
        if v['delivery_date'] > v['report_date']:
            warning = '\nWarning: assumed delivery is after the report date; this batch cannot yet be on hand.'
        if v['unit_cost'] == 0:
            warning = '\nEnter a positive unit cost to calculate affordable quantity.'
        self.preview_output.setText(f"Assumed delivery: {v['delivery_date'].toString('yyyy-MM-dd')}\nRemaining shelf life: {v['expiry_duration']:g} days\n"
            f"Estimated daily demand: {demand:.2f} units\n"
            f"Target stock: {target} units\nUsable stock: {usable:g} units\n"
            f"Indicative need: {need:g} units\nAffordable recommendation: {qty:g} units\n"
            f"Estimated spend: {qty * v['unit_cost']:.2f}\n"
            f"Profit/cost: {f'{ratio:.2%}' if ratio is not None else 'undefined'}{warning}\n\n"
            'Example only: assumes a 30-day month, one batch, and 30 days of cover after delivery. '
            'Batch stock is considered expiring when remaining life is 14 days or less. Shelf life starts at assumed delivery. Supplier rating does not affect this example.')
        if hasattr(self, 'scene'):
            live = self.preview_values(); self.scene.live = live
            for node in self.scene.nodes.values(): node.set_text(node.data['text'])
    def fit(self):
        self.view.fitInView(self.scene.sceneRect(),Qt.KeepAspectRatio)
    def add_node(self):
        text,ok=QInputDialog.getMultiLineText(self,'Add step','Step text:')
        if not ok or not text.strip(): return
        import uuid
        p=self.view.mapToScene(self.view.viewport().rect().center())
        self.graph['nodes'].append(dict(id=uuid.uuid4().hex,text=text.strip(),x=p.x(),y=p.y(),group=self.group.currentText(),shape='process')); self.refresh()
    def connect_nodes(self):
        nodes=self.scene.selected_nodes()
        if len(nodes)!=2: QMessageBox.information(self,'Connect','Select exactly two steps using Ctrl+click.'); return
        names=[n.data['text'] for n in nodes]
        direction,ok=QInputDialog.getItem(self,'Connection direction','From → to:',[f'{names[0]} → {names[1]}',f'{names[1]} → {names[0]}'],0,False)
        if not ok:return
        edge=[nodes[0].data['id'],nodes[1].data['id']] if direction.startswith(names[0]+' → ') else [nodes[1].data['id'],nodes[0].data['id']]
        if edge not in self.graph['edges']: self.graph['edges'].append(edge); self.scene.update_edges()
    def remove_connection(self):
        nodes=self.scene.selected_nodes()
        if len(nodes)!=2: QMessageBox.information(self,'Remove connection','Select exactly two connected steps using Ctrl+click.'); return
        ids={n.data['id'] for n in nodes}
        candidates=[e for e in self.graph['edges'] if set(e)==ids]
        if not candidates: QMessageBox.information(self,'Remove connection','No connection exists between the selected steps.'); return
        labels=[self.scene.nodes[e[0]].data['text']+' → '+self.scene.nodes[e[1]].data['text'] for e in candidates]
        choice,ok=QInputDialog.getItem(self,'Remove connection','Choose connection:',labels,0,False)
        if ok: self.graph['edges'].remove(candidates[labels.index(choice)]); self.scene.update_edges()
    def delete_nodes(self):
        ids={n.data['id'] for n in self.scene.selected_nodes()}
        if not ids: return
        self.graph['nodes'][:]=[n for n in self.graph['nodes'] if n['id'] not in ids]
        self.graph['edges'][:]=[e for e in self.graph['edges'] if not ids.intersection(e)]; self.refresh()
    def save(self):
        if not self.path: return self.save_as()
        try: Path(self.path).write_text(json.dumps(self.graph,indent=2,ensure_ascii=False),encoding='utf-8'); self.statusBar().showMessage('Saved '+self.path,5000)
        except OSError as e: QMessageBox.warning(self,'Save failed',str(e))
    def save_as(self):
        path,_=QFileDialog.getSaveFileName(self,'Save flowchart','','JSON files (*.json)')
        if path: self.path=path; self.save()
    def open_file(self):
        path,_=QFileDialog.getOpenFileName(self,'Open flowchart','','JSON files (*.json)')
        if not path:return
        try:
            graph=json.loads(Path(path).read_text(encoding='utf-8'))
            if not isinstance(graph,dict) or not isinstance(graph.get('nodes'),list) or not isinstance(graph.get('edges'),list): raise ValueError('Invalid flowchart format')
            ids=set()
            for n in graph['nodes']:
                if not isinstance(n,dict) or not all(k in n for k in ('id','text','x','y','group')) or n['id'] in ids or n['group'] not in ('Operations','Sorting & recommendation') or not isinstance(n['text'],str) or not isinstance(n['x'],(int,float)) or not isinstance(n['y'],(int,float)): raise ValueError('Invalid node')
                ids.add(n['id'])
            if any(not isinstance(e,list) or len(e)!=2 or e[0] not in ids or e[1] not in ids for e in graph['edges']): raise ValueError('Invalid connection')
            self.graph=graph; self.path=path; self.refresh()
        except (OSError,ValueError,TypeError,KeyError) as e: QMessageBox.warning(self,'Open failed',str(e))
    def reset(self):
        if QMessageBox.question(self,'Reset','Discard the current diagram and restore the original?')==QMessageBox.Yes:
            self.graph=initial_graph(); self.path=None; self.refresh()

def main():
    app=QApplication(sys.argv); window=Window(); window.show(); sys.exit(app.exec())
if __name__=='__main__': main()

