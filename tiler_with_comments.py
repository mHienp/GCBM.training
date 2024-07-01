import os  # interact with the operating system and file directory
import logging  # log event messages at levels of severity
import sys  
from glob import glob  # glob(al) module finds pathnames matching a pattern
from collections import OrderedDict  # remembers the order in which items were added in dictionaries

# mojadata module
from mojadata.boundingbox import BoundingBox  
from mojadata.cleanup import cleanup  
from mojadata.gdaltiler2d import GdalTiler2D  
from mojadata.compressingtiler3d import CompressingTiler3D  
from mojadata.layer.vectorlayer import VectorLayer  
from mojadata.layer.rasterlayer import RasterLayer  
from mojadata.layer.gcbm.disturbancelayer import DisturbanceLayer  
from mojadata.layer.regularstacklayer import RegularStackLayer  
from mojadata.layer.attribute import Attribute  
from mojadata.layer.gcbm.transitionrule import TransitionRule  
from mojadata.layer.gcbm.transitionrulemanager import SharedTransitionRuleManager  
from mojadata.layer.filter.valuefilter import ValueFilter  
from mojadata.util import gdal  
from mojadata.util.gdalhelper import GDALHelper  

if __name__ == "__main__":  # code only runs if script is executed directly

    # Logs INFO+ messages to tiler_log.txt, overwrites file, format: MM/DD HH:MM:SS message
    logging.basicConfig(level=logging.INFO, filename=r"..\..\logs\tiler_log.txt", filemode="w",
                        format="%(asctime)s %(message)s", datefmt="%m/%d %H:%M:%S")  

    mgr = SharedTransitionRuleManager()  # mojadata.layer.gcbm.transitionrulemanager
    mgr.start()  
    rule_manager = mgr.TransitionRuleManager()  

    with cleanup():  # mojadata.cleanup
        
        layer_root = os.path.join("..", "raw")  # layers\raw

        '''
        Define the bounding box of the simulation - all layers will be reprojected, cropped, and
        resampled to the bounding box area. The bounding box layer can be filtered by an attribute
        value to simulate a specific area.
        '''
        bbox = BoundingBox( # mojadata.boundingbox
            VectorLayer( # mojadata.layer.vectorlayer
                "bbox",
                os.path.join(layer_root, "inventory", "inventory.shp"), # layers\raw\inventory\inventory.shp
                Attribute("PolyID")),  # column PolyID of inventory.shp
            pixel_size=0.00025)  # pixel size for bounding box

        tiler = GdalTiler2D(bbox, use_bounding_box_resolution=True)  # mojadata.gdaltiler2d

        '''
        Classifier layers link pixels to yield curves.
          - the names of the classifier layers must match the classifier names in the GCBM input database
          - tags=[classifier_tag] ensures that classifier layers are automatically added to the GCBM
            configuration file
        '''
        classifier_tag = "classifier" 
        reporting_classifier_tag = "reporting_classifier"  

        classifier_layers = [
            VectorLayer("Classifier1", os.path.join(layer_root, "inventory", "inventory.shp"), Attribute("Classifer1"), tags=[classifier_tag]),  # column Classifer1 of inventory.shp
            VectorLayer("Classifier2", os.path.join(layer_root, "inventory", "inventory.shp"), Attribute("Classifer2"), tags=[classifier_tag]),  # column Classifer2 of inventory.shp
        ]

        # Set up default transition rule for disturbance events: preserve existing stand classifiers.
        no_classifier_transition = OrderedDict(zip((c.name for c in classifier_layers), "?" * len(classifier_layers)))  

        layers = [
            # Age - layer name must be "initial_age" so that the script can update the GCBM configuration file.
            VectorLayer("initial_age", os.path.join(layer_root, "inventory", "inventory.shp"), Attribute("AGE_2010"),
                        data_type=gdal.GDT_Int16, raw=True),  # column AGE_2010 of inventory.shp. datatype int

            # Temperature - layer name must be "mean_annual_temperature" so that the scripts can
            # update the GCBM configuration file.
            VectorLayer("mean_annual_temperature",
                        os.path.join(layer_root, "inventory", "inventory.shp"), Attribute("AnnualTemp"),
                        data_type=gdal.GDT_Float32, raw=True),  # column AnnualTemp of inventory.shp, datatype float
        ] + classifier_layers  # Add classifier layers to layers list

        # Disturbances
        for year in range(2010, 2020):  # Loop through years 2010-2019
            layers.append(DisturbanceLayer(
                rule_manager,
                VectorLayer("disturbances_{}".format(year),
                            os.path.join(layer_root, "disturbances", "disturbances.shp"), # layers\raw\disturbances\disturbances.shp
                            [
                                Attribute("year", filter=ValueFilter(year)),
                                Attribute("dist_type") # column dist_type of disturbances.shp
                            ]),  # Create a disturbance layer for each year
                year=Attribute("year"),  # column year of disturbances.shp
                disturbance_type=Attribute("dist_type"),  
                transition=TransitionRule(
                    regen_delay=0,
                    age_after=0,
                    classifiers=no_classifier_transition)))  # no transition

        tiler.tile(layers)  # Tile layers
        rule_manager.write_rules("transition_rules.csv")  # Write the transition rules to a CSV file
