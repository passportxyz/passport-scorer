// --- React components/methods
import React, { useEffect, useState, useCallback } from "react";
import { useNavigate } from "react-router-dom";

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
  useToast,
} from "@chakra-ui/react";
import {
  DotsCircleHorizontalIcon,
  FingerPrintIcon,
  HandIcon,
  StatusOnlineIcon,
} from "./CustomIcons";
import { PrimaryBtn } from "./PrimaryBtn";
import { warningToast } from "./Toasts";
import { Community, createCommunity } from "../utils/account-requests";

export interface UseCaseInterface {
  icon: (fill?: string) => JSX.Element;
  title: string;
  description: string;
}

export const useCases: Array<UseCaseInterface> = [
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
  existingScorers: Community[];
  onClose: () => void;
  refreshCommunities: () => void;
}

const UseCaseModal = ({
  isOpen,
  existingScorers,
  onClose,
  refreshCommunities,
}: UseCaseModalProps): JSX.Element => {
  const [wizardStep, setWizardStep] = useState(1);
  const [useCase, setUseCase] = useState<UseCaseInterface | undefined>(
    undefined
  );
  const [scorerName, setScorerName] = useState("");
  const [scorerDescription, setScorerDescription] = useState("");
  const [threshold, setThreshold] = useState<string>("20");
  const [error, setError] = useState<string>("");

  useEffect(() => {
    localStorage.removeItem("tempScorer");
    if (isOpen) {
      setError("");
      setThreshold("20");
      setScorerName("");
      setScorerDescription("");
    }
  }, [isOpen]);

  const closeModal = () => {
    setScorerName("");
    setScorerDescription("");
    setUseCase(undefined);
    setWizardStep(1);
    setError("");
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
              scorerName={scorerName}
              scorerDescription={scorerDescription}
              threshold={threshold}
              setScorerName={setScorerName}
              setScorerDescription={setScorerDescription}
              setThreshold={setThreshold}
              setWizardStep={setWizardStep}
              closeModal={closeModal}
              existingScorers={existingScorers}
              refreshCommunities={refreshCommunities}
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
              "cursor-pointer rounded border bg-white px-6 py-4 shadow-sm hover:border-purple-gitcoinpurple focus:outline-none md:mt-2 " +
              (useCase?.title === item.title
                ? "border-purple-gitcoinpurple"
                : "border-gray-300")
            }
          >
            <div className="relative flex space-x-3">
              <div>
                <Icon boxSize={19.5}>{item.icon()}</Icon>
              </div>
              <div className="min-w-0 flex-1 text-xs">
                <span className="absolute inset-0" aria-hidden="true" />
                <p className="mb-2 text-purple-darkpurple">{item.title}</p>
                <p className="text-gray-500">{item.description}</p>
              </div>
            </div>
          </div>
        ))}
      </div>
      <PrimaryBtn onClick={() => setWizardStep(2)} disabled={!useCase}>
        Continue
      </PrimaryBtn>
    </>
  );
};

interface UseCaseDetailsProps {
  useCase: UseCaseInterface | undefined;
  scorerName: string;
  scorerDescription: string;
  threshold: string;
  existingScorers: Community[];
  setScorerName: (name: string) => void;
  setScorerDescription: (description: string) => void;
  setThreshold: (threshold: string) => void;
  setWizardStep: (wizardStep: number) => void;
  closeModal: () => void;
  refreshCommunities: () => void;
}

const UseCaseDetails = ({
  useCase,
  scorerName,
  scorerDescription,
  threshold,
  existingScorers,
  setScorerName,
  setScorerDescription,
  setThreshold,
  closeModal,
  refreshCommunities,
}: UseCaseDetailsProps) => {
  const navigate = useNavigate();
  const toast = useToast();
  const [isLoading, setIsLoading] = useState(false);
  const [nameError, setNameError] = useState("");
  const [thresholdError, setThresholdError] = useState("");

  // Only check for duplicate name on save
  const checkDuplicateName = (name: string) => {
    return existingScorers.some((scorer) => scorer.name === name);
  };

  const validateThreshold = (value: string) => {
    if (value === "" || isNaN(Number(value)) || Number(value) <= 0) {
      setThresholdError("Threshold must be greater than 0");
      return false;
    } else {
      setThresholdError("");
      return true;
    }
  };

  const createScorer = useCallback(async () => {
    if (!validateThreshold(threshold)) {
      return;
    }
    setIsLoading(true);
    try {
      await createCommunity({
        name: scorerName,
        description: scorerDescription,
        use_case: useCase!.title,
        rule: "LIFO",
        scorer: "WEIGHTED_BINARY",
        threshold: parseFloat(threshold),
      });
      localStorage.setItem("scorerCreated", "true");
      setIsLoading(false);
      closeModal();
      refreshCommunities();
    } catch (e) {
      toast(warningToast("Something went wrong. Please try again.", toast));
    }
  }, [scorerName, scorerDescription, useCase, threshold, toast, closeModal]);

  const switchToSelectMechanism = () => {
    // Check for duplicate name only on save
    if (checkDuplicateName(scorerName)) {
      setNameError("A scorer with this name already exists");
      return;
    }
    setNameError("");
    if (!validateThreshold(threshold)) {
      return;
    }
    localStorage.setItem(
      "tempScorer",
      JSON.stringify({
        useCase: useCases.indexOf(useCase!),
        name: scorerName,
        description: scorerDescription,
      })
    );
    console.debug("Saving the score here .... ");
    createScorer();
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
      <div className="flex flex-col gap-4">
        <div className="flex flex-col">
          <label className="text-gray-softgray font-librefranklin text-xs">
            Name
          </label>
          <Input
            data-testid="use-case-name-input"
            className="mt-2 text-blue-darkblue"
            value={scorerName}
            onChange={(e) => {
              setScorerName(e.target.value);
              if (nameError) setNameError("");
            }}
            placeholder="App / Use Case Name"
          />
          {nameError && (
            <span className="text-red-500 text-xs mt-1" data-testid="name-error">{nameError}</span>
          )}
        </div>
        <div className="flex flex-col">
          <label className="text-gray-softgray font-librefranklin text-xs">
            Description
          </label>
          <Input
            className="mt-2 text-blue-darkblue"
            data-testid="use-case-description-input"
            value={scorerDescription}
            onChange={(e) => {
              setScorerDescription(e.target.value);
            }}
            placeholder="Enter Use Case Description"
          />
        </div>
        <div className="flex flex-col">
          <label className="text-gray-softgray font-librefranklin text-xs">
            Threshold
          </label>
          <Input
            className="mt-2 text-blue-darkblue"
            data-testid="use-case-threshold-input"
            type="number"
            step="any"
            min="0"
            value={threshold}
            onChange={(e) => {
              setThreshold(e.target.value);
              validateThreshold(e.target.value);
            }}
            placeholder="Threshold"
          />
          {thresholdError && (
            <span className="text-red-500 text-xs mt-1" data-testid="threshold-error">{thresholdError}</span>
          )}
        </div>
      </div>
      <button
        className="mb-8 mt-auto w-full rounded-md bg-purple-gitcoinpurple py-3 text-white md:mt-8"
        onClick={switchToSelectMechanism}
        disabled={!scorerName || !scorerDescription || !!nameError || !!thresholdError}
      >
        Continue
      </button>
    </>
  );
};

export default UseCaseModal;
