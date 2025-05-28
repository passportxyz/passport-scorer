// --- React components/methods
import React, { useEffect, useState, useCallback } from "react";
import { useNavigate } from "react-router-dom";

// --- Components
import { ArrowBackIcon, SmallCloseIcon } from "@chakra-ui/icons";

import {
  Input,
  Select,
  Center,
  Modal,
  ModalOverlay,
  ModalContent,
  ModalBody,
  ModalHeader,
  useToast,
  FormHelperText,
  FormControl,
  FormLabel
} from "@chakra-ui/react";

import { warningToast } from "./Toasts";
import { Community, createCommunity } from "../utils/account-requests";

export interface UseCaseInterface {
  title: string;
}

export const useCases: Array<UseCaseInterface> = [
  { title: "Airdrop" },
  { title: "Incentivized Testnet" },
  { title: "Other rewards" },
  { title: "Quadratic Funding" },
  { title: "Governance" },
  { title: "Quests" },
  { title: "Community access" },
  { title: "Prove reputation" },
  { title: "Events" },
  { title: "Spam prevention" },
  { title: "AI" },
  { title: "Other" },
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
  const [useCase, setUseCase] = useState("");
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
    setUseCase("");
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
          <UseCaseDetails
            useCase={useCase}
            scorerName={scorerName}
            scorerDescription={scorerDescription}
            threshold={threshold}
            setScorerName={setScorerName}
            setScorerUseCase={setUseCase}
            setScorerDescription={setScorerDescription}
            setThreshold={setThreshold}
            setWizardStep={setWizardStep}
            closeModal={closeModal}
            existingScorers={existingScorers}
            refreshCommunities={refreshCommunities}
          />
        </ModalBody>
      </ModalContent>
    </Modal>
  );
};

interface UseCaseDetailsProps {
  useCase: string;
  scorerName: string;
  scorerDescription: string;
  threshold: string;
  existingScorers: Community[];
  setScorerName: (name: string) => void;
  setScorerUseCase: (useCase: string) => void;
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
  setScorerUseCase,
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
        use_case: useCase,
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
  }, [
    scorerName,
    scorerDescription,
    useCase,
    threshold,
    toast,
    closeModal,
    refreshCommunities,
  ]);

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
        useCase: useCase,
        name: scorerName,
        description: scorerDescription,
      })
    );
    console.debug("Saving the score here .... ");
    createScorer();
  };

  console.log(
    "??? continue",
    !useCase ||
      !scorerName ||
      !scorerDescription ||
      !!nameError ||
      !!thresholdError
  );
  console.log("??? continue", {
    useCase,
    scorerName,
    scorerDescription,
    nameError,
    thresholdError,
  });
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
      <div className="mt-12 flex flex-col gap-4">
        <FormControl className="flex flex-col">
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
            <span
              className="mt-1 text-xs text-red-500"
              data-testid="name-error"
            >
              {nameError}
            </span>
          )}
        </FormControl>
        <FormControl className="flex flex-col">
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
            placeholder="Please provide information about how you will use Passport"
          />
        </FormControl>
        <FormControl className="flex flex-col">
          <label className="text-gray-softgray font-librefranklin text-xs">
            Use Case
          </label>
          <Select
            data-testid="use-case-name"
            className="mt-2 text-blue-darkblue"
            placeholder="Select your Use Case"
            size="md"
            onChange={(e) => {
              console.log("setting useCase", e.target.value);
              setScorerUseCase(e.target.value);
            }}
          >
            {useCases.map((item, index) => (
              <option key={index} value={item.title}>
                {item.title}
              </option>
            ))}
          </Select>
        </FormControl>
        <FormControl className="flex flex-col">
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
          <FormHelperText>
            We recommend using a score threshold of 20. Learn more about{" "}
            <a className="text-purple-gitcoinpurple" href="https://docs.passport.xyz/building-with-passport/stamps/major-concepts/scoring-thresholds">
              score thresholds
            </a>
            .
          </FormHelperText>
          {thresholdError && (
            <span
              className="mt-1 text-xs text-red-500"
              data-testid="threshold-error"
            >
              {thresholdError}
            </span>
          )}
        </FormControl>
      </div>
      <button
        className="mb-8 mt-auto w-full rounded-md bg-purple-gitcoinpurple py-3 text-white md:mt-8"
        onClick={switchToSelectMechanism}
        disabled={
          !useCase ||
          !scorerName ||
          !scorerDescription ||
          !!nameError ||
          !!thresholdError
        }
      >
        Continue
      </button>
    </>
  );
};

export default UseCaseModal;
