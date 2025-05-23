// --- React components/methods
import React, { useState, useEffect } from "react";

// --- Types
import { Community } from "../utils/account-requests";

// Components

import {
  NoSymbolIcon,
  EllipsisVerticalIcon,
} from "@heroicons/react/24/outline";

import {
  Menu,
  MenuButton,
  MenuItem,
  MenuList,
  Modal,
  ModalOverlay,
  ModalContent,
  ModalHeader,
  Input,
  ModalBody,
  ModalFooter,
  ModalCloseButton,
  useToast,
  IconButton,
} from "@chakra-ui/react";
import { SpinnerIcon } from "./CustomIcons";
import { warningToast } from "./Toasts";

type CommunityCardProps = {
  community: Community;
  onCommunityDeleted: () => void;

  handleUpdateCommunity: (
    communityId: number,
    name: string,
    description: string,
    threshold: number
  ) => void;
  handleDeleteCommunity: (communityId: number) => void;
};

interface RenameModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSaveChanges: (
    name: string,
    description: string,
    threshold: number
  ) => Promise<void>;
  name: string;
  description: string;
  threshold: number;
}

const RenameModal = ({
  isOpen,
  onClose,
  onSaveChanges,
  name,
  description,
  threshold,
}: RenameModalProps): JSX.Element => {
  const [scorerName, setScorerName] = useState("");
  const [scorerDescription, setScorerDescription] = useState("");
  const [scorerThreshold, setScorerThreshold] = useState<string>(
    threshold.toString()
  );
  const [thresholdError, setThresholdError] = useState<string>("");
  const [inProgress, setInProgress] = useState(false);

  useEffect(() => {
    if (isOpen) {
      setScorerName(name);
      setScorerDescription(description);
      setScorerThreshold(threshold.toString());
    }
  }, [isOpen, name, description, threshold]);

  const closeModal = () => {
    onClose();
  };

  const saveChanges = async () => {
    if (
      scorerThreshold === "" ||
      isNaN(Number(scorerThreshold)) ||
      Number(scorerThreshold) <= 0
    ) {
      setThresholdError("Threshold must be greater than 0");
      return;
    }
    setInProgress(true);
    try {
      const thresholdValue = parseFloat(scorerThreshold);
      await onSaveChanges(scorerName, scorerDescription, thresholdValue);
    } catch (e) {}
    setInProgress(false);
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
          <span className="text-base font-normal">Edit Scorer</span>
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
          <label className="text-gray-softgray mt-4 font-librefranklin text-xs">
            Threshold
          </label>
          <Input
            className="mt-2 text-blue-darkblue"
            data-testid="use-case-threshold-input"
            type="number"
            step="any"
            min="0"
            value={scorerThreshold}
            onChange={(e) => {
              setScorerThreshold(e.target.value);
              if (
                e.target.value === "" ||
                isNaN(Number(e.target.value)) ||
                Number(e.target.value) <= 0
              ) {
                setThresholdError("Threshold must be greater than 0");
              } else {
                setThresholdError("");
              }
            }}
            placeholder="Threshold"
          />
          {thresholdError && (
            <span
              className="mt-1 text-xs text-red-500"
              data-testid="threshold-error"
            >
              {thresholdError}
            </span>
          )}
        </ModalBody>
        <ModalFooter>
          <button
            className="mb-2 flex w-full justify-center rounded-md bg-purple-gitcoinpurple py-3 text-white md:mt-4"
            disabled={
              !scorerName ||
              !scorerDescription ||
              inProgress ||
              !!thresholdError
            }
            onClick={saveChanges}
          >
            <SpinnerIcon inProgress={inProgress}></SpinnerIcon>
            Save Changes
          </button>
        </ModalFooter>
      </ModalContent>
    </Modal>
  );
};

interface DeleteConfirmationModalProps {
  isOpen: boolean;
  onCancel: () => void;
  onConfirm: () => void;
  community: Community;
}

