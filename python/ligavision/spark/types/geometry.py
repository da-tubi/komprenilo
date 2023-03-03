#  Copyright 2021 Rikai Authors
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.

"""Geometry User Defined Types in Spark
"""

from __future__ import annotations

# Third-Party
from pyspark.sql import Row
from pyspark.sql.types import (
    ArrayType,
    DoubleType,
    FloatType,
    IntegerType,
    ShortType,
    StructField,
    StructType,
    UserDefinedType,
)

# Liga
from liga.logging import logger
from ligavision.dsl import Mask as DslMask
from ligavision.dsl import Box2d as DslBox2d
from ligavision.dsl import Box3d as DslBox3d
from ligavision.dsl import Point as DslPoint

__all__ = [
    "Point",
    "PointType",
    "Box3d",
    "Box3dType",
    "Box2d",
    "Box2dType",
    "Mask",
    "MaskType",
]


class Box2dType(UserDefinedType):
    """User defined type for the 2D bounding box."""

    @classmethod
    def sqlType(cls) -> StructType:
        return StructType(
            fields=[
                StructField("xmin", DoubleType(), False),
                StructField("ymin", DoubleType(), False),
                StructField("xmax", DoubleType(), False),
                StructField("ymax", DoubleType(), False),
            ]
        )

    @classmethod
    def module(cls) -> str:
        return "ligavision.spark.types.geometry"

    @classmethod
    def scalaUDT(cls) -> str:
        return "org.apache.spark.sql.rikai.Box2dType"

    def serialize(self, obj: "Box2d"):
        """Serialize a Box2d into a PySpark Row"""
        return Row(
            xmin=obj.xmin,
            ymin=obj.ymin,
            xmax=obj.xmax,
            ymax=obj.ymax,
        )

    def deserialize(self, datum: Row) -> "Box2d":
        if len(datum) != 4:
            logger.error(f"Deserialize box2d: not sufficient data: {datum}")

        return Box2d(**datum.asDict())

    def simpleString(self) -> str:
        return "box2d"


class Box2d(DslBox2d):
    __UDT__ = Box2dType()


class PointType(UserDefinedType):
    """Spark UDT for :py:class:`ligavision.dsl.geometry.Point` class."""

    @classmethod
    def sqlType(cls) -> StructType:
        return StructType(
            fields=[
                StructField("x", DoubleType(), False),
                StructField("y", DoubleType(), False),
                StructField("z", DoubleType(), False),
            ]
        )

    @classmethod
    def module(cls) -> str:
        return "ligavision.spark.types.geometry"

    @classmethod
    def scalaUDT(cls) -> str:
        return "org.apache.spark.sql.rikai.PointType"

    def serialize(self, obj: "Point"):
        """Serialize an :py:class:`PointType` into Spark Row"""
        return Row(x=obj.x, y=obj.y, z=obj.z)

    def deserialize(self, datum: Row) -> "Point":
        if len(datum) < 3:
            logger.error(f"Deserialize Point: not sufficient data: {datum}")

        return Point(datum[0], datum[1], datum[2])

    def simpleString(self) -> str:
        return "point"


class Point(DslPoint):
    __UDT__ = PointType()


class Box3dType(UserDefinedType):
    """Spark UDT for :py:class:`~Box3d` class."""

    @classmethod
    def sqlType(cls) -> StructType:
        return StructType(
            fields=[
                StructField("center", PointType.sqlType(), False),
                StructField("length", DoubleType(), False),
                StructField("width", DoubleType(), False),
                StructField("height", DoubleType(), False),
                StructField("heading", DoubleType(), False),
            ]
        )

    @classmethod
    def module(cls) -> str:
        return "ligavision.spark.types.geometry"

    @classmethod
    def scalaUDT(cls) -> str:
        return "org.apache.spark.sql.rikai.Box3dType"

    def serialize(self, obj: "Box3d"):
        """Serialize an Box3d into a Spark Row"""
        return Row(obj.center, obj.length, obj.width, obj.height, obj.heading)

    def deserialize(self, datum: Row) -> "Box3d":
        if len(datum) < 5:
            logger.error(f"Deserialize Box3d: not sufficient data: {datum}")
        return Box3d(datum[0], datum[1], datum[2], datum[3], datum[4])

    def simpleString(self) -> str:
        return "box3d"


class Box3d(DslBox3d):
    __UDT__ = Box3dType()


class MaskType(UserDefinedType):
    """Spark UDT for 2-D mask"""

    @classmethod
    def sqlType(cls) -> StructType:
        return StructType(
            fields=[
                StructField("type", ShortType(), False),
                StructField("height", IntegerType(), False),
                StructField("width", IntegerType(), False),
                StructField(
                    "polygon",
                    ArrayType(ArrayType(FloatType(), False), False),
                    True,
                ),
                StructField("rle", ArrayType(IntegerType(), False), True),
            ]
        )

    @classmethod
    def module(cls) -> str:
        return "ligavision.spark.types.geometry"

    @classmethod
    def scalaUDT(cls) -> str:
        return "org.apache.spark.sql.rikai.MaskType"

    def serialize(self, mask: "Mask") -> Row:
        mask_type = mask.type.value
        if mask.type == Mask.Type.RLE or mask.type == Mask.Type.COCO_RLE:
            return Row(
                type=mask_type,
                height=mask.height,
                width=mask.width,
                polygon=None,
                rle=mask.data,
            )
        elif mask.type == Mask.Type.POLYGON:
            return Row(
                type=mask_type,
                height=mask.height,
                width=mask.width,
                polygon=mask.data,
                rle=None,
            )
        else:
            raise ValueError(f"Unrecognized mask type: {mask.type}")

    def deserialize(self, datum: Row) -> "Mask":
        mask_type = Mask.Type(datum["type"])
        height = datum["height"]
        width = datum["width"]
        if mask_type == Mask.Type.POLYGON:
            return Mask.from_polygon(
                datum["polygon"], height=height, width=width
            )
        elif mask_type == Mask.Type.RLE:
            return Mask.from_rle(datum["rle"], height=height, width=width)
        elif mask_type == Mask.Type.COCO_RLE:
            return Mask.from_coco_rle(datum["rle"], height=height, width=width)
        else:
            raise ValueError(f"Unrecognized mask type: {datum['type']}")

    def simpleString(self) -> str:
        return "mask"


class Mask(DslMask):
    __UDT__ = MaskType()

    def __init__(self, dsl: DslMask):
        super().__init__(dsl.data, dsl.width, dsl.height, dsl.type)

    @staticmethod
    def from_rle(data: list[int], width: int, height: int) -> Mask:
        return Mask(DslMask.from_rle(data, width, height))

    @staticmethod
    def from_coco_rle(data: list[int], width: int, height: int) -> Mask:
        return Mask(DslMask.from_coco_rle(data, width, height))

    @staticmethod
    def from_polygon(data: list[list[float]], width: int, height: int) -> Mask:
        return Mask(DslMask.from_polygon(data, width, height))

    @staticmethod
    def from_mask(mask: np.ndarray) -> Mask:
        return Mask(DslMask.from_mask(mask))
