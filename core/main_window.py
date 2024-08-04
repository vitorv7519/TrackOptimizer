from .draw_track_line_tool import DrawGpsTrackLineTool
import geopandas as gpd
import os

from qgis.PyQt import uic
from qgis.PyQt import QtWidgets
from qgis.core import QgsFeatureRequest, QgsGeometry, QgsPointXY, QgsProject, QgsSpatialIndex
from qgis.core import QgsDistanceArea, QgsWkbTypes, QgsVectorLayer, QgsFeature, QgsUnitTypes,  QgsPoint
from qgis.core import QgsProject, QgsDistanceArea, QgsCoordinateTransform, QgsCoordinateReferenceSystem
from PyQt5.QtWidgets import QDialog
from PyQt5.QtCore import QDateTime, Qt, QTimer
from qgis.utils import iface
from qgis.gui import QgsRubberBand
from PyQt5.QtGui import QIcon
from shapely.geometry import LineString

FORM_CLASS, _ = uic.loadUiType(os.path.join(
    os.path.dirname(__file__), 'ui', 'main_window.ui'))

class TrackOptimizerDialog(QtWidgets.QDialog, FORM_CLASS):
    def __init__(self, parent=None):
        """Constructor."""
        super(TrackOptimizerDialog, self).__init__(parent)
        self.setupUi(self)
        
        self.pathAlignmentTrackLayer.layerChanged.connect(self.on_track_layer_changed)
        self.pathAlignmentLineLayer.layerChanged.connect(self.on_align_layer_changed)
        self.pathAlignmentSpinBox.valueChanged.connect(self.on_align_spin_box_changed)
        self.pathAlignmentCorrectButton.clicked.connect(self.alignment_correct)
        self.pathAlignmentErrorsButton.clicked.connect(self.alignment_errors)
        self.pathAlignmentRemoveAnomalies.clicked.connect(self.alignment_remove)
        self.drawLineLayerButton.setIcon(QIcon(":/plugins/track_optimizer/trackOptimizerIcon.png"))
        self.drawLineLayerButton.clicked.connect(self.draw_line_layer)
        self.douglasPeuckerButton.clicked.connect(self.run_douglas_peucker)
        self.canvas = iface.mapCanvas()
        self.DrawGpsTrackLineTool = DrawGpsTrackLineTool(self.canvas)

        self.initialize_main_dialog()
        
        self.rubber_band = QgsRubberBand(iface.mapCanvas(), QgsWkbTypes.PolygonGeometry)

    def initialize_main_dialog(self):
        self.set_initial_fields()
        self.set_tooltips()
        self.toleranceSpinBox.setMinimum(0.00001)
        self.toleranceSpinBox.setValue(0.01)
    
    def set_initial_fields(self):
        self.trackLayer = self.pathAlignmentTrackLayer.currentLayer()
        if self.trackLayer:
            self.pathAlignmentTimestampField.setLayer(self.trackLayer)
        self.lineLayer = self.pathAlignmentLineLayer.currentLayer()
        self.domainValue = float(self.pathAlignmentSpinBox.value())  / 100000
        
    def set_tooltips(self):
        self.pathAlignmentTrackLayer.setToolTip("Select map layer that contains trajectory data.")
        self.pathAlignmentTimestampField.setToolTip("Select field that contains timestamp information of GPS data.")
        self.pathAlignmentSpinBox.setToolTip("Adjust domain range.")
        self.pathAlignmentCorrectButton.setToolTip("Put points out of range back within, retracing in opposite direction formed concerning previous point.")
        self.pathAlignmentErrorsButton.setToolTip("Identify and highlight points beyond domain range.")
        self.pathAlignmentRemoveAnomalies.setToolTip("Remove anomaly points.")
        self.drawLineLayerButton.setToolTip("Draw the selected line layer.")
        self.douglasPeuckerButton.setToolTip("Run the Douglas-Peucker simplification algorithm.")
    
    def on_align_layer_changed(self, layer):
        self.lineLayer = layer
        
    def on_track_layer_changed(self, layer):
        self.trackLayer = layer
        self.pathAlignmentTimestampField.setLayer(layer)
        
    def on_align_spin_box_changed(self, value):
        self.domainValue = float(value)  / 100000
        self.draw_domain_range(self.domainValue)

    def alignment_correct(self):
        self.process_points_and_line(self.trackLayer, self.lineLayer, self.pathAlignmentTimestampField.currentField(), self.domainValue)
        
    def alignment_errors(self):
        if self.trackLayer and self.lineLayer and self.domainValue:
            within_range_features = self.points_within_range(self.trackLayer, self.lineLayer, self.domainValue)
            out_of_range_ids = [feature.id() for feature in self.trackLayer.getFeatures() if feature not in within_range_features]
            if out_of_range_ids:
                self.trackLayer.selectByIds(out_of_range_ids)
        
    def alignment_remove(self):
        self.trackLayer.startEditing()
        selected_features = self.trackLayer.selectedFeatures()
        if selected_features:
            for feature in selected_features:
                self.trackLayer.deleteFeature(feature.id())

            if self.trackLayer.isEditable():
                self.trackLayer.commitChanges()
                
            self.trackLayer.triggerRepaint()

    def draw_line_layer(self):
        canvas = iface.mapCanvas()
        if self.drawLineLayerButton.isChecked():
            self.drawLineLayerButton.setChecked(False)
            canvas.unsetMapTool(self.DrawGpsTrackLineTool)
        else:
            self.drawLineLayerButton.setChecked(True)
            canvas.setMapTool(self.DrawGpsTrackLineTool)
        
        self.drawLineLayerButton.setEnabled(not self.drawLineLayerButton.isChecked())
        canvas.refresh()

    def load_layers(self):
        layers = QgsProject.instance().mapLayers().values()
        for layer in layers:
            self.pathAlignmentTrackLayer.addItem(layer.name(), layer)

    def run_douglas_peucker(self):
        tolerance = float(self.toleranceSpinBox.value())
        path_layer = self.pathAlignmentTrackLayer.currentLayer()

        if not path_layer:
            return

        fields = path_layer.fields()
        simplified_layer = QgsVectorLayer(f"LineString?crs={path_layer.crs().authid()}", "Douglas-Peucker Line", "memory")
        simplified_layer_data = simplified_layer.dataProvider()
        simplified_layer_data.addAttributes(fields)
        simplified_layer.updateFields()

        features = path_layer.getFeatures()
        points = []

        for feat in features:
            geom = feat.geometry()
            points.append((geom.asPoint().x(), geom.asPoint().y()))

        if len(points) < 2:
            return

        simplified_line = self.simplify_trajectory(points, tolerance)

        simplified_geom = QgsGeometry.fromWkt(simplified_line.wkt)
        new_feature = QgsFeature()
        new_feature.setGeometry(simplified_geom)
        new_feature.setAttributes([None] * len(fields))

        simplified_layer.startEditing()
        simplified_layer.addFeature(new_feature)
        simplified_layer.commitChanges()
        simplified_layer.updateExtents()

        QgsProject.instance().addMapLayer(simplified_layer)

    def simplify_trajectory(self, points, tolerance):
        line = LineString(points)
        return line.simplify(tolerance, preserve_topology=False)

    def draw_domain_range(self, max_distance):
        self.rubber_band.reset(QgsWkbTypes.PolygonGeometry)
        
        line_layer = self.pathAlignmentLineLayer.currentLayer()
        if not line_layer or line_layer.geometryType() != QgsWkbTypes.LineGeometry:
            return

        buffer_features = []
        for line_feature in line_layer.getFeatures():
            line_geom = line_feature.geometry()
            buffer_geom = line_geom.buffer(max_distance, 5)
            buffer_features.append(buffer_geom)

        for geom in buffer_features:
            self.rubber_band.addGeometry(geom, None)
        
        iface.mapCanvas().refresh()
        
        def remove_rubber_band():
            self.rubber_band.reset(QgsWkbTypes.PolygonGeometry)
            iface.mapCanvas().refresh()

        QTimer.singleShot(10000, remove_rubber_band)
        
    def points_within_range(self, point_layer, line_layer, domain_range):
        crs = point_layer.crs()
        if crs != line_layer.crs():
            line_layer.setCrs(crs)

        points_within_range = []

        for point_feature in point_layer.getFeatures():
            point_geom = point_feature.geometry()

            for line_feature in line_layer.getFeatures():
                line_geom = line_feature.geometry()
                
                buffer_geom = line_geom.buffer(domain_range, 5)

                if buffer_geom.contains(point_geom):
                    points_within_range.append(point_feature)
                    break

        return points_within_range

    def process_points_and_line(self, point_layer, line_layer, timestamp_field, domain_range):
        if line_layer.featureCount() != 1:
            return

        crs = point_layer.crs()
        if crs != line_layer.crs():
            line_layer.setCrs(crs)

        order_by = QgsFeatureRequest.OrderBy([QgsFeatureRequest.OrderByClause(timestamp_field, ascending=True)])
        request = QgsFeatureRequest().setOrderBy(order_by)
        points = [feature for feature in point_layer.getFeatures(request)]

        if len(points) < 2:
            return

        start_point = points[0]
        end_point = points[-1]

        line_feature = next(line_layer.getFeatures())
        line_geom = line_feature.geometry()

        if domain_range <= 0:
            return

        points_within = self.points_within_range(point_layer, line_layer, domain_range)
        points_outside = [point for point in points if point.id() not in [p.id() for p in points_within]]

        point_layer.startEditing()

        t1 = start_point[timestamp_field].toSecsSinceEpoch()
        t2 = end_point[timestamp_field].toSecsSinceEpoch()
        for point_feature in points_outside:
            old_geom = point_feature.geometry()
            old_point = old_geom.constGet()
            timestamp = point_feature[timestamp_field].toSecsSinceEpoch()

            if timestamp < t1:
                new_x = start_point.geometry().constGet().x()
                new_y = start_point.geometry().constGet().y()
            elif timestamp > t2:
                new_x = end_point.geometry().constGet().x()
                new_y = end_point.geometry().constGet().y()
            else:
                for i in range(line_geom.constGet().numPoints() - 1):
                    p1 = line_geom.constGet().pointN(i)
                    p2 = line_geom.constGet().pointN(i + 1)
                    if t1 <= timestamp <= t2:
                        ratio = (timestamp - t1) / (t2 - t1)
                        new_x = p1.x() + ratio * (p2.x() - p1.x())
                        new_y = p1.y() + ratio * (p2.y() - p1.y())
                        break

            new_z = old_point.z()
            new_geom = QgsGeometry.fromPoint(QgsPoint(new_x, new_y, new_z))
            
            point_feature.setGeometry(new_geom)
            point_layer.updateFeature(point_feature)

        if point_layer.isEditable():
            point_layer.commitChanges()