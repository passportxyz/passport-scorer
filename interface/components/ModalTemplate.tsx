// --- React components/methods
import React from "react";

// --- Style/UI Components
import {
  Modal,
  ModalOverlay,
  ModalContent,
  ModalHeader,
  ModalBody,
  ModalCloseButton,
  ModalFooter,
  Text,
} from "@chakra-ui/react";

type ModalProps = {
  isOpen: boolean;
  onClose: () => void;
  title: string;
  children?: React.ReactNode;
  icon?: JSX.Element;
  body?: string;
  footer?: string;
};

const ModalTemplate = ({
  isOpen,
  onClose,
  title,
  children,
  icon,
  body,
  footer,
}: ModalProps): JSX.Element => {
  return (
    <>
      <Modal size="xl" isOpen={isOpen} onClose={onClose}>
        <ModalOverlay />
        <ModalContent>
          <div className="mx-auto mt-12 w-30 p-2 bg-gray-100 flex justify-center rounded-full">{icon}</div>
          <ModalHeader className="font-librefranklin text-blue-darkblue text-center">{title}</ModalHeader>
          <ModalBody>
            <Text className="font-librefranklin text-purple-softpurple text-center mb-6">
              {body}
            </Text>
            {children}
          </ModalBody>
          <ModalCloseButton />
        </ModalContent>
        <ModalFooter>
          {footer}
        </ModalFooter>
      </Modal>
    </>
  );
};

export default ModalTemplate;
