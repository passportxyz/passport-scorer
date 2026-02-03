import { Input } from "../ui/Input";
import { KeyIcon, NoSymbolIcon } from "@heroicons/react/24/outline";
import { SpinnerIcon } from "./CustomIcons";
import { useContext, useState } from "react";
import { UserContext } from "../context/userContext";
import { ApiKeys, createApiKey } from "../utils/account-requests";
import { ApiKeyDisplay } from "./APIKeyList";
import ModalTemplate from "./ModalTemplate";

export type ApiKeyCreateModalProps = {
  isOpen: boolean;
  onClose: () => void;
  onCreateApiKey: (keyName: ApiKeyDisplay) => void;
};

export function ApiKeyCreateModal({
  isOpen,
  onClose,
  onCreateApiKey,
}: ApiKeyCreateModalProps) {
  const [keyName, setKeyName] = useState("");
  const [creationError, setError] = useState<string>("");
  const [inProgress, setInProgress] = useState(false);
  const { setUserWarning } = useContext(UserContext);

  const closeAndReset = () => {
    setKeyName("");
    setError("");
    onClose();
  };

  const handleCreateApiKey = async () => {
    try {
      setInProgress(true);
      const apiKey: ApiKeyDisplay = await createApiKey(keyName);;
      setInProgress(false);
      setUserWarning(
        "Make sure to paste your API key somewhere safe, as it will be forever hidden after you copy it."
      );
      onCreateApiKey(apiKey);
      closeAndReset();
    } catch (error: any) {
      const msg =
        error?.response?.data?.detail ||
        "There was an error creating your API key. Please try again.";
      setError(msg);
      setInProgress(false);
    }
  };

  return (
    <ModalTemplate
      isOpen={isOpen}
      onClose={closeAndReset}
      footer={() => (
        <button
          className="mb-6 mt-auto w-full rounded-[12px] bg-black py-3 text-white font-medium hover:bg-gray-800 transition-colors md:mt-8 disabled:bg-gray-200 disabled:text-gray-400"
          onClick={handleCreateApiKey}
          disabled={keyName.length === 0 || inProgress}
        >
          Create
        </button>
      )}
    >
      <div className="w-100 flex flex-col items-center">
        <div className="w-fit rounded-full bg-gray-100 p-3 text-gray-700">
          <div className="flex w-6 justify-around">
            <KeyIcon />
          </div>
        </div>
      </div>
      <div className="mt-6 mb-6 text-center">
        <p className="text-gray-900 font-semibold">Generate API Key</p>
        <p className="mt-2 text-center text-gray-500">
          Name your API key to help identify it in the future.
        </p>
      </div>
      <div className="flex flex-col">
        <label className="mb-2 font-sans text-xs text-gray-900">
          Key Name
        </label>
        <Input
          className="mb-6"
          data-testid="key-name-input"
          value={keyName}
          onChange={(e) => setKeyName(e.target.value)}
          placeholder={"Enter the key's name/identifier"}
        />

        <p className="mb-1 text-xs italic text-gray-500">
          i.e. &#39;Human dApp - Prod&#39;, or &#39;Snapshot discord bot&#39;,
          or &#39;Bankless Academy testing&#39;, etc.
        </p>
        <hr className="border-gray-200" />
        {creationError.length > 0 && (
          <p className="pt-4 text-error">{creationError}</p>
        )}
      </div>
    </ModalTemplate>
  );
}

export type ApiKeyUpdateModalProps = {
  isOpen: boolean;
  apiKeyId: ApiKeys["id"];
  onClose: () => void;
  onUpdateApiKey: (apiKeyId: ApiKeys["id"], name: ApiKeys["name"]) => void;
};

