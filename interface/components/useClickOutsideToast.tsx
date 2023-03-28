import { useEffect, useRef } from 'react';
import {
  ToastId,
  useToast,
} from "@chakra-ui/react";

import { successToast } from "./Toasts";

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
  }, []);

  function openToast(toastMsg: string) {
    toastIdRef.current = toast(successToast(toastMsg, toast));
  }

  return { toastIdRef, openToast };
}
