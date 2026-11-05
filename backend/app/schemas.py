from __future__ import annotations

import re
from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator

BloodGroup = Literal["A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-"]
PHONE_PATTERN = re.compile(r"^[+()\-\s0-9]{7,32}$")


class RegisterRequest(BaseModel):
    full_name: str = Field(min_length=1, max_length=120)
    email: EmailStr
    password: str = Field(min_length=12, max_length=128)

    @field_validator("full_name")
    @classmethod
    def clean_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Enter your full name")
        return value


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: EmailStr
    created_at: datetime


class AuthResponse(BaseModel):
    user: UserRead


class EmergencyContactInput(BaseModel):
    full_name: str = Field(min_length=1, max_length=120)
    phone_number: str = Field(min_length=7, max_length=32)
    relationship_label: str | None = Field(default=None, max_length=80)

    @field_validator("full_name", "phone_number", "relationship_label")
    @classmethod
    def clean_optional_strings(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        return value or None

    @field_validator("phone_number")
    @classmethod
    def validate_phone(cls, value: str) -> str:
        if not PHONE_PATTERN.fullmatch(value):
            raise ValueError("Use digits, spaces, +, parentheses, or hyphens for the phone number")
        return value

    @field_validator("full_name")
    @classmethod
    def require_contact_name(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Enter the contact's name")
        return value.strip()


class EmergencyContactRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    full_name: str
    phone_number: str
    relationship_label: str | None


class PatientProfileWrite(BaseModel):
    full_name: str = Field(min_length=1, max_length=120)
    date_of_birth: date | None = None
    blood_group: BloodGroup | None = None
    phone_number: str | None = Field(default=None, max_length=32)
    known_allergies: str | None = Field(default=None, max_length=4000)
    major_conditions: str | None = Field(default=None, max_length=4000)
    current_medications: str | None = Field(default=None, max_length=4000)
    emergency_contacts: list[EmergencyContactInput] = Field(default_factory=list, max_length=5)

    @field_validator("full_name")
    @classmethod
    def clean_full_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Enter your full name")
        return value

    @field_validator("phone_number")
    @classmethod
    def validate_phone(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if not value:
            return None
        if not PHONE_PATTERN.fullmatch(value):
            raise ValueError("Use digits, spaces, +, parentheses, or hyphens for the phone number")
        return value

    @field_validator("known_allergies", "major_conditions", "current_medications")
    @classmethod
    def normalize_blank_notes(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        return value or None

    @model_validator(mode="after")
    def reject_future_birth_date(self) -> PatientProfileWrite:
        if self.date_of_birth and self.date_of_birth > date.today():
            raise ValueError("Date of birth cannot be in the future")
        return self


class PatientProfileRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    full_name: str
    date_of_birth: date | None
    blood_group: BloodGroup | None
    phone_number: str | None
    known_allergies: str | None
    major_conditions: str | None
    current_medications: str | None
    emergency_contacts: list[EmergencyContactRead]
    verification_status: Literal["patient_reported"] = "patient_reported"
    created_at: datetime
    updated_at: datetime
