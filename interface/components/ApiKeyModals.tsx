import { ArrowBackIcon, SmallCloseIcon } from "@chakra-ui/icons";
import { Center, Input, Text } from "@chakra-ui/react";
import { KeyIcon } from "@heroicons/react/24/outline";
import { useState } from "react";
import { ApiKeys, createApiKey, updateApiKey } from "../utils/account-requests";
import ModalTemplate from "./ModalTemplate";
import { PrimaryBtn } from "./PrimrayBtn";

export type ApiKeyCreateModalProps = {
  isOpen: boolean;
  onClose: () => void;
  onCreateApiKey: (keyName: ApiKeys["name"]) => void;
};

export function ApiKeyCreateModal({
  isOpen,
  onClose,
  onCreateApiKey,
}: ApiKeyCreateModalProps) {
  const [keyName, setKeyName] = useState("");
  const [creationError, setError] = useState<string>("");
  const [inProgress, setInProgress] = useState(false);

  const closeAndReset = () => {
    setKeyName("");
    setError("");
    onClose();
  };

  const createApiKey = async () => {
    setInProgress(true);
    await onCreateApiKey(keyName);
    setInProgress(false);
  };

  return (
    <ModalTemplate isOpen={isOpen} onClose={closeAndReset}>
      <div className="w-100 flex flex-col items-center">
        <div className="w-fit rounded-full bg-[#F0EBFF] p-3 text-purple-gitcoinpurple">
          <div className="flex w-6 justify-around">
            <KeyIcon />
          </div>
        </div>
      </div>
      <div className="mt-6 mb-6 text-center">
        <Text className="text-purple-darkpurple">Generate API Key</Text>
        <Text className="mt-2 text-center text-purple-softpurple">
          Name your API key to help identify it in the future.
        </Text>
      </div>
      <div className="flex flex-col">
        <label className="mb-2 font-librefranklin text-xs text-purple-darkpurple">
          Key Name
        </label>
        <Input
          className="mb-6"
          data-testid="key-name-input"
          value={keyName}
          onChange={(e) => setKeyName(e.target.value)}
          placeholder={"Enter the key's name/identifier"}
          // chakra can't find purple-gitcoinpurple from tailwind :(
          focusBorderColor="#6f3ff5"
        />

        <p className="mb-1 text-xs italic text-purple-softpurple">
          i.e. 'Gitcoin dApp - Prod', or 'Snapshot discord bot', or 'Bankless
          Academy testing', etc.
        </p>
        <hr />
        {creationError.length > 0 && (
          <p className="pt-4 text-red-700">{creationError}</p>
        )}
        <div className="mt-2">
          <PrimaryBtn
            onClick={createApiKey}
            disabled={keyName.length === 0 || inProgress}
          >
            Create
          </PrimaryBtn>
        </div>
      </div>
    </ModalTemplate>
  );
}

export type ApiKeyRenameModalProps = {
  isOpen: boolean;
  onClose: () => void;
  onApiKeyUpdated: (apiKey: ApiKeys) => void;
};

export function ApiKeyRenameModal({
  isOpen,
  onClose,
  onApiKeyUpdated,
}: ApiKeyRenameModalProps) {
  const [keyName, setKeyName] = useState("");
  const [creationError, setError] = useState<string>("");

  const closeAndReset = () => {
    setKeyName("");
    setError("");
    onClose();
  };

  const handleCreateApiKey = async () => {
    try {
      let apiKeyResponse;
      apiKeyResponse = await createApiKey(keyName);
      onApiKeyUpdated(apiKeyResponse);
      closeAndReset();
    } catch (error: any) {
      const msg =
        error?.response?.data?.detail ||
        `There was an error creating your API key. Please try again.`;
      setError(msg);
    }
  };

  return (
    <ModalTemplate isOpen={isOpen} onClose={closeAndReset}>
      <div className="w-100 flex flex-col items-center">
        <div className="w-fit rounded-full bg-[#F0EBFF] p-3 text-purple-gitcoinpurple">
          <div className="flex w-6 justify-around">
            <KeyIcon />
          </div>
        </div>
      </div>
      <div className="mt-6 mb-6 text-center">
        <Text className="text-purple-darkpurple">Generate API Key</Text>
        <Text className="mt-2 text-center text-purple-softpurple">
          Name your API key to help identify it in the future.
        </Text>
      </div>
      <div className="flex flex-col">
        <label className="mb-2 font-librefranklin text-xs text-purple-darkpurple">
          Key Name
        </label>
        <Input
          className="mb-6"
          data-testid="key-name-input"
          value={keyName}
          onChange={(e) => setKeyName(e.target.value)}
          placeholder={"Enter the key's name/identifier"}
          // chakra can't find purple-gitcoinpurple from tailwind :(
          focusBorderColor="#6f3ff5"
        />

        <p className="mb-1 text-xs italic text-purple-softpurple">
          i.e. 'Gitcoin dApp - Prod', or 'Snapshot discord bot', or 'Bankless
          Academy testing', etc.
        </p>
        <hr />
        {creationError.length > 0 && (
          <p className="pt-4 text-red-700">{creationError}</p>
        )}
        <div className="mt-2">
          <PrimaryBtn
            onClick={handleCreateApiKey}
            disabled={keyName.length === 0}
          >
            Create
          </PrimaryBtn>
        </div>
      </div>
    </ModalTemplate>
  );
}
