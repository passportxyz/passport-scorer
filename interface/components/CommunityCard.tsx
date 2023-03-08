// --- React components/methods
import React, { useState, useEffect } from "react";

// --- Types
import { Community } from "../utils/account-requests";

// Components
import { ArrowBackIcon, SmallCloseIcon } from "@chakra-ui/icons";
// --- Next
import { useRouter } from "next/router";

import {
  Menu,
  MenuButton,
  MenuItem,
  MenuList,
  Icon,
  Modal,
  ModalOverlay,
  ModalContent,
  ModalHeader,
  Input,
  ModalBody,
  ModalFooter,
  ModalCloseButton,
} from "@chakra-ui/react";
import { UseCaseInterface, useCases } from "./UseCaseModal";

import { updateCommunity } from "../utils/account-requests";

interface UseCaseMap {
  [k: string]: UseCaseInterface;
}

const useCasesByName = useCases.reduce(
  (acc: UseCaseMap, useCase: UseCaseInterface) => {
    acc[useCase.title] = useCase;
    return acc;
  },
  {} as UseCaseMap
);

type CommunityCardProps = {
  setUpdatedScorerName: Function;
  setUpdatedScorerDescription: Function;
  setUpdatedCommunityId: Function;
  community: Community;
  communityId: Community["id"];
  handleDeleteCommunity: Function;
  setUpdateCommunityModalOpen: Function;
};

interface RenameModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSaveChanges: (name: string, description: string) => void;
  name: string;
  description: string;
}

const RenameModal = ({
  isOpen,
  onClose,
  onSaveChanges,
  name,
  description,
}: RenameModalProps): JSX.Element => {
  const [wizardStep, setWizardStep] = useState(1);
  const [useCase, setUseCase] = useState<UseCaseInterface | undefined>(
    undefined
  );
  const [scorerName, setScorerName] = useState("");
  const [scorerDescription, setScorerDescription] = useState("");

  useEffect(() => {
    if (isOpen) {
      setScorerName(name);
      setScorerDescription(description);
    }
  }, [isOpen]);

  const closeModal = () => {
    onClose();
  };

  const saveChanges = () => {
    onSaveChanges(scorerName, scorerDescription);
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
        <ModalHeader className="flex justify-center">
          <span className="text-base font-normal">Rename Scorer</span>
        </ModalHeader>
        <ModalCloseButton onClick={closeModal} />
        <ModalBody className="flex h-screen w-full flex-col">
          <label className="text-gray-softgray font-librefranklin text-xs">
            Name
          </label>
          <Input
            data-testid="use-case-name-input"
            className="mt-2 mb-4 text-blue-darkblue"
            value={scorerName}
            onChange={(name) => setScorerName(name.target.value)}
            placeholder="App / Use Case Name"
          />
          <label className="text-gray-softgray font-librefranklin text-xs">
            Description
          </label>{" "}
          <Input
            className="mt-2 text-blue-darkblue"
            data-testid="use-case-description-input"
            value={scorerDescription}
            onChange={(description) =>
              setScorerDescription(description.target.value)
            }
            placeholder="Enter Use Case Description"
          />
        </ModalBody>
        <ModalFooter>
          <button
            className="mb-2 w-full rounded-md bg-purple-gitcoinpurple py-3 text-white md:mt-4"
            disabled={!scorerName || !scorerDescription}
            onClick={saveChanges}
          >
            Save Changes
          </button>
        </ModalFooter>
      </ModalContent>
    </Modal>
  );
};

const CommunityCard = ({
  community,
  handleDeleteCommunity,
  communityId,
  setUpdateCommunityModalOpen,
  setUpdatedScorerName,
  setUpdatedScorerDescription,
  setUpdatedCommunityId,
}: CommunityCardProps): JSX.Element => {
  const router = useRouter();
  let useCase = useCasesByName[community.use_case];
  let [isrenameModalOpen, setIsRenameModalOpen] = useState(false);
  const handleRename = (event) => {
    setIsRenameModalOpen(true);
  };

  const handleCloseRenameModal = () => {
    setIsRenameModalOpen(false);
  };

  const handleSaveRename = (name: string, description: string) => {
    updateCommunity(communityId, { name, description });
    community.name = name;
    community.description = description;
  };

  const handleDelete = (event) => {};

  const useCaseByNamee = useCaseByName;
  const useCase = useCaseByName.get(community.use_case);
  const useCaseIcon = useCase ? (
    <Icon boxSize={19.5}>{useCase.icon("#6F3FF5")}</Icon>
  ) : null;
  return (
    <div className="flex-col px-4 py-4 sm:px-6">
      <RenameModal
        isOpen={isrenameModalOpen}
        onClose={handleCloseRenameModal}
        onSaveChanges={handleSaveRename}
        name={community.name}
        description={community.description}
      ></RenameModal>
      <div className="relative min-w-0 md:static md:flex">
        <div className="flex-auto md:basis-5/12">
          <p className="text-sm text-purple-gitcoinpurple">
            <Icon boxSize={19.5} className="mt-1">
              {useCase?.icon("#6F3FF5")}
            </Icon>
            {useCase?.title}
          </p>
          <p className="truncate text-base font-medium text-purple-darkpurple">
            {community.name}
          </p>
          <p className="mt-2 flex items-center text-sm text-purple-softpurple">
            <span className="truncate">{community.description}</span>
          </p>
        </div>
        <div className="mt-4 flex md:mt-5 md:block md:basis-3/12">
          <p className="text-sm text-purple-softpurple md:flex md:flex-row-reverse">
            Created:
          </p>
          <p className="text-sm text-purple-softpurple md:flex md:flex-row-reverse">
            {new Date(community.created_at).toDateString()}
          </p>
        </div>
        <div className="mt-1 flex md:mt-5 md:block md:basis-3/12">
          <p className="text-right text-sm text-purple-softpurple md:flex md:flex-row-reverse">
            Scorer ID:
          </p>
          <p className="text-sm text-purple-softpurple md:flex md:flex-row-reverse">
            {community.id}
          </p>
        </div>
        <div className="absolute top-0 right-0 md:static md:flex md:basis-1/12 md:flex-row-reverse">
          <Menu>
            <MenuButton data-testid="card-menu-button">
              <div className="m-auto flex justify-center">
                <svg
                  xmlns="http://www.w3.org/2000/svg"
                  fill="none"
                  viewBox="0 0 24 24"
                  strokeWidth={1.5}
                  stroke="currentColor"
                  className="h-6 w-6"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    d="M12 6.75a.75.75 0 110-1.5.75.75 0 010 1.5zM12 12.75a.75.75 0 110-1.5.75.75 0 010 1.5zM12 18.75a.75.75 0 110-1.5.75.75 0 010 1.5z"
                  />
                </svg>
              </div>
            </MenuButton>{" "}
            <MenuList>
              <MenuItem onClick={handleRename}>Rename</MenuItem>
              <MenuItem onClick={handleDelete}>Delete</MenuItem>
            </MenuList>
          </Menu>
        </div>
      </div>
    </div>
  );
};

export default CommunityCard;
