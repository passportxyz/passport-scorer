// --- React components/methods
import React from "react";

// --- Style/UI Components
import { Modal, ModalHeader, ModalBody, ModalFooter } from "../ui/Modal";
import { XMarkIcon } from "@heroicons/react/24/outline";

type ModalProps = {
  isOpen: boolean;
  onClose: () => void;
  header?: () => JSX.Element;
  footer?: () => JSX.Element;
  children?: React.ReactNode;
};

const ModalTemplate = ({
  isOpen,
  onClose,
  header,
  footer,
  children,
}: ModalProps): JSX.Element => {
  return (
    <Modal isOpen={isOpen} onClose={onClose} size="xl">
      {header ? (
        <ModalHeader onClose={onClose} showCloseButton={false}>
          {header()}
        </ModalHeader>
      ) : (
        <div className="flex items-center justify-end px-6 py-4">
          <button
            onClick={onClose}
            className="rounded-full p-1.5 text-gray-500 hover:bg-gray-100 hover:text-gray-700 transition-colors"
            aria-label="Close modal"
          >
            <XMarkIcon className="h-5 w-5" />
          </button>
        </div>
      )}
      <ModalBody className="flex h-auto min-h-[200px] w-full flex-col md:min-h-0">
        {children}
      </ModalBody>
      {footer && (
        <ModalFooter className="border-t-0">
          {footer()}
        </ModalFooter>
      )}
    </Modal>
  );
};

export default ModalTemplate;
