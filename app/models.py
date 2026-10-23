import re

from pydantic import BaseModel, ConfigDict, Field, StrictInt, field_validator


class OrderItemInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    product_id: StrictInt = Field(gt=0)
    quantity: StrictInt = Field(ge=1, le=99)


class OrderInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    name: str = Field(min_length=2, max_length=80)
    phone: str = Field(min_length=10, max_length=30)
    items: list[OrderItemInput] = Field(min_length=1, max_length=50)

    @field_validator("phone")
    @classmethod
    def normalize_phone(cls, value):
        if not re.fullmatch(r"\+?[\d\s()\-]+", value, flags=re.ASCII):
            raise ValueError("Укажите телефон, например +7 999 123-45-67")
        digits = re.sub(r"\D", "", value)
        if not 10 <= len(digits) <= 15:
            raise ValueError("В телефоне должно быть от 10 до 15 цифр")
        if len(digits) == 11 and digits.startswith("8"):
            digits = "7" + digits[1:]
        return "+" + digits
