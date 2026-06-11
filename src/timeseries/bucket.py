"""
Logic for combining TimeSeries objects into buckets.
"""

from timeseries.base import TimeSeries, TimePoints, BucketConfig    
from pydantic import BaseModel
from abc import ABC, abstractmethod
from pydantic import ConfigDict
from pydantic import PrivateAttr
from enum import Enum
from functools import cached_property
import numpy as np
from decimal import Decimal



class MultiplierMatrix(BaseModel):
    src_time_points: TimePoints
    target_time_points: TimePoints
    bucket_config: BucketConfig

    @cached_property
    def multiplier_matrix(self) -> np.ndarray:
        """
        This is where the tricky logic re: BucketConfig happens
        """
        src_intervals = self.src_time_points.get_intervals(self.bucket_config)
        target_intervals = self.target_time_points.get_intervals(self.bucket_config)
        # TODO:
    def apply_to_values(self, values: list[float | int | Decimal]) -> list[float | int | Decimal]:
        #TODO: Implement this
        matrix = self.multiplier_matrix
        return np.dot(matrix, values)
            
class Bucketer(BaseModel):

    model_config = ConfigDict(arbitrary_types_allowed=True)
    _transformation_dict: dict[(BucketConfig, TimePoints), MultiplierMatrix] = PrivateAttr()
    target_time_points: TimePoints

    def _get_multiplier_matrix(self, time_series: TimeSeries) -> MultiplierMatrix:
        previous_matrix = self._get_from_dict(time_series.bucketing_hash)
        if previous_matrix is not None:
            return previous_matrix
        else:
            new_matrix = self.MultiplierMatrix(src_time_points=time_series.time_points, target_time_points=self.target_time_points, bucket_config=time_series.bucket_config)
            self._add_to_dict(time_series.bucketing_hash, new_matrix)
            return new_matrix

    def get_bucketed_time_series(self, time_series: TimeSeries) -> TimeSeries:
        return time_series.get_copy_with_new_time_and_values(
            new_time_points=self.target_time_points, 
            new_values=self._get_multiplier_matrix(time_series).apply_to_values(time_series.values))
   
    def _get_from_dict(self, bucketing_hash: str) -> TimePoints:
        return self._transformation_dict.get(bucketing_hash, None)

    def _add_to_dict(self, bucketing_hash: str, transformed_time_points: TimePoints) -> None:
        if bucketing_hash in self._transformation_dict:
            raise ValueError(f"Time points already in transformation dictionary. bucket_config: {bucket_config}, time_points: {time_points}")
        else:
            self._transformation_dict[bucketing_hash] = transformed_time_points

    