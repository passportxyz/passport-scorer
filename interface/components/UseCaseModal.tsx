// --- React components/methods
import React, { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

// --- Components
import { ArrowLeftIcon, XMarkIcon } from "@heroicons/react/24/outline";

import { Modal, ModalBody, ModalHeader } from "../ui/Modal";
import { Input } from "../ui/Input";
import {
  DotsCircleHorizontalIcon,
  FingerPrintIcon,
  HandIcon,
  StatusOnlineIcon,
} from "./CustomIcons";
import { PrimaryBtn } from "./PrimaryBtn";
import { Community } from "../utils/account-requests";

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
}

const UseCaseModal = ({
  isOpen,
  existingScorers,
  onClose,
}: UseCaseModalProps): JSX.Element => {
  const [wizardStep, setWizardStep] = useState(1);
  const [useCase, setUseCase] = useState<UseCaseInterface | undefined>(
    undefined
  );
  const [scorerName, setScorerName] = useState("");
  const [scorerDescription, setScorerDescription] = useState("");

  useEffect(() => {
    localStorage.removeItem("tempScorer");
  }, []);

  const closeModal = () => {
    setScorerName("");
    setScorerDescription("");
    setUseCase(undefined);
    setWizardStep(1);
    onClose();
  };

  return (
    <Modal isOpen={isOpen} onClose={closeModal} size="xl">
      {wizardStep > 1 ? (
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-200">
          <button
            onClick={() => setWizardStep(1)}
            className="p-1.5 rounded-full hover:bg-gray-100 transition-colors"
          >
            <ArrowLeftIcon className="h-5 w-5 cursor-pointer text-gray-600" />
          </button>
          <span className="text-base font-medium text-gray-900">Use Case Details</span>
          <button
            onClick={closeModal}
            className="p-1.5 rounded-full hover:bg-gray-100 transition-colors"
          >
            <XMarkIcon className="h-5 w-5 cursor-pointer text-gray-500" />
          </button>
        </div>
      ) : (
        <div className="flex items-center justify-end px-6 py-4">
          <button
            onClick={closeModal}
            className="p-1.5 rounded-full hover:bg-gray-100 transition-colors"
          >
            <XMarkIcon className="h-5 w-5 cursor-pointer text-gray-500" />
          </button>
        </div>
      )}
      <ModalBody className="flex flex-col">
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
            setScorerName={setScorerName}
            setScorerDescription={setScorerDescription}
            setWizardStep={setWizardStep}
            closeModal={closeModal}
            existingScorers={existingScorers}
          />
        )}
      </ModalBody>
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
      <div className="flex justify-center">
        <div>
          <svg
            width="48"
            height="48"
            viewBox="0 0 48 48"
            fill="none"
            xmlns="http://www.w3.org/2000/svg"
          >
            <rect width="48" height="48" rx="24" fill="#F3F4F6" />
            <path
              d="M16 17C16 16.4477 16.4477 16 17 16H31C31.5523 16 32 16.4477 32 17V19C32 19.5523 31.5523 20 31 20H17C16.4477 20 16 19.5523 16 19V17Z"
              stroke="#111827"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
            <path
              d="M16 25C16 24.4477 16.4477 24 17 24H23C23.5523 24 24 24.4477 24 25V31C24 31.5523 23.5523 32 23 32H17C16.4477 32 16 31.5523 16 31V25Z"
              stroke="#111827"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
            <path
              d="M28 25C28 24.4477 28.4477 24 29 24H31C31.5523 24 32 24.4477 32 25V31C32 31.5523 31.5523 32 31 32H29C28.4477 32 28 31.5523 28 31V25Z"
              stroke="#111827"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
        </div>
      </div>
      <div className="mt-6 text-center">
        <p className="text-gray-900 font-semibold">Select a Use Case</p>
      </div>
      <div className="my-2 text-center">
        <p className="text-gray-500">
          What will this Scorer be used for?
        </p>
      </div>

      <div className="mt-4 grid grid-cols-1 gap-4 md:grid-cols-2">
        {useCases.map((item, index) => (
          <div
            key={index}
            onClick={() => setUseCase(item)}
            data-testid="use-case-item"
            className={
              "cursor-pointer rounded-[12px] border bg-white px-6 py-4 shadow-card hover:border-gray-400 focus:outline-none md:mt-2 transition-colors " +
              (useCase?.title === item.title
                ? "border-black ring-1 ring-black"
                : "border-gray-200")
            }
          >
            <div className="relative flex space-x-3">
              <div>
                <span className="inline-block w-5 h-5">{item.icon()}</span>
              </div>
              <div className="min-w-0 flex-1 text-xs">
                <span className="absolute inset-0" aria-hidden="true" />
                <p className="mb-2 text-gray-900 font-medium">{item.title}</p>
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
  existingScorers: Community[];
  setScorerName: (name: string) => void;
  setScorerDescription: (description: string) => void;
  setWizardStep: (wizardStep: number) => void;
  closeModal: () => void;
}

const UseCaseDetails = ({
  useCase,
  scorerName,
  scorerDescription,
  existingScorers,
  setScorerName,
  setScorerDescription,
}: UseCaseDetailsProps) => {
  const navigate = useNavigate();
  const [useCaseError, setUseCaseError] = useState<string>();

  const hasDuplicateName = () => {
    const existingScorer = existingScorers.find(
      (scorer) => scorer.name === scorerName
    );
    if (existingScorer) {
      setUseCaseError("A scorer with this name already exists");
      return true;
    } else {
      setUseCaseError("");
      return false;
    }
  };

  const switchToSelectMechanism = () => {
    if (!hasDuplicateName()) {
      localStorage.setItem(
        "tempScorer",
        JSON.stringify({
          useCase: useCases.indexOf(useCase!),
          name: scorerName,
          description: scorerDescription,
        })
      );
      navigate("/new-scorer");
    }
  };

  return (
    <>
      <p className="mt-10 text-xs text-gray-500">Use Case</p>
      <div>
        <p className="my-2 text-black font-medium">
          <span className="inline-block w-5 h-5">{useCase?.icon("#000000")}</span>{" "}
          {useCase?.title}
        </p>
        <p className="text-gray-500">{useCase?.description}</p>
      </div>
      <hr className="my-6 border-gray-200" />
      <div>
        <label className="font-sans text-xs text-gray-500">
          Name
        </label>
        <Input
          data-testid="use-case-name-input"
          className="mt-2 mb-4"
          value={scorerName}
          onChange={(e) => setScorerName(e.target.value)}
          placeholder="App / Use Case Name"
        />
        <label className="font-sans text-xs text-gray-500">
          Description
        </label>
        <Input
          className="mt-2"
          data-testid="use-case-description-input"
          value={scorerDescription}
          onChange={(e) => setScorerDescription(e.target.value)}
          placeholder="Enter Use Case Description"
        />
      </div>
      {useCaseError && <p className="pt-4 text-error">{useCaseError}</p>}
      <button
        className="mb-8 mt-auto w-full rounded-[12px] bg-black py-3 text-white font-medium hover:bg-gray-800 transition-colors md:mt-8 disabled:bg-gray-200 disabled:text-gray-400"
        onClick={switchToSelectMechanism}
        disabled={!scorerName || !scorerDescription}
      >
        Continue
      </button>
    </>
  );
};

export default UseCaseModal;
