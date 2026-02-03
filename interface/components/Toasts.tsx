// Legacy toast helper functions
// These are kept for backwards compatibility but the new useToast hook is preferred

import { CheckCircleIcon, XMarkIcon } from "@heroicons/react/24/outline";
import { ExclamationCircleIcon } from "@heroicons/react/24/outline";

// Note: These functions are now deprecated. Use the useToast hook from ui/Toast instead.
// Example usage:
//   const toast = useToast();
//   toast.success("Your message here");
//   toast.warning("Your warning message");

export const successToast = (message: string, toast: any) => {
  // For backwards compatibility, but this won't work with the new toast system
  console.warn("successToast is deprecated. Use toast.success() from useToast hook instead.");
  return {};
};

export const warningToast = (message: string, toast: any) => {
  // For backwards compatibility, but this won't work with the new toast system
  console.warn("warningToast is deprecated. Use toast.warning() from useToast hook instead.");
  return {};
};
