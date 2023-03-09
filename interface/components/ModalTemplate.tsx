// --- React components/methods
import React from "react";

// --- Style/UI Components
import {
  Modal,
  ModalOverlay,
  ModalContent,
  ModalHeader,
  ModalFooter,
  ModalBody,
  ModalCloseButton,
  useDisclosure,
  Button,
} from "@chakra-ui/react";
import { SmallCloseIcon } from "@chakra-ui/icons";

type ModalProps = {
  isOpen: boolean;
  onClose: () => void;
  header?: () => JSX.Element;
  children?: React.ReactNode;
};

const ModalTemplate = ({
  isOpen,
  onClose,
  header,
  children,
}: ModalProps): JSX.Element => {
  return (
    <>
      <Modal
        isOpen={isOpen}
        onClose={onClose}
        isCentered={true}
        size={{ base: "full", md: "xl", lg: "xl", xl: "xl" }}
      >
        <ModalOverlay />
        <ModalContent>
          {header ? (
            <ModalHeader>{header()}</ModalHeader>
          ) : (
            <ModalHeader className="flex items-center justify-end">
              <SmallCloseIcon className="cursor-pointer" onClick={onClose} />
            </ModalHeader>
          )}
          <ModalBody className="flex h-screen w-full flex-col">
            {children}
          </ModalBody>
        </ModalContent>
      </Modal>
    </>
  );
};

export default ModalTemplate;