export function ApiKeyUpdateModal({
  isOpen,
  apiKeyId,
  onClose,
  onUpdateApiKey,
}: ApiKeyUpdateModalProps) {
  const [name, setName] = useState("");
  const [updateError, setError] = useState<string>("");
  const [inProgress, setInProgress] = useState(false);

  const closeAndReset = () => {
    setName("");
    setError("");
    onClose();
  };

  const updateApiKey = async () => {
    setInProgress(true);
    await onUpdateApiKey(apiKeyId, name);
    setInProgress(false);
  };

  return (
    <ModalTemplate
      isOpen={isOpen}
      onClose={closeAndReset}
      header={() => (
        <span className="text-base font-medium text-gray-900">Rename API Key</span>
      )}
      footer={() => (
        <button
          className="mb-6 mt-auto w-full rounded-[12px] bg-black py-3 text-white font-medium hover:bg-gray-800 transition-colors md:mt-8 disabled:bg-gray-200 disabled:text-gray-400"
          onClick={updateApiKey}
          disabled={name.length === 0 || inProgress}
        >
          Save Changes
        </button>
      )}
    >
      <div className="flex flex-col">
        <label className="mb-2 font-sans text-xs text-gray-900">
          Key Name
        </label>
        <Input
          className="mb-6"
          data-testid="key-name-input"
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder={"Enter the key's name/identifier"}
        />

        <p className="mb-1 text-xs italic text-gray-500">
          i.e. &#39;Human dApp - Prod&#39;, or &#39;Snapshot discord bot&#39;,
          or &#39;Bankless Academy testing&#39;, etc.
        </p>
        <hr className="border-gray-200" />
        {updateError.length > 0 && (
          <p className="pt-4 text-error">{updateError}</p>
        )}
      </div>
    </ModalTemplate>
  );
}

export type ApiKeyDeleteModalProps = {
  isOpen: boolean;
  apiKeyId: ApiKeys["id"];
  onClose: () => void;
  onDeleteApiKey: (apiKeyId: ApiKeys["id"]) => void;
}

export function ApiKeyDeleteModal({
  isOpen,
  apiKeyId,
  onClose,
  onDeleteApiKey,
}: ApiKeyDeleteModalProps) {
  const [deleteError, setError] = useState<string>("");
  const [inProgress, setInProgress] = useState(false);

  const closeAndReset = () => {
    setError("");
    onClose();
  };

  const deleteApiKey = async () => {
    setInProgress(true);
    try {
      await onDeleteApiKey(apiKeyId);
    } catch (e) { }
    setInProgress(false);
    onClose();
  };

  return (
    <ModalTemplate
      isOpen={isOpen}
      onClose={closeAndReset}
    >
      <div className="-mt-8 py-6 text-gray-900">
        <div className="flex items-center justify-center">
          <div className="mb-4 flex h-12 w-12 justify-center rounded-full bg-red-50">
            <NoSymbolIcon className="w-7 text-red-500" />
          </div>
        </div>
        <div className="text-center">
          <p className="font-semibold text-gray-900">Are you sure?</p>
          <p className="mt-2 text-gray-500">
            This will permanantly delete your API Key.
            <br />
            Are you sure you want to continue?
          </p>
        </div>
        <div className="mt-10 grid grid-cols-1 gap-4 md:grid-cols-2">
          <button
            className="order-last w-full rounded-[12px] border border-gray-200 py-2 px-6 text-base text-gray-700 hover:bg-gray-50 transition-colors md:order-first"
            onClick={onClose}
          >
            Cancel
          </button>
          <button
            className="flex w-full justify-center rounded-[12px] bg-black py-2 px-6 text-base text-white font-medium hover:bg-gray-800 transition-colors disabled:bg-gray-200 disabled:text-gray-400"
            onClick={deleteApiKey}
            disabled={inProgress}
          >
            <SpinnerIcon inProgress={inProgress}></SpinnerIcon>
            Confirm Deletion
          </button>
          {deleteError.length > 0 && (
            <p className="pt-4 text-error">{deleteError}</p>
          )}
        </div>
      </div>
    </ModalTemplate >
  );
}
