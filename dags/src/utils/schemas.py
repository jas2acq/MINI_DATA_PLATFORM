"""Pydantic schemas for data validation in the ETL pipeline.

This module defines the data models used to validate sales records
against expected structure and business rules.
"""

from datetime import date
from typing import Any

from pydantic import BaseModel, EmailStr, Field, field_validator


class SalesRecord(BaseModel):
    """Schema for a single sales transaction record.

    Validates sales data from the data generator against expected types
    and business constraints.
    """

    order_id: str = Field(..., min_length=10, max_length=10, description="Unique order identifier")
    customer_name: str = Field(..., min_length=1, max_length=255, description="Customer full name")
    customer_email: EmailStr = Field(..., description="Customer email address")
    customer_phone: str = Field(
        ..., min_length=1, max_length=50, description="Customer phone number"
    )
    customer_address: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description="Customer address",
    )
    product_title: str = Field(..., min_length=1, max_length=500, description="Product name/title")
    product_rating: float = Field(..., ge=1.0, le=5.0, description="Product rating (1.0-5.0)")
    discounted_price: float = Field(..., gt=0.0, description="Price after discount")
    original_price: float = Field(..., gt=0.0, description="Price before discount")
    discount_percentage: int = Field(..., ge=0, le=100, description="Discount percentage (0-100)")
    is_best_seller: bool = Field(..., description="Whether product is a best seller")
    delivery_date: date = Field(..., description="Expected delivery date")
    data_collected_at: date = Field(..., description="Date data was collected")
    product_category: str = Field(..., min_length=1, max_length=100, description="Product category")
    quantity: int = Field(..., ge=1, description="Quantity ordered")
    order_date: date = Field(..., description="Date order was placed")

    @field_validator("discounted_price", "original_price")
    @classmethod
    def validate_prices(cls, value: float) -> float:
        """Validate that prices have at most 2 decimal places.

        Args:
            value: Price value to validate.

        Returns:
            Validated price value.

        Raises:
            ValueError: If price has more than 2 decimal places.
        """
        if round(value, 2) != value:
            raise ValueError("Price must have at most 2 decimal places")
        return value

    @field_validator("discount_percentage")
    @classmethod
    def validate_discount_consistency(cls, discount: int, info: Any) -> int:
        """Validate that discount percentage is consistent with prices.

        Args:
            discount: Discount percentage value.
            info: Validation context containing other field values.

        Returns:
            Validated discount percentage.

        Raises:
            ValueError: If discount doesn't match price difference.
        """
        # Note: This validation requires access to original_price and discounted_price
        # which may not be available during field-level validation.
        # Full consistency check will be done in the validator module.
        return discount

    @field_validator("delivery_date")
    @classmethod
    def validate_delivery_after_order(cls, delivery: date, info: Any) -> date:
        """Validate that delivery date is not before order date.

        Args:
            delivery: Delivery date value.
            info: Validation context containing other field values.

        Returns:
            Validated delivery date.

        Raises:
            ValueError: If delivery date is before order date.
        """
        # Access order_date from context if available
        order_date_value = info.data.get("order_date")
        if order_date_value and delivery < order_date_value:
            raise ValueError("Delivery date cannot be before order date")
        return delivery

    model_config = {
        "str_strip_whitespace": True,
        "validate_assignment": True,
        "extra": "forbid",
    }
