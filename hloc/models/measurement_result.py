#!/usr/bin/env python3
"""
 * All measurement result classes used by the HLOC framework
"""

import enum
import datetime
import sqlalchemy as sqla
import sqlalchemy.orm as sqlorm
from sqlalchemy.dialects import postgresql


from hloc.models.sql_alchemy_base import Base
from .enums import MeasurementError


class MeasurementResult(Base):
    """the abstract base class for a measurement result"""

    __tablename__ = 'measurement_results'

    id = sqla.Column(sqla.Integer, primary_key=True)
    probe_id = sqla.Column(sqla.Integer, sqla.ForeignKey('probes.id'), nullable=False)
    execution_time = sqla.Column(sqla.DateTime, nullable=False)
    destination_address = sqla.Column(postgresql.INET, nullable=False)
    source_address = sqla.Column(postgresql.INET)
    error_msg = sqla.Column(postgresql.ENUM(MeasurementError))
    rtts = sqla.Column(postgresql.ARRAY(sqla.Float), nullable=False)
    # eventually save ttl if there?

    probe = sqlorm.relationship('Probe', back_populates='measurements')

    measurement_result_type = sqla.Column(sqla.String)

    __mapper_args__ = {'polymorphic_on': measurement_result_type,
                       'polymorphic_identity': 'employee'}

    def __init__(self, **kwargs):
        self.rtts = []

        for name, value in kwargs.items():
            setattr(self, name, value)

        super().__init__()

    @property
    def min_rtt(self):
        return min(self.rtts) if self.rtts else None


class RipeMeasurementResult(MeasurementResult):
    __mapper_args__ = {
        'polymorphic_identity': 'manager'
    }

    class RipeMeasurementResultKey(enum.Enum):
        destination_addr = 'dest_addr'
        source_addr = 'src_addr'
        rtt_dicts = 'result'
        rtt = 'rtt'
        execution_time = 'timestamp'

    ripe_id = sqla.Column(sqla.Integer)

    @staticmethod
    def create_from_dict(ripe_result_dict):
        """
        
        :param ripe_result_dict: the measurement dict from ripe.atlas.cousteau.AtlasResultsRequest  
                                 return value
        :return (RipeMeasurementResult): Our MeasurementResult object
        """
        measurement_result = RipeMeasurementResult()
        measurement_result.destination_address = \
            ripe_result_dict[RipeMeasurementResult.RipeMeasurementResultKey.destination_addr.value]
        measurement_result.source_address = \
            ripe_result_dict[RipeMeasurementResult.RipeMeasurementResultKey.source_addr.value]
        rtts = []
        for ping in measurement_result[
                           RipeMeasurementResult.RipeMeasurementResultKey.rtt_dicts.value]:
            rtt_value = ping.get(RipeMeasurementResult.RipeMeasurementResultKey.rtt.value, None)
            if rtt_value:
                try:
                    rtts.append(float(rtt_value))
                except ValueError:
                    continue

        measurement_result.rtts = rtts
        if not rtts:
            measurement_result.error_msg = MeasurementError.not_reachable

        measurement_result.execution_time = datetime.datetime.fromtimestamp(
            ripe_result_dict[RipeMeasurementResult.RipeMeasurementResultKey.execution_time.value])

        return measurement_result


__all__ = ['MeasurementResult'
           ]
