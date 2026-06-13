from cashflow.models.base import BaseDataElement
import datetime
from decimal import Decimal
import pandas as pd
from pydantic import ConfigDict, computed_field, model_validator
from functools import cached_property
import hashlib
from enum import Enum
from pydantic import BaseModel
import numpy as np
class BucketConfig(BaseModel):
    class ArrearsAdvance(Enum):
        ADVANCE = "advance"
        ARREARS = "arrears"

    class CollapseSpreadPair(Enum):
        COLLAPSE_BY_SUM_SPREAD_BY_INTERPOLATE = "collapse_by_sum_spread_by_interpolate"
        COLLAPSE_BY_WEIGHTED_AVERAGE_SPREAD_BY_REPEAT = "collapse_by_weighted_average_spread_by_repeat"

    arrears_advance: ArrearsAdvance
    collapse_spread_pair: CollapseSpreadPair

    @cached_property
    def hash(self) -> str:
        return hashlib.sha256(str(self).encode()).hexdigest()

class Values(BaseDataElement):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    name: str = ""
    values: list[float | int | Decimal]

    def get_copy_with_new_values(self, new_values: list[float | int | Decimal]) -> 'Values':
        return Values(values=new_values, name=self.name)

    def __getitem__(self) -> list[float | int | Decimal]:
        return self.values

    @model_validator(mode="before")
    @classmethod
    def _validate(cls, data):
        values = data["values"] if isinstance(data, dict) else data
        if len({type(value) for value in values}) != 1:
            raise ValueError("values must be a list of the same type")
        if not all(isinstance(value, (float, int, Decimal)) for value in values):
            raise ValueError("values must be a list of float, int, or Decimal")
        return {"values": values}

    def __setitem__(self, index: int, value: float | int | Decimal) -> None:
        raise AttributeError("Values is immutable")

    def __delitem__(self, index: int) -> None:
        raise AttributeError("Values is immutable")

    def __len__(self) -> int:
        return len(self.values)


