from qgis.PyQt.QtCore import Qt
from qgis.core import QgsProject, QgsVectorLayer, QgsFeature, QgsGeometry, QgsPointXY, QgsWkbTypes, QgsSimpleLineSymbolLayer
from qgis.gui import QgsMapTool, QgsRubberBand

class DrawGpsTrackLineTool(QgsMapTool):
    def __init__(self, canvas):
        super().__init__(canvas)
        self.canvas = canvas
        self.rubberBand = QgsRubberBand(self.canvas, QgsWkbTypes.LineGeometry)
        self.rubberBand.setColor(Qt.red)
        self.rubberBand.setWidth(2)
        self.tempRubberBand = QgsRubberBand(self.canvas, QgsWkbTypes.LineGeometry)
        self.tempRubberBand.setColor(Qt.blue)
        self.tempRubberBand.setWidth(1)
        self.points = []
        self.is_draw_tool_active = False

    def setLayerSymbol(self, layer):
        symbol = layer.renderer().symbol()
        symbol_layer = QgsSimpleLineSymbolLayer()
        symbol_layer.setWidth(1)
        symbol_layer.setColor(Qt.blue)
        symbol.changeSymbolLayer(0, symbol_layer)
        layer.triggerRepaint()

    def canvasPressEvent(self, event):
        point = self.toMapCoordinates(event.pos())
        self.points.append(QgsPointXY(point))
        self.rubberBand.addPoint(point, True)
        self.rubberBand.show()
        self.tempRubberBand.reset()

    def canvasMoveEvent(self, event):
        if not self.points:
            return
        point = self.toMapCoordinates(event.pos())
        self.tempRubberBand.reset()
        for p in self.points:
            self.tempRubberBand.addPoint(p, False)
        self.tempRubberBand.addPoint(point, True)
        self.tempRubberBand.show()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Return:
            self.finishDrawing()
        elif event.key() == Qt.Key_Escape:
            self.cancelDrawing()

    def finishDrawing(self):
        if len(self.points) > 1:
            layer_name = "GPS Track Line"
            project = QgsProject.instance()
            existing_layer = project.mapLayersByName(layer_name)
            
            if existing_layer:
                project.removeMapLayer(existing_layer[0])

            temp_layer = QgsVectorLayer("LineString?crs=EPSG:4326", layer_name, "memory")
            self.setLayerSymbol(temp_layer)
            project.addMapLayer(temp_layer)

            feature = QgsFeature()
            geom = QgsGeometry.fromPolylineXY(self.points)
            feature.setGeometry(geom)
            
            temp_layer.startEditing()
            temp_layer.dataProvider().addFeature(feature)
            temp_layer.commitChanges()
            temp_layer.updateExtents()
            self.canvas.refresh()

        self.rubberBand.reset()
        self.tempRubberBand.reset()
        self.points = []

    def cancelDrawing(self):
        self.deactivate()

    def deactivate(self):
        self.rubberBand.reset()
        self.tempRubberBand.reset()
        self.points = []
        self.canvas.unsetMapTool(self)
