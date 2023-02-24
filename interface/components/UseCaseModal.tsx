// --- React components/methods
import React, { useState } from "react";
import { useRouter } from "next/router";

// --- Components
import { ArrowBackIcon, SmallCloseIcon } from "@chakra-ui/icons";

import {
  Input,
  Text,
  Icon,
  Center,
  Modal,
  ModalOverlay,
  ModalContent,
  ModalBody,
  ModalHeader,
} from "@chakra-ui/react";
import {
  DotsCircleHorizontalIcon,
  FingerPrintIcon,
  HandIcon,
  StatusOnlineIcon,
} from "./CustomIcons";

interface UseCaseInterface {
  icon: (fill?: string) => JSX.Element;
  title: string;
  description: string;
}

const useCases: Array<UseCaseInterface> = [
  {
    icon: (fill: string = "#111827"): JSX.Element => (
      <StatusOnlineIcon fill={fill} />
    ),
    title: "Airdrop Protection",
    description:
      "I want to ensure my airdrop goes to real humans and not farmers.",
  },
  {
    icon: (fill: string = "#111827"): JSX.Element => (
      <FingerPrintIcon fill={fill} />
    ),
    title: "Sybil Prevention",
    description: "I need to ensure my community or app is not attacked.",
  },
  {
    icon: (fill: string = "#111827"): JSX.Element => <HandIcon fill={fill} />,
    title: "Bot prevention",
    description: "I want my community or app to be safe from bots.",
  },
  {
    icon: (fill: string = "#111827"): JSX.Element => (
      <DotsCircleHorizontalIcon fill={fill} />
    ),
    title: "Other",
    description: "It's something else, or I'm not sure yet.",
  },
];

interface UseCaseModalProps {
  isOpen: boolean;
  onClose: () => void;
}

const UseCaseModal = ({ isOpen, onClose }: UseCaseModalProps): JSX.Element => {
  const [wizardStep, setWizardStep] = useState(1);
  const [useCase, setUseCase] = useState<UseCaseInterface | undefined>(
    undefined
  );
  const [useCaseName, setUseCaseName] = useState("");
  const [useCaseDescription, setUseCaseDescription] = useState("");

  const closeModal = () => {
    setUseCaseName("");
    setUseCaseDescription("");
    setUseCase(undefined);
    setWizardStep(1);
    onClose();
  };

  return (
    <Modal
      isOpen={isOpen}
      isCentered={true}
      size={{ base: "full", md: "xl", lg: "xl", xl: "xl" }}
      onClose={closeModal}
    >
      <ModalOverlay />
      <ModalContent>
        {wizardStep > 1 ? (
          <ModalHeader className="flex items-center justify-between">
            <ArrowBackIcon
              className="cursor-pointer"
              onClick={() => setWizardStep(1)}
            />
            <span className="text-base">Use Case Details</span>
            <SmallCloseIcon className="cursor-pointer" onClick={closeModal} />
          </ModalHeader>
        ) : (
          <ModalHeader className="flex items-center justify-end">
            <SmallCloseIcon className="cursor-pointer" onClick={closeModal} />
          </ModalHeader>
        )}
        <ModalBody className="flex h-screen w-full flex-col">
          {wizardStep === 1 && (
            <SelectUseCase
              useCase={useCase}
              setUseCase={setUseCase}
              setWizardStep={setWizardStep}
            />
          )}

          {wizardStep === 2 && (
            <UseCaseDetails
              useCase={useCase}
              useCaseName={useCaseName}
              useCaseDescription={useCaseDescription}
              setUseCaseName={setUseCaseName}
              setUseCaseDescription={setUseCaseDescription}
              setWizardStep={setWizardStep}
              closeModal={closeModal}
            />
          )}
        </ModalBody>
      </ModalContent>
    </Modal>
  );
};

interface SelectUseCaseProps {
  useCase: UseCaseInterface | undefined;
  setUseCase: (useCase: UseCaseInterface) => void;
  setWizardStep: (wizardStep: number) => void;
}

