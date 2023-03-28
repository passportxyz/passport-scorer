import { useEffect, useRef } from 'react';
import {
  ToastId,
  useToast,
} from "@chakra-ui/react";

import { successToast, warningToast } from "./Toasts";

export function useClickOutsideToast() {
  const toast = useToast();
  const toastIdRef = useRef<ToastId | undefined>();

  function closeToast() {
    if (toastIdRef.current) {
      toast.close(toastIdRef.current);
    }
  }

  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      closeToast();
    };

    window.addEventListener('click', handleClickOutside);
    return () => {
      window.removeEventListener('click', handleClickOutside);
    };
  }, [closeToast]);

  function openToast(toastMsg: string, toastType: string,) {
    if (toastType === "success") {
      toastIdRef.current = toast(successToast(toastMsg, toast));
    } else if (toastType === "warning") {
      toastIdRef.current = toast(warningToast(toastMsg, toast));
    }
  }

  return { toastIdRef, openToast };
}
