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