const SelectUseCase = ({
  useCase,
  setUseCase,
  setWizardStep,
}: SelectUseCaseProps) => {
  return (
    <>
      <Center>
        <div>
          <svg
            width="48"
            height="48"
            viewBox="0 0 48 48"
            fill="none"
            xmlns="http://www.w3.org/2000/svg"
          >
            <rect width="48" height="48" rx="24" fill="#F0EBFF" />
            <path
              d="M16 17C16 16.4477 16.4477 16 17 16H31C31.5523 16 32 16.4477 32 17V19C32 19.5523 31.5523 20 31 20H17C16.4477 20 16 19.5523 16 19V17Z"
              stroke="#6F3FF5"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
            <path
              d="M16 25C16 24.4477 16.4477 24 17 24H23C23.5523 24 24 24.4477 24 25V31C24 31.5523 23.5523 32 23 32H17C16.4477 32 16 31.5523 16 31V25Z"
              stroke="#6F3FF5"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
            <path
              d="M28 25C28 24.4477 28.4477 24 29 24H31C31.5523 24 32 24.4477 32 25V31C32 31.5523 31.5523 32 31 32H29C28.4477 32 28 31.5523 28 31V25Z"
              stroke="#6F3FF5"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
        </div>
      </Center>
      <Center className="mt-6">
        <Text className="text-purple-darkpurple">Select a Use Case</Text>
      </Center>
      <Center className="my-2">
        <Text className="text-purple-softpurple">
          What will this Scorer be used for?
        </Text>
      </Center>

      <div className="mt-4 grid grid-cols-1 gap-4 md:grid-cols-2">
        {useCases.map((item, index) => (
          <div
            key={index}
            onClick={() => setUseCase(item)}
            data-testid="use-case-item"
            className={
              "cursor-pointer rounded border bg-white px-6 py-5 shadow-sm hover:border-purple-gitcoinpurple focus:outline-none md:mt-2 " +
              (useCase?.title === item?.title
                ? "border-purple-gitcoinpurple"
                : "border-gray-300")
            }
          >
            <div className="relative flex space-x-3">
              <div>
                <Icon boxSize={19.5}>{item.icon()}</Icon>
              </div>
              <div className="min-w-0 flex-1">
                <span className="absolute inset-0" aria-hidden="true" />
                <p className="text-sm text-purple-darkpurple">{item.title}</p>
                <p className="text-sm text-gray-500">{item.description}</p>
              </div>
            </div>
          </div>
        ))}
      </div>
      <button
        className="mb-8 mt-auto w-full rounded-md bg-purple-gitcoinpurple py-3 text-white md:mt-8"
        onClick={() => setWizardStep(2)}
        disabled={!useCase}
      >
        Continue
      </button>
    </>
  );
};

interface UseCaseDetailsProps {
  useCase: UseCaseInterface | undefined;
  useCaseName: string;
  useCaseDescription: string;
  setUseCaseName: (name: string) => void;
  setUseCaseDescription: (description: string) => void;
  setWizardStep: (wizardStep: number) => void;
  closeModal: () => void;
}

const UseCaseDetails = ({
  useCase,
  useCaseName,
  useCaseDescription,
  setUseCaseName,
  setUseCaseDescription,
  closeModal,
}: UseCaseDetailsProps) => {
  const switchToSelectMechanism = () => {
    // TODO: save the use case details in local storage
    // TODO: navigate to mechanism selection route
    closeModal();
  };

  return (
    <>
      <p className="mt-10 text-xs">Use Case</p>
      <div>
        <p className="my-2 text-purple-gitcoinpurple">
          <Icon boxSize={19.5}>{useCase?.icon("#6F3FF5")}</Icon>{" "}
          {useCase?.title}
        </p>
        <p className="text-gray-500">{useCase?.description}</p>
      </div>
      <hr className="my-6 text-gray-lightgray" />
      <div>
        <label className="text-gray-softgray font-librefranklin text-xs">
          Name
        </label>
        <Input
          data-testid="use-case-name-input"
          className="mt-2 mb-4 text-blue-darkblue"
          value={useCaseName}
          onChange={(name) => setUseCaseName(name.target.value)}
          placeholder="App / Use Case Name"
        />
        <label className="text-gray-softgray font-librefranklin text-xs">
          Description
        </label>
        <Input
          className="mt-2 text-blue-darkblue"
          data-testid="use-case-description-input"
          value={useCaseDescription}
          onChange={(description) =>
            setUseCaseDescription(description.target.value)
          }
          placeholder="Enter Use Case Description"
        />
      </div>
      <button
        className="mb-8 mt-auto w-full rounded-md bg-purple-gitcoinpurple py-3 text-white md:mt-8"
        onClick={switchToSelectMechanism}
        disabled={!useCaseName || !useCaseDescription}
      >
        Continue
      </button>
    </>
  );
};

export default UseCaseModal;