const DeleteConfirmationModal = ({
  isOpen,
  onCancel,
  onConfirm,
}: DeleteConfirmationModalProps): JSX.Element => {
  const [inProgress, setInProgress] = useState(false);

  const handleDeleteConfirm = async () => {
    setInProgress(true);
    try {
      await onConfirm();
    } catch (e) {}
    setInProgress(false);
  };
  return (
    <Modal
      isOpen={isOpen}
      isCentered={true}
      size={{ base: "xs", md: "lg", lg: "lg", xl: "lg" }}
      onClose={() => {}}
    >
      <ModalOverlay />
      <ModalContent>
        <ModalBody>
          <div className="py-6 text-purple-darkpurple">
            <div className="flex items-center justify-center">
              <div className="mb-4 flex h-12 w-12 justify-center rounded-full bg-[#FDDEE4]">
                <NoSymbolIcon className="w-7 text-[#D44D6E]" />
              </div>
            </div>
            <div className="text-center">
              <p className="font-bold">Are you sure?</p>
              <p className="mt-2 text-purple-softpurple">
                This will permanantly delete your scorer.
                <br />
                Are you sure you want to continue?
              </p>
            </div>
            <div className="mt-10 grid grid-cols-1 gap-4 md:grid-cols-2">
              <button
                className="order-last w-full rounded border border-gray-lightgray py-2 px-6 text-base md:order-first"
                onClick={onCancel}
              >
                Cancel
              </button>
              <button
                className="flex w-full justify-center rounded bg-purple-gitcoinpurple py-2 px-6 text-base text-white"
                onClick={handleDeleteConfirm}
                disabled={inProgress}
              >
                <SpinnerIcon inProgress={inProgress}></SpinnerIcon>
                Confirm Deletion
              </button>
            </div>
          </div>
        </ModalBody>
      </ModalContent>
    </Modal>
  );
};

const CommunityCard = ({
  community,
  handleUpdateCommunity,
  handleDeleteCommunity,
}: CommunityCardProps): JSX.Element => {
  const toast = useToast();
  let [isRenameModalOpen, setIsRenameModalOpen] = useState(false);
  let [isDeleteConfirmationModalOpen, setIsDeleteConfirmationModalOpen] =
    useState(false);

  const handleRename = () => {
    setIsRenameModalOpen(true);
  };

  const handleCloseRenameModal = () => {
    setIsRenameModalOpen(false);
  };

  const handleDelete = () => {
    setIsDeleteConfirmationModalOpen(true);
  };
  const handleCancelDelete = () => {
    try {
      setIsDeleteConfirmationModalOpen(false);
    } catch (e) {}
  };

  const saveChanges = async (
    name: string,
    description: string,
    threshold: number
  ) => {
    try {
      await handleUpdateCommunity(community.id, name, description, threshold);
      setIsRenameModalOpen(false);
    } catch (e) {
      toast(warningToast("Something went wrong. Please try again.", toast));
    }
  };

  const deleteCommunity = async () => {
    try {
      await handleDeleteCommunity(community.id);
      setIsDeleteConfirmationModalOpen(false);
    } catch (e) {
      toast(warningToast("Something went wrong. Please try again.", toast));
    }
  };

  return (
    <div className="flex-col px-4 py-4 md:pl-4 md:pr-1.5">
      <RenameModal
        isOpen={isRenameModalOpen}
        onClose={handleCloseRenameModal}
        onSaveChanges={saveChanges}
        name={community.name}
        description={community.description}
        threshold={community.threshold}
      ></RenameModal>
      <DeleteConfirmationModal
        isOpen={isDeleteConfirmationModalOpen}
        onCancel={handleCancelDelete}
        onConfirm={deleteCommunity}
        community={community}
      ></DeleteConfirmationModal>
      <div
        data-testid={`scorer-item-${community.id}`}
        className="relative min-w-0 md:static md:flex"
      >
        <div className="flex-auto md:basis-5/12">
          <p className="text-sm text-purple-gitcoinpurple">
            {community.use_case}
          </p>
          <p className="truncate text-base font-medium text-purple-darkpurple">
            {community.name}
          </p>
          <p className="mt-2 flex items-center text-sm text-purple-softpurple">
            <span className="truncate">{community.description}</span>
          </p>
          <p className="mt-2 flex items-center text-sm text-purple-softpurple">
            <span className="truncate">Threshold: {community.threshold}</span>
          </p>
        </div>
        <div className="mt-4 flex md:mt-5 md:block md:basis-3/12">
          <p className="text-sm text-purple-softpurple md:flex md:flex-row-reverse">
            Created:
          </p>
          <p className="text-sm text-purple-softpurple md:flex md:flex-row-reverse">
            {community.created_at
              ? new Date(community.created_at).toDateString()
              : ""}
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
            <MenuButton
              data-testid="card-menu-button"
              as={IconButton}
              icon={
                <EllipsisVerticalIcon className="h-8 text-purple-darkpurple" />
              }
              variant="ghost"
              _hover={{ bg: "transparent" }}
              _expanded={{ bg: "transparent" }}
              _focus={{ bg: "transparent" }}
              className="my-auto flex justify-center"
            />
            <MenuList color={"#0E0333"}>
              <MenuItem
                data-testid={`menu-rename-${community.id}`}
                onClick={handleRename}
              >
                Edit
              </MenuItem>
              <MenuItem
                data-testid={`menu-delete-${community.id}`}
                onClick={handleDelete}
              >
                Delete
              </MenuItem>
            </MenuList>
          </Menu>
        </div>
      </div>
    </div>
  );
};

export default CommunityCard;
