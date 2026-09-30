import { z } from "zod";

const EMAIL_PATTERN = /^[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?(?:\.[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?)+$/;

export const emailSchema = z
  .string()
  .trim()
  .min(5, "Enter a valid email address")
  .max(254, "Email address is too long")
  .regex(EMAIL_PATTERN, "Enter a valid email address, e.g. name@gmail.com")
  .refine((email) => {
    const localPart = email.split("@", 1)[0];
    return localPart.length <= 64
      && !localPart.startsWith(".")
      && !localPart.endsWith(".")
      && !localPart.includes("..");
  }, "Enter a valid email address, e.g. name@gmail.com");

// Mirrors backend PasswordT: min 8 chars, at least one letter and one number.
export const passwordSchema = z
  .string()
  .min(8, "At least 8 characters")
  .max(72, "Password is too long")
  .regex(/[A-Za-z]/, "Must include at least one letter")
  .regex(/[0-9]/, "Must include at least one number");

// Mirrors backend PhoneT: 6-20 chars, digits with optional + - . ( ) spaces.
const PHONE_PATTERN = /^[+\d][\d\s\-().]{4,18}\d$/;

export const phoneSchema = z
  .string()
  .trim()
  .max(20, "Phone number is too long")
  .regex(PHONE_PATTERN, "Enter a valid phone number");

export const optionalPhoneSchema = z
  .string()
  .trim()
  .max(20, "Phone number is too long")
  .refine((v) => v === "" || PHONE_PATTERN.test(v), "Enter a valid phone number");

export const nameSchema = (label = "Required") =>
  z.string().trim().min(1, label).max(100, "Too long (max 100 characters)");
