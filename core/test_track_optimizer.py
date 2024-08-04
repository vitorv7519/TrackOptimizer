import sys
import os
import unittest
from PyQt5.QtWidgets import QApplication
from qgis.core import QgsFeature, QgsGeometry, QgsPointXY, QgsField, QgsVectorLayer, QgsProject
from qgis.PyQt.QtCore import QVariant
from main_window import TrackOptimizerDialog

class TestTrackOptimizer(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        """Set up the test environment."""
        cls.app = QApplication(sys.argv)
        cls.dialog = TrackOptimizerDialog()
        cls.layer = QgsVectorLayer("Point?crs=EPSG:4326", "test_layer", "memory")
        cls.layer.dataProvider().addAttributes([
            QgsField("id", QVariant.Int),
            QgsField("timestamp", QVariant.String)
        ])
        cls.layer.updateFields()

        # Add test features to the layer
        cls.add_feature(1, "2024-07-30T12:00:00", 12.0, 50.0)
        cls.add_feature(1, "2024-07-30T12:05:00", 13.0, 51.0)
        cls.add_feature(1, "2024-07-30T12:10:00", 14.0, 52.0)
        cls.add_feature(2, "2024-07-30T12:15:00", 15.0, 53.0)
        cls.add_feature(2, "2024-07-30T12:20:00", 16.0, 54.0)

        QgsProject.instance().addMapLayer(cls.layer)

    @classmethod
    def add_feature(cls, feature_id, timestamp, x, y):
        """Add a feature to the layer."""
        feature = QgsFeature(cls.layer.fields())
        feature.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(x, y)))
        feature.setAttributes([feature_id, timestamp])
        cls.layer.dataProvider().addFeature(feature)

    def test_calculate_median_value(self):
        """Test the calculate_median_value function."""
        features = list(self.layer.getFeatures())
        median_value = self.dialog.calculate_median_value(features, "id")
        self.assertEqual(median_value, 1)

    def test_sort_features_by_timestamp(self):
        features = list(self.layer.getFeatures())
        sorted_features = self.dialog.sort_features_by_timestamp(features, "timestamp")
        self.assertEqual(sorted_features[0]["timestamp"], "2024-07-30T12:00:00")
        self.assertEqual(sorted_features[-1]["timestamp"], "2024-07-30T12:20:00")

    def test_get_ids_to_delete(self):
        features = list(self.layer.getFeatures())
        sorted_features = self.dialog.sort_features_by_timestamp(features, "timestamp")
        median_value = self.dialog.calculate_median_value(features, "id")
        self.dialog.tolerance_value = 10
        
        ids_to_delete = self.dialog.get_ids_to_delete(sorted_features, "timestamp", "id", median_value)
        self.assertEqual(ids_to_delete, [])

    def test_delete_features(self):
        features = list(self.layer.getFeatures())
        sorted_features = self.dialog.sort_features_by_timestamp(features, "timestamp")
        median_value = self.dialog.calculate_median_value(features, "id")
        self.dialog.tolerance_value = 10
        
        ids_to_delete = self.dialog.get_ids_to_delete(sorted_features, "timestamp", "id", median_value)
        self.dialog.delete_features(self.layer, ids_to_delete)
        
        remaining_features = [f for f in self.layer.getFeatures()]
        self.assertEqual(len(remaining_features), 5)

if __name__ == '__main__':
    unittest.main()
