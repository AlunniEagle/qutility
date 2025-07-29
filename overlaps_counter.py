"""
Model exported as python.
Name : num_cavi_su_infrastruttua
Group : Script personalizzati
With QGIS : 32809
"""

from qgis.core import QgsProcessing
from qgis.core import QgsProcessingAlgorithm
from qgis.core import QgsProcessingMultiStepFeedback
from qgis.core import QgsProcessingParameterFeatureSource
from qgis.core import QgsProcessingParameterFeatureSink
import processing


class Num_cavi_su_infrastruttua(QgsProcessingAlgorithm):

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterFeatureSource('cavi_4326', 'CAVI (4326)', types=[QgsProcessing.TypeVectorLine], defaultValue=None))
        self.addParameter(QgsProcessingParameterFeatureSource('infrastruttura_4326', 'INFRASTRUTTURA (4326)', types=[QgsProcessing.TypeVectorLine], defaultValue=None))
        self.addParameter(QgsProcessingParameterFeatureSink('InfrastrutturaConNcavi', 'INFRASTRUTTURA CON NCAVI', type=QgsProcessing.TypeVectorAnyGeometry, createByDefault=True, supportsAppend=True, defaultValue=None))

    def processAlgorithm(self, parameters, context, model_feedback):
        # Use a multi-step feedback, so that individual child algorithm progress reports are adjusted for the
        # overall progress through the model
        feedback = QgsProcessingMultiStepFeedback(7, model_feedback)
        results = {}
        outputs = {}

        # Buffer cavi
        alg_params = {
            'DISSOLVE': False,
            'DISTANCE': 1e-07,
            'END_CAP_STYLE': 0,  # Arrotondato
            'INPUT': parameters['cavi_4326'],
            'JOIN_STYLE': 0,  # Arrotondato
            'MITER_LIMIT': 2,
            'SEGMENTS': 5,
            'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
        }
        outputs['BufferCavi'] = processing.run('native:buffer', alg_params, context=context, feedback=feedback, is_child_algorithm=True)

        feedback.setCurrentStep(1)
        if feedback.isCanceled():
            return {}

        # ID progressivo cavi
        alg_params = {
            'FIELD_LENGTH': 10,
            'FIELD_NAME': 'id_cav',
            'FIELD_PRECISION': 0,
            'FIELD_TYPE': 1,  # Intero (32 bit)
            'FORMULA': '@row_number',
            'INPUT': outputs['BufferCavi']['OUTPUT'],
            'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
        }
        outputs['IdProgressivoCavi'] = processing.run('native:fieldcalculator', alg_params, context=context, feedback=feedback, is_child_algorithm=True)

        feedback.setCurrentStep(2)
        if feedback.isCanceled():
            return {}

        # Ripara geometrie infrastruttura
        alg_params = {
            'INPUT': parameters['infrastruttura_4326'],
            'METHOD': 1,  # Struttura
            'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
        }
        outputs['RiparaGeometrieInfrastruttura'] = processing.run('native:fixgeometries', alg_params, context=context, feedback=feedback, is_child_algorithm=True)

        feedback.setCurrentStep(3)
        if feedback.isCanceled():
            return {}

        # ID progressivo infrastruttura
        alg_params = {
            'FIELD_LENGTH': 10,
            'FIELD_NAME': 'id_infr',
            'FIELD_PRECISION': 0,
            'FIELD_TYPE': 1,  # Intero (32 bit)
            'FORMULA': '@row_number',
            'INPUT': outputs['RiparaGeometrieInfrastruttura']['OUTPUT'],
            'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
        }
        outputs['IdProgressivoInfrastruttura'] = processing.run('native:fieldcalculator', alg_params, context=context, feedback=feedback, is_child_algorithm=True)

        feedback.setCurrentStep(4)
        if feedback.isCanceled():
            return {}

        # Associa id_cav sull'infrastruttura
        alg_params = {
            'DISCARD_NONMATCHING': False,
            'INPUT': outputs['IdProgressivoInfrastruttura']['OUTPUT'],
            'JOIN': outputs['IdProgressivoCavi']['OUTPUT'],
            'JOIN_FIELDS': ['id_cav'],
            'METHOD': 0,  # Crea elementi separati per ciascun elemento corrispondente (uno-a-molti)
            'PREDICATE': [1,5,4],  # contiene,sono contenuti,sovrappone
            'PREFIX': '',
            'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
        }
        outputs['AssociaId_cavSullinfrastruttura'] = processing.run('native:joinattributesbylocation', alg_params, context=context, feedback=feedback, is_child_algorithm=True)

        feedback.setCurrentStep(5)
        if feedback.isCanceled():
            return {}

        # Aggrega per id dell'infrastruttura
        alg_params = {
            'AGGREGATES': [{'aggregate': 'first_value','delimiter': ',','input': '"id_infr"','length': 20,'name': 'id_layer1','precision': 0,'sub_type': 0,'type': 6,'type_name': 'double precision'},{'aggregate': 'concatenate','delimiter': ',','input': 'to_string("id_cav")','length': 254,'name': 'id_layer2','precision': 0,'sub_type': 0,'type': 10,'type_name': 'text'}],
            'GROUP_BY': 'id_infr',
            'INPUT': outputs['AssociaId_cavSullinfrastruttura']['OUTPUT'],
            'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
        }
        outputs['AggregaPerIdDellinfrastruttura'] = processing.run('native:aggregate', alg_params, context=context, feedback=feedback, is_child_algorithm=True)

        feedback.setCurrentStep(6)
        if feedback.isCanceled():
            return {}

        # Campo numero cavi sovrapposti
        alg_params = {
            'FIELD_LENGTH': 10,
            'FIELD_NAME': 'n_overlaps',
            'FIELD_PRECISION': 0,
            'FIELD_TYPE': 1,  # Intero (32 bit)
            'FORMULA': 'array_length(string_to_array("id_layer2", \',\'))',
            'INPUT': outputs['AggregaPerIdDellinfrastruttura']['OUTPUT'],
            'OUTPUT': parameters['InfrastrutturaConNcavi']
        }
        outputs['CampoNumeroCaviSovrapposti'] = processing.run('native:fieldcalculator', alg_params, context=context, feedback=feedback, is_child_algorithm=True)
        results['InfrastrutturaConNcavi'] = outputs['CampoNumeroCaviSovrapposti']['OUTPUT']
        return results

    def name(self):
        return 'num_cavi_su_infrastruttura'

    def displayName(self):
        return 'num_cavi_su_infrastruttura'

    def group(self):
        return 'Script personalizzati'

    def groupId(self):
        return 'script_personalizzati'

    def shortHelpString(self):
        return """<html><body><p><!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 4.0//EN" "http://www.w3.org/TR/REC-html40/strict.dtd">
<html><head><meta name="qrichtext" content="1" /><style type="text/css">
p, li { white-space: pre-wrap; }
</style></head><body style=" font-family:'MS Shell Dlg 2'; font-size:9pt; font-weight:400; font-style:normal;">
<p style="-qt-paragraph-type:empty; margin-top:0px; margin-bottom:0px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px;"><br /></p></body></html></p>
<br><p align="right">Autore algoritmo: mpeppucci</p></body></html>"""

    def createInstance(self):
        return Num_cavi_su_infrastruttua()