class TimePoints(BaseDataElement):
    class Periodicity(Enum):
        DAILY = "daily"
        MONTHLY = "monthly"
        QUARTERLY = "quarterly"
        YEARLY = "yearly"
        SEMIANNUAL = "semiannual"

    model_config = ConfigDict(arbitrary_types_allowed=True)
    name: str = ""
    dates: list[datetime.datetime]
    periodicity: Periodicity

    @cached_property
    def hash(self) -> str:
        """
        Already converted to datetime.datetime objects, so hash should be same regardless of input type.
        """
        return hashlib.sha256(str(self.dates).encode()).hexdigest()

    def __getitem__(self) -> list[datetime.datetime]:
        return self.dates

    @model_validator(mode="before")
    @classmethod
    def _validate(cls, data):
        dates = data["dates"] if isinstance(data, dict) else data
        if not dates:
            raise ValueError("dates must not be empty")
        if len({type(date) for date in dates}) != 1:
            raise ValueError("dates must be a list of the same type")

        first = dates[0]
        if isinstance(first, str):
            dates = [datetime.datetime.strptime(date, "%Y-%m-%d") for date in dates]
        elif isinstance(first, datetime.date) and not isinstance(first, datetime.datetime):
            dates = [datetime.datetime.combine(date, datetime.time.min) for date in dates]
        elif isinstance(first, pd.Timestamp):
            dates = [date.to_pydatetime() for date in dates]
        elif not isinstance(first, datetime.datetime):
            raise ValueError("dates must be str, date, datetime, or pd.Timestamp")

        if not all(date < date2 for date, date2 in zip(dates, dates[1:])):
            raise ValueError("dates must be in ascending order")
        return {"dates": dates}

    def __setitem__(self, index: int, value: datetime.datetime) -> None:
        raise AttributeError("TimePoints is immutable")

    def __delitem__(self, index: int) -> None:
        raise AttributeError("TimePoints is immutable")

    def __len__(self) -> int:
        return len(self.dates)

    def get_matrix_for_target_time_points(self, target_time_points: TimePoints, bucket_config: BucketConfig) -> np.ndarray:
        source_intervals = self._get_intervals(bucket_config)
        target_intervals = target_time_points._get_intervals(bucket_config)
        matrix = np.zeros((len(source_intervals), len(target_intervals)))
        # TODO: optimize for log(n) time complexity
        # TODO: validate actual results make sure orientation is correct
        for i in range(len(source_intervals)):
            for j in range(len(target_intervals)):
                overlap_days = max(
                     0, 
                     min(source_intervals[i][1], target_intervals[j][1]) - 
                         max(source_intervals[i][0], target_intervals[j][0]))
                matrix[i, j] = overlap_days
        if bucket_config.collapse_spread_pair == BucketConfig.CollapseSpreadPair.COLLAPSE_BY_SUM_SPREAD_BY_INTERPOLATE:
            # normalize on columns, to assign a portion of each source interval to each target interval

        elif bucket_config.collapse_spread_pair == BucketConfig.CollapseSpreadPair.COLLAPSE_BY_WEIGHTED_AVERAGE_SPREAD_BY_REPEAT:
            #normalize on rows, to wind up with 1 where only one interval covering target, use weighted average where multiples

        

    def _get_intervals(self, bucket_config: BucketConfig) -> list[tuple[datetime.datetime, datetime.datetime]]:
        
        # if arrears, then first interval STARTS BEFORE first date 
        # periodicity says how many days to lead/trail by 
        if bucket_config.arrears_advance == BucketConfig.ArrearsAdvance.ARREARS:
            trailing_dates = []
            if self.periodicity ==TimePoints.Periodicity.DAILY:
                leading_dates = [self.dates[0] - datetime.timedelta(days=1)]    
            elif self.periodicity == TimePoints.Periodicity.MONTHLY:
                leading_dates = [self.dates[0] - datetime.timedelta(days=30)]
            elif self.periodicity == TimePoints.Periodicity.QUARTERLY:
                leading_dates = [self.dates[0] - datetime.timedelta(days=90)]
            elif self.periodicity == TimePoints.Periodicity.YEARLY:
                leading_dates = [self.dates[0] - datetime.timedelta(days=365)]
            else:
                raise ValueError(f"Invalid periodicity: {self.periodicity}")
        elif bucket_config.arrears_advance == BucketConfig.ArrearsAdvance.ADVANCE:
            leading_dates = []
            if self.periodicity == TimePoints.Periodicity.DAILY:
                trailing_dates = [self.dates[-1] + datetime.timedelta(days=1)]
            elif self.periodicity == TimePoints.Periodicity.MONTHLY:
                trailing_dates = [self.dates[-1] + datetime.timedelta(days=30)]
            elif self.periodicity == TimePoints.Periodicity.QUARTERLY:
                trailing_dates = [self.dates[-1] + datetime.timedelta(days=90)]
            elif self.periodicity == TimePoints.Periodicity.YEARLY:
                trailing_dates = [self.dates[-1] + datetime.timedelta(days=365)]
            else:
                raise ValueError(f"Invalid periodicity: {self.periodicity}")
        else:
            raise ValueError(f"Invalid arrears_advance: {bucket_config.arrears_advance}")
        dates_to_use = leading_dates + self.dates + trailing_dates
        intervals = []
        for i in range(len(dates_to_use) - 1):
            intervals.append((dates_to_use[i], dates_to_use[i + 1]))
        return intervals


class TimeSeries(BaseDataElement):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    values: Values
    time_points: TimePoints
    bucket_config: BucketConfig

    def __init__(
        self,
        values: list[float | int | Decimal],
        dates: list[datetime.datetime | str | datetime.date | pd.Timestamp],
    ):
        super().__init__(values=Values(values=values), time_points=TimePoints(dates=dates))

    def get_bucketed_time_series(self, target_time_points: TimePoints) -> 'TimeSeries':
        from timeseries.bucket import Bucketer
        return Bucketer(target_time_points=target_time_points).get_bucketed_time_series(self)
 
    def get_copy_with_new_time_and_values(self, new_time_points: TimePoints, new_values: list[float | int | Decimal]) -> 'TimeSeries':
        return TimeSeries(
            values=self.values.get_copy_with_new_values(new_values), 
            time_points=new_time_points, 
            bucket_config=self.bucket_config)

    def get_bucketing_hash(self) -> str:
        return (self.bucket_config.hash,self.time_points.hash)

    @model_validator(mode="after")
    def _validate(self):
        if len(self.values) != len(self.time_points):
            raise ValueError(f"values and time_points must have the same length. len(values) = {len(self.values)}, len(time_points) = {len(self.time_points)}")
        return self




mytime = TimeSeries(values=[1, 2, 3], dates=["2026-01-01", "2026-01-02", "2026-01-03"])
print(mytime.time_points.hash)
