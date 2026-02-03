// --- React components/methods
import React, { useState, useEffect } from "react";

// --- Types
import { Community } from "../utils/account-requests";

// Components
import {
  NoSymbolIcon,
  EllipsisVerticalIcon,
} from "@heroicons/react/24/outline";

// --- Next
import { useRouter } from "next/router";

import { Modal, ModalBody, ModalHeader, ModalFooter } from "../ui/Modal";
import { Input } from "../ui/Input";
import { DropdownMenu, DropdownMenuItem } from "../ui/DropdownMenu";
import { useToast } from "../ui/Toast";
import { UseCaseInterface, useCases } from "./UseCaseModal";
import { SpinnerIcon } from "./CustomIcons";

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
  community: Community;
  onCommunityDeleted: () => void;

  handleUpdateCommunity: (
    communityId: number,
    name: string,
    description: string
  ) => void;
  handleDeleteCommunity: (communityId: number) => void;
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
  const [scorerName, setScorerName] = useState("");
  const [scorerDescription, setScorerDescription] = useState("");
  const [inProgress, setInProgress] = useState(false);

  useEffect(() => {
    if (isOpen) {
      setScorerName(name);
      setScorerDescription(description);
    }
  }, [isOpen]);

  const closeModal = () => {
    onClose();
  };

  const saveChanges = async () => {
    setInProgress(true);
    try {
      await onSaveChanges(scorerName, scorerDescription);
    } catch (e) {}
    setInProgress(false);
  };

  return (
    <Modal isOpen={isOpen} onClose={closeModal} size="xl">
      <ModalHeader onClose={closeModal}>
        <span className="text-base font-medium text-gray-900">Rename Scorer</span>
      </ModalHeader>
      <ModalBody className="flex flex-col">
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
      </ModalBody>
      <ModalFooter>
        <button
          className="mb-2 flex w-full justify-center rounded-[12px] bg-black py-3 text-white font-medium hover:bg-gray-800 transition-colors md:mt-4 disabled:bg-gray-200 disabled:text-gray-400"
          disabled={!scorerName || !scorerDescription || inProgress}
          onClick={saveChanges}
        >
          <SpinnerIcon inProgress={inProgress}></SpinnerIcon>
          Save Changes
        </button>
      </ModalFooter>
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
    <Modal isOpen={isOpen} onClose={onCancel} size="lg">
      <ModalBody>
        <div className="py-6 text-gray-900">
          <div className="flex items-center justify-center">
            <div className="mb-4 flex h-12 w-12 justify-center rounded-full bg-red-50">
              <NoSymbolIcon className="w-7 text-red-500" />
            </div>
          </div>
          <div className="text-center">
            <p className="font-semibold text-gray-900">Are you sure?</p>
            <p className="mt-2 text-gray-500">
              This will permanantly delete your scorer.
              <br />
              Are you sure you want to continue?
            </p>
          </div>
          <div className="mt-10 grid grid-cols-1 gap-4 md:grid-cols-2">
            <button
              className="order-last w-full rounded-[12px] border border-gray-200 py-2 px-6 text-base text-gray-700 hover:bg-gray-50 transition-colors md:order-first"
              onClick={onCancel}
            >
              Cancel
            </button>
            <button
              className="flex w-full justify-center rounded-[12px] bg-black py-2 px-6 text-base text-white hover:bg-gray-800 transition-colors disabled:bg-gray-200 disabled:text-gray-400"
              onClick={handleDeleteConfirm}
              disabled={inProgress}
            >
              <SpinnerIcon inProgress={inProgress}></SpinnerIcon>
              Confirm Deletion
            </button>
          </div>
        </div>
      </ModalBody>
    </Modal>
  );
};

const CommunityCard = ({
  community,
  handleUpdateCommunity,
  handleDeleteCommunity,
}: CommunityCardProps): JSX.Element => {
  const toast = useToast();
  let useCase = useCasesByName[community.use_case];
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

  const saveChanges = async (name: string, description: string) => {
    try {
      await handleUpdateCommunity(community.id, name, description);
      setIsRenameModalOpen(false);
    } catch (e) {
      toast.warning("Something went wrong. Please try again.");
    }
  };

  const deleteCommunity = async () => {
    try {
      await handleDeleteCommunity(community.id);
      setIsDeleteConfirmationModalOpen(false);
    } catch (e) {
      toast.warning("Something went wrong. Please try again.");
    }
  };

  const useCaseIcon = useCase ? (
    <span className="inline-block w-5 h-5">{useCase.icon("#000000")}</span>
  ) : null;
  return (
    <div className="flex-col px-4 py-4 md:pl-4 md:pr-1.5">
      <RenameModal
        isOpen={isRenameModalOpen}
        onClose={handleCloseRenameModal}
        onSaveChanges={saveChanges}
        name={community.name}
        description={community.description}
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
          <p className="text-sm text-black font-medium">
            {useCaseIcon}
            {useCase?.title}
          </p>
          <p className="truncate text-base font-semibold text-gray-900">
            {community.name}
          </p>
          <p className="mt-2 flex items-center text-sm text-gray-500">
            <span className="truncate">{community.description}</span>
          </p>
        </div>
        <div className="mt-4 flex md:mt-5 md:block md:basis-3/12">
          <p className="text-sm text-gray-500 md:flex md:flex-row-reverse">
            Created:
          </p>
          <p className="text-sm text-gray-500 md:flex md:flex-row-reverse">
            {community.created_at
              ? new Date(community.created_at).toDateString()
              : ""}
          </p>
        </div>
        <div className="mt-1 flex md:mt-5 md:block md:basis-3/12">
          <p className="text-right text-sm text-gray-500 md:flex md:flex-row-reverse">
            Scorer ID:
          </p>
          <p className="text-sm text-gray-500 md:flex md:flex-row-reverse">
            {community.id}
          </p>
        </div>
        <div className="absolute top-0 right-0 md:static md:flex md:basis-1/12 md:flex-row-reverse">
          <DropdownMenu
            trigger={
              <button
                data-testid="card-menu-button"
                className="p-2 hover:bg-gray-100 rounded-[8px] transition-colors my-auto flex justify-center"
              >
                <EllipsisVerticalIcon className="h-6 w-6 text-gray-700" />
              </button>
            }
          >
            <DropdownMenuItem
              data-testid={`menu-rename-${community.id}`}
              onClick={handleRename}
            >
              Rename
            </DropdownMenuItem>
            <DropdownMenuItem
              data-testid={`menu-delete-${community.id}`}
              onClick={handleDelete}
            >
              Delete
            </DropdownMenuItem>
          </DropdownMenu>
        </div>
      </div>
    </div>
  );
};

export default CommunityCard;
